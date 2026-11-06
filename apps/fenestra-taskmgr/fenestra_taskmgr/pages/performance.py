"""Performance page: device list with mini graphs + detail view with 60-second graphs."""
from __future__ import annotations

from gi.repository import Gdk, Gtk

from .. import util
from ..i18n import _
from ..widgets.common import Menu, ToolButton, label
from ..widgets.graph import CompositionBar, Graph
from .base import Page
from .processes import run_task_dialog

NET_SCALES = [1e4, 5e4, 1e5, 5e5, 1e6, 5e6, 1e7, 5e7, 1e8, 5e8, 1e9, 1e10]
DISK_SCALES = [x * 1048576 for x in (0.1, 0.5, 1, 10, 50, 100, 500, 1000, 5000)]


def nice_scale(peak, scales):
    for s in scales:
        if peak <= s:
            return s
    return scales[-1]


class StatBlock(Gtk.Box):
    """Big stats (label over value) on the left + key/value list on the right."""

    def __init__(self):
        super().__init__(spacing=16)
        self.add_css_class("stat-block")
        self.big = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.append(self.big)
        self.side = Gtk.Grid(column_spacing=12, row_spacing=2)
        self.side.set_margin_top(4)
        self.side.set_valign(Gtk.Align.START)
        self.append(self.side)
        self.values = {}
        self.side_values = {}

    def add_row(self, keys, bar=None):
        row = Gtk.Box(spacing=18)
        for i, k in enumerate(keys):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            col.append(label(k, "stat-key"))
            v = label("", "stat-value")
            col.append(v)
            if bar:
                wrap = Gtk.Box()
                line = Gtk.DrawingArea()
                line.set_size_request(1, -1)
                line.set_margin_end(7)
                line.set_draw_func(_bar_draw, bar[i] if isinstance(bar, (list, tuple)) else bar)
                wrap.append(line)
                wrap.append(col)
                row.append(wrap)
            else:
                row.append(col)
            self.values[k] = v
        self.big.append(row)

    def add_side(self, key):
        n = len(self.side_values)
        self.side.attach(label(key + ":", "stat-side-key"), 0, n, 1, 1)
        v = label("", "stat-side-value")
        self.side.attach(v, 1, n, 1, 1)
        self.side_values[key] = v

    def set(self, key, text):
        w = self.values.get(key) or self.side_values.get(key)
        if w is not None and w.get_text() != text:
            w.set_text(text)


def _bar_draw(area, cr, w, h, style):
    from .. import theme
    line = theme.get().graph[style[0]][0]
    cr.set_source_rgba(line.red, line.green, line.blue, 1)
    cr.set_line_width(1)
    if style[1] == "dash":
        cr.set_dash([3, 2])
    cr.move_to(0.5, 2)
    cr.line_to(0.5, h)
    cr.stroke()


class Device:
    def __init__(self, page, key, kind):
        self.page, self.key, self.kind = page, key, kind
        self.item = Gtk.Button()
        self.item.add_css_class("perf-item")
        box = Gtk.Box(spacing=10)
        self.mini = Graph(kind, mini=True, min_h=40)
        self.mini.set_size_request(60, -1)
        box.append(self.mini)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        txt.set_valign(Gtk.Align.START)
        self.t1 = label("", "perf-item-title")
        self.t2 = label("", "perf-item-sub")
        self.t3 = label("", "perf-item-sub")
        self.t3.set_visible(False)
        txt.append(self.t1)
        txt.append(self.t2)
        txt.append(self.t3)
        box.append(txt)
        self.item.set_child(box)
        self.item.connect("clicked", lambda *_: page.select(self.key))
        self.view = None

    def set_lines(self, a, b, c=None):
        if self.t1.get_text() != a:
            self.t1.set_text(a)
        if self.t2.get_text() != b:
            self.t2.set_text(b)
        self.t3.set_visible(c is not None)
        if c is not None and self.t3.get_text() != c:
            self.t3.set_text(c)


class DetailView(Gtk.Box):
    def __init__(self, kind):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("perf-detail")
        self.kind = kind
        head = Gtk.Box()
        head.add_css_class("perf-head")
        self.title = label("", "perf-title")
        head.append(self.title)
        self.model = label("", "perf-model", xalign=1.0, ellipsize=True)
        self.model.set_hexpand(True)
        self.model.set_valign(Gtk.Align.CENTER)
        self.model.set_margin_top(6)
        head.append(self.model)
        self.append(head)
        self.stats = StatBlock()

    def axis(self, left, right):
        b = Gtk.Box()
        lft = label(left, "perf-axis")
        b.append(lft)
        r = label(right, "perf-axis", xalign=1.0)
        r.set_hexpand(True)
        b.append(r)
        self.append(b)
        return lft, r

    def graph(self, kind, vexpand=True, min_h=60):
        g = Graph(kind, min_h=min_h)
        g.set_vexpand(vexpand)
        g.set_margin_top(1)
        self.append(g)
        return g


class PerformancePage(Page):
    pid = "performance"
    title = _("Performance")
    searchable = False

    def __init__(self, win):
        super().__init__(win)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        lsw = Gtk.ScrolledWindow()
        lsw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.list.add_css_class("perf-list")
        lsw.set_child(self.list)
        lsw.set_size_request(211, -1)
        self.append(lsw)
        self.rsw = Gtk.ScrolledWindow()
        self.rsw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.rsw.set_hexpand(True)
        self.detail_stack = Gtk.Stack()
        self.detail_stack.set_hhomogeneous(False)
        self.detail_stack.set_vhomogeneous(False)
        self.detail_stack.set_size_request(380, 420)
        self.rsw.set_child(self.detail_stack)
        self.append(self.rsw)
        self.devices: dict[str, Device] = {}
        self.order: list[str] = []
        self.current = None
        self.want = getattr(win, "perf_start", None) or "cpu"
        self.run_btn = ToolButton("tm-run-symbolic", _("Run new task"), lambda: run_task_dialog(self.win))
        click = Gtk.GestureClick(button=3)
        click.connect("pressed", self._graph_menu)
        self.detail_stack.add_controller(click)

    def tools(self):
        return [self.run_btn]

    def more_menu(self, m):
        m.add(_("Copy"), self.copy, icon_name="tm-copy-symbolic", shortcut="Ctrl+C")
        if self.current == "cpu":
            m.add(_("Overall utilization"), lambda: self._cpu_mode("overall"),
                  check=util.opts()["cpu_graph"] == "overall")
            m.add(_("Logical processors"), lambda: self._cpu_mode("logical"),
                  check=util.opts()["cpu_graph"] == "logical")
        m.add_separator()

    def _graph_menu(self, g, n, x, y):
        if self.current != "cpu":
            return
        m = Menu(self.detail_stack)
        m.add(_("Overall utilization"), lambda: self._cpu_mode("overall"),
              check=util.opts()["cpu_graph"] == "overall")
        m.add(_("Logical processors"), lambda: self._cpu_mode("logical"),
              check=util.opts()["cpu_graph"] == "logical")
        m.add_separator()
        m.add(_("Copy"), self.copy, icon_name="tm-copy-symbolic")
        m.popup_at(x, y)

    def _cpu_mode(self, mode):
        util.opts().set("cpu_graph", mode)
        d = self.devices.get("cpu")
        if d and d.view:
            d.view.big_graph.set_visible(mode == "overall")
            d.view.cores.set_visible(mode == "logical")
        if self.win.snap:
            self.update(self.win.snap)

    def copy(self):
        d = self.devices.get(self.current)
        if not d or not d.view:
            return
        lines = [d.view.title.get_text(), d.view.model.get_text()]
        st = d.view.stats
        for k, v in list(st.values.items()) + list(st.side_values.items()):
            lines.append(f"{k}\t{v.get_text()}")
        Gdk.Display.get_default().get_clipboard().set("\n".join(lines))

    # ------------------------------------------------------------ devices
    def _ensure(self, key, kind):
        d = self.devices.get(key)
        if d is None:
            d = Device(self, key, kind)
            self.devices[key] = d
            self.order.append(key)
            self.list.append(d.item)
        return d

    def select(self, key):
        if key not in self.devices:
            key = "cpu"
        self.current = key
        for k, d in self.devices.items():
            if k == key:
                d.item.add_css_class("selected")
            else:
                d.item.remove_css_class("selected")
        d = self.devices[key]
        if d.view is None:
            d.view = self._build_view(d)
            self.detail_stack.add_named(d.view, key)
        self.detail_stack.set_visible_child(d.view)
        if self.win.snap:
            self.update(self.win.snap)

    def _build_view(self, d):
        v = DetailView(d.kind)
        st = v.stats
        if d.kind == "cpu":
            v.title.set_text(_("CPU"))
            v.axis(_("% Utilization"), "100%")
            v.big_graph = v.graph("cpu")
            v.cores = Gtk.Grid(column_spacing=4, row_spacing=4, column_homogeneous=True,
                               row_homogeneous=True)
            v.cores.set_vexpand(True)
            v.core_graphs = []
            v.append(v.cores)
            mode = util.opts()["cpu_graph"]
            v.big_graph.set_visible(mode == "overall")
            v.cores.set_visible(mode == "logical")
            v.axis(_("60 seconds"), "0")
            st.add_row([_("Utilization"), _("Speed")])
            st.add_row([_("Processes"), _("Threads"), _("Handles")])
            st.add_row([_("Up time")])
            s = self.win.collector.static
            st.add_side(_("Base speed"))
            st.add_side(_("Sockets"))
            if s.vm:
                st.add_side(_("Virtual processors"))
                st.add_side(_("Virtual machine"))
            else:
                st.add_side(_("Cores"))
                st.add_side(_("Logical processors"))
                st.add_side(_("Virtualization"))
            if s.caches:
                for lvl in sorted(s.caches):
                    st.add_side(_("L%s cache") % lvl)
            else:
                st.add_side(_("L%s cache") % "1")
        elif d.kind == "mem":
            v.title.set_text(_("Memory"))
            v.axis(_("Memory usage"), "")
            v.big_graph = v.graph("mem")
            v.axis(_("60 seconds"), "0")
            sp = label(_("Memory composition"), "perf-axis")
            sp.set_margin_top(8)
            v.append(sp)
            v.comp = CompositionBar()
            v.comp.set_margin_top(4)
            v.append(v.comp)
            st.add_row([_("In use (Compressed)"), _("Available")])
            st.add_row([_("Committed"), _("Cached")])
            st.add_row([_("Paged pool"), _("Non-paged pool")])
            st.add_side(_("Slots used"))
            st.add_side(_("Hardware reserved"))
        elif d.kind == "disk":
            v.title.set_text("")
            v.axis(_("Active time"), "100%")
            v.big_graph = v.graph("disk")
            v.axis(_("60 seconds"), "0")
            ax = v.axis(_("Disk transfer rate"), "")
            ax[0].set_margin_top(8)
            v.rate_label = ax[1]
            v.rate_graph = v.graph("disk", vexpand=False, min_h=66)
            v.rate_graph.rows = 6
            v.axis(_("60 seconds"), "0")
            st.add_row([_("Active time"), _("Average response time")])
            st.add_row([_("Read speed"), _("Write speed")], bar=[("disk", "dash"), ("disk", "solid")])
            for k in (_("Capacity"), _("Formatted"), _("System disk"), _("Page file"), _("Type")):
                st.add_side(k)
        elif d.kind == "net":
            v.axis(_("Throughput"), "")
            v.scale_label = v.model  # placeholder replaced below
            v.big_graph = v.graph("net")
            v.axis(_("60 seconds"), "0")
            st.add_row([_("Send")], bar=[("net", "dash")])
            st.add_row([_("Receive")], bar=[("net", "solid")])
            st.add_side(_("Adapter name"))
            if d.key in self._wifi_keys:
                st.add_side(_("SSID"))
            st.add_side(_("Connection type"))
            st.add_side(_("IPv4 address"))
            st.add_side(_("IPv6 address"))
        else:  # gpu
            v.axis(_("Utilization"), "100%")
            v.big_graph = v.graph("gpu")
            v.axis(_("60 seconds"), "0")
            st.add_row([_("Utilization")])
        # axis label boxes: the first axis row's right label shows the scale
        first_axis = v.get_first_child().get_next_sibling()
        v.top_right = first_axis.get_last_child()
        st.set_margin_top(4)
        v.append(st)
        return v

    # ------------------------------------------------------------ updates
    _wifi_keys: set = set()

    def update(self, snap):
        h = self.win.history
        tick = h.ticks
        static = self.win.collector.static
        # CPU
        cpu = self._ensure("cpu", "cpu")
        cpu.mini.set_data([(h.get("cpu"), "fill")], 100, tick)
        cpu.set_lines(_("CPU"), f"{util.fmt_pct0(snap.cpu_total)}  {util.fmt_ghz(snap.freq_khz)}")
        # memory
        m = snap.mem
        mem = self._ensure("mem", "mem")
        mem.mini.set_data([(h.get("mem"), "fill")], 100, tick)
        gb = 1024 ** 3
        mem.set_lines(_("Memory"), f"{m['used'] / gb:.1f}/{m['total'] / gb:.1f} GB "
                      f"({util.fmt_pct0(m['used'] / m['total'] * 100)})")
        for d in snap.disks:
            key = f"disk{d['index']}"
            dv = self._ensure(key, "disk")
            dv.mini.set_data([(h.get(f"disk:{d['name']}"), "fill")], 100, tick)
            dv.disk = d
            dv.set_lines(self._disk_title(d), d["type"], util.fmt_pct0(d["active"]))
        for i, n in enumerate(snap.nets):
            key = f"net{i}"
            if n["kind"] == "wifi":
                self._wifi_keys.add(key)
            nv = self._ensure(key, "net")
            s_, r_ = h.get(f"nets:{n['id']}"), h.get(f"netr:{n['id']}")
            peak = max([x for x in s_ + r_ if x] or [0])
            sc = nice_scale(max(peak, 1), NET_SCALES)
            mline = float(f"{min(peak, sc * 0.8):.1g}") if peak > sc * 0.15 else None
            nv.mini.set_data([(r_, "fill"), (s_, "line")], sc, tick, scale_line=mline)
            nv.net = n
            sub = n["conn"] or n["label"] if n["up"] else _("Not connected")
            nv.set_lines(n["label"], sub,
                         _("S: %s R: %s Kbps") % (util.fmt_bits_int(n["send"]), util.fmt_bits_int(n["recv"])))
        for g in snap.gpus:
            key = f"gpu{g['index']}"
            gv = self._ensure(key, "gpu")
            gv.mini.set_data([(h.get(f"gpu:{g['index']}"), "fill")], 100, tick)
            gv.gpu = g
            gv.set_lines(f"GPU {g['index']}", g["name"], util.fmt_pct0(g["busy"]))
        if self.current is None:
            self.select(self.want if self.want in self.devices else "cpu")
            return
        d = self.devices.get(self.current)
        if d is None or d.view is None or not self.get_mapped() and not util.DEMO:
            return
        v = d.view
        st = v.stats
        if d.kind == "cpu":
            v.model.set_text(static.cpu_model)
            if v.big_graph.get_visible():
                v.big_graph.set_data([(h.get("cpu"), "fill")], 100, tick)
            else:
                self._cores(v, snap, h, tick)
            st.set(_("Utilization"), util.fmt_pct0(snap.cpu_total))
            st.set(_("Speed"), util.fmt_ghz(snap.freq_khz))
            st.set(_("Processes"), str(snap.n_procs))
            st.set(_("Threads"), str(snap.n_threads))
            st.set(_("Handles"), str(snap.n_handles))
            st.set(_("Up time"), util.fmt_uptime(snap.uptime))
            st.set(_("Base speed"), util.fmt_ghz(static.base_khz) if static.base_khz else "N/A")
            st.set(_("Sockets"), str(static.sockets))
            st.set(_("Virtual processors"), str(static.logical))
            st.set(_("Virtual machine"), _("Yes"))
            st.set(_("Cores"), str(static.cores))
            st.set(_("Logical processors"), str(static.logical))
            st.set(_("Virtualization"), _("Enabled") if static.virtualization else _("Not capable"))
            if static.caches:
                for lvl, size in static.caches.items():
                    st.set(_("L%s cache") % lvl, util.fmt_size(size))
            else:
                st.set(_("L%s cache") % "1", "N/A")
        elif d.kind == "mem":
            total = m["total"]
            v.model.set_text(util.fmt_size(total + m.get("reserved", 0)))
            v.top_right.set_text(util.fmt_size(total))
            v.big_graph.set_data([(h.get("mem"), "fill")], 100, tick)
            standby = max(0, m["avail"] - m["free"])
            v.comp.set_parts(m["used"], m["modified"], standby, m["free"])
            st.set(_("In use (Compressed)"), f"{util.fmt_size(m['used'])} ({util.fmt_size(m['compressed'])})")
            st.set(_("Available"), util.fmt_size(m["avail"]))
            st.set(_("Committed"), f"{m['committed'] / gb:.1f}/{m['commit_limit'] / gb:.1f} GB")
            st.set(_("Cached"), util.fmt_size(m["cached"]))
            st.set(_("Paged pool"), util.fmt_size(m["paged"]))
            st.set(_("Non-paged pool"), util.fmt_size(m["nonpaged"]))
            st.set(_("Slots used"), "N/A")
            st.set(_("Hardware reserved"), util.fmt_size(m.get("reserved", 0)))
        elif d.kind == "disk":
            dd = d.disk
            v.title.set_text(self._disk_title(dd))
            v.model.set_text(dd["model"])
            v.big_graph.set_data([(h.get(f"disk:{dd['name']}"), "fill")], 100, tick)
            r_, w_ = h.get(f"diskr:{dd['name']}"), h.get(f"diskw:{dd['name']}")
            peak = max([x for x in r_ + w_ if x] or [0])
            sc = nice_scale(max(peak, 1), DISK_SCALES)
            v.rate_label.set_text(util.fmt_scale_bytes(sc))
            v.rate_graph.set_data([(w_, "fill"), (r_, "dash")], sc, tick)
            st.set(_("Active time"), util.fmt_pct0(dd["active"]))
            st.set(_("Average response time"), f"{dd['resp']:.1f} ms")
            st.set(_("Read speed"), util.fmt_bps_short(dd["read"]))
            st.set(_("Write speed"), util.fmt_bps_short(dd["write"]))
            st.set(_("Capacity"), util.fmt_size(dd["capacity"]))
            st.set(_("Formatted"), util.fmt_size(dd["formatted"]))
            st.set(_("System disk"), _("Yes") if dd["system"] else _("No"))
            st.set(_("Page file"), _("Yes") if dd["pagefile"] else _("No"))
            st.set(_("Type"), dd["type"])
        elif d.kind == "net":
            n = d.net
            v.title.set_text(n["label"])
            v.model.set_text(n["adapter"])
            s_, r_ = h.get(f"nets:{n['id']}"), h.get(f"netr:{n['id']}")
            peak = max([x for x in s_ + r_ if x] or [0])
            sc = nice_scale(max(peak, 1), NET_SCALES)
            v.top_right.set_text(util.fmt_scale(sc))
            line = None
            if peak > sc * 0.15:
                line = min(peak, sc * 0.8)
                line = float(f"{line:.1g}")
            v.big_graph.set_data([(r_, "fill"), (s_, "dash")], sc, tick, scale_line=line,
                                 scale_text=util.fmt_scale(line) if line else None)
            st.set(_("Send"), util.fmt_bits(n["send"]))
            st.set(_("Receive"), util.fmt_bits(n["recv"]))
            st.set(_("Adapter name"), n["label"])
            st.set(_("SSID"), n["conn"])
            st.set(_("Connection type"), "802.11" if n["kind"] == "wifi" else _("Ethernet"))
            st.set(_("IPv4 address"), n["ipv4"] or "—")
            st.set(_("IPv6 address"), n["ipv6"] or "—")
        else:
            g = d.gpu
            v.title.set_text(f"GPU {g['index']}")
            v.model.set_text(g["name"])
            v.big_graph.set_data([(h.get(f"gpu:{g['index']}"), "fill")], 100, tick)
            st.set(_("Utilization"), util.fmt_pct0(g["busy"]))

    def _cores(self, v, snap, h, tick):
        n = len(snap.cpu_cores)
        if len(v.core_graphs) != n:
            cols = 1
            while cols * cols < n:
                cols += 1
            for i in range(n):
                g = Graph("cpu", min_h=30, rows=4, cols=6)
                g.set_hexpand(True)
                g.set_vexpand(True)
                v.cores.attach(g, i % cols, i // cols, 1, 1)
                v.core_graphs.append(g)
        for i, g in enumerate(v.core_graphs):
            g.set_data([(h.get(f"cpu{i}"), "fill")], 100, tick)

    @staticmethod
    def _disk_title(d):
        t = _("Disk %d") % d["index"]
        return f"{t} ({d['label']})" if d["label"] else t

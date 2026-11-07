"""Main window: title bar with search, navigation rail, command bar and page stack."""
from __future__ import annotations

import os

from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk

from . import theme, util
from .i18n import _
from .sampler import History
from .widgets.common import Menu, ToolSlot, icon, label

NAV = [
    ("processes", "tm-processes-symbolic", "Processes"),
    ("performance", "tm-performance-symbolic", "Performance"),
    ("apphistory", "tm-history-symbolic", "App history"),
    ("startup", "tm-startup-symbolic", "Startup apps"),
    ("users", "tm-users-symbolic", "Users"),
    ("details", "tm-details-symbolic", "Details"),
    ("services", "tm-services-symbolic", "Services"),
]


class NavItem(Gtk.Button):
    def __init__(self, pid, icon_name, text, cb):
        super().__init__()
        self.pid = pid
        self.add_css_class("nav-item")
        box = Gtk.Box()
        self.pill = Gtk.Box()
        self.pill.add_css_class("nav-pill")
        self.pill.set_valign(Gtk.Align.CENTER)
        box.append(self.pill)
        box.append(icon(icon_name, 20, "nav-icon"))
        self.lbl = label(_(text), "nav-label")
        box.append(self.lbl)
        self.set_child(box)
        self.set_tooltip_text(_(text))
        self.connect("clicked", lambda *_: cb(pid))

    def set_selected(self, on):
        if on:
            self.add_css_class("selected")
        else:
            self.remove_css_class("selected")


_logged = set()


def _log_once(key, msg):
    if key not in _logged:
        _logged.add(key)
        print(f"fenestra-taskmgr: {msg}", flush=True)


class TitleBar(Gtk.Widget):
    """Title bar layout: icon + title on the left, caption buttons on the right and the
    search box centred like Windows (34 % of the width, 200-600 px).  Its minimum width
    never depends on the current window width, so restoring a maximised window can
    always shrink it back (a size request computed from the allocation used to pin the
    title bar wider than the window)."""
    __gtype_name__ = "FenestraTaskTitleBar"

    def __init__(self):
        super().__init__()
        self.add_css_class("titlebar")
        self.start = self.center = self.end = None

    def _set(self, attr, w):
        old = getattr(self, attr)
        if old is not None:
            old.unparent()
        setattr(self, attr, w)
        w.set_parent(self)

    def set_start(self, w):
        self._set("start", w)

    def set_center(self, w):
        self._set("center", w)

    def set_end(self, w):
        self._set("end", w)

    def _kids(self):
        return [w for w in (self.start, self.center, self.end) if w is not None and w.get_visible()]

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            mn = nat = 0
            for w in (self.start, self.end):
                if w is not None and w.get_visible():
                    a, b, _x, _y = w.measure(orientation, -1)
                    mn += a
                    nat += b
            return mn, nat + 600, -1, -1
        mn = nat = 0
        for w in self._kids():
            a, b, _x, _y = w.measure(orientation, -1)
            mn, nat = max(mn, a), max(nat, b)
        return mn, nat, -1, -1

    def do_size_allocate(self, w, h, baseline):
        left = right = 0
        if self.start is not None and self.start.get_visible():
            mn, nat, _a, _b = self.start.measure(Gtk.Orientation.HORIZONTAL, -1)
            sw = max(mn, min(nat, w))
            self.start.allocate(sw, h, -1, None)
            left = sw
        if self.end is not None and self.end.get_visible():
            mn, nat, _a, _b = self.end.measure(Gtk.Orientation.HORIZONTAL, -1)
            ew = max(mn, min(nat, max(0, w - left)))
            tr = Gsk.Transform().translate(_pt(w - ew, 0))
            self.end.allocate(ew, h, -1, tr)
            right = ew
        c = self.center
        if c is not None and c.get_visible():
            mn, _nat, _a, _b = c.measure(Gtk.Orientation.HORIZONTAL, -1)
            want = round(min(600, max(200, w * 0.34)))
            avail_l, avail_r = left + 12, w - right - 12
            cw = max(0, min(want, avail_r - avail_l))
            if cw < max(mn, 120):
                c.set_child_visible(False)
                return
            c.set_child_visible(True)
            x = int(w / 2 + 13 - cw / 2)  # measured: 265 px at 764 px
            x = max(avail_l, min(x, avail_r - cw))
            ch = min(h, c.measure(Gtk.Orientation.VERTICAL, cw)[1])
            tr = Gsk.Transform().translate(_pt(x, int((h - ch) / 2)))
            c.allocate(cw, ch, -1, tr)


def _pt(x, y):
    p = Graphene.Point()
    p.x, p.y = x, y
    return p


class TaskWindow(Gtk.ApplicationWindow):
    def __init__(self, app, collector, start_page="processes", expanded=None):
        super().__init__(application=app)
        self.app = app
        self.collector = collector
        self.set_title(_("Task Manager"))
        self.set_icon_name("org.fenestra.TaskManager")
        self.set_default_size(764, 580)
        self.set_size_request(400, 300)
        self.add_css_class("taskmgr")
        self.pages = {}
        self.current = None
        self.snap = None
        self.history = History()
        if hasattr(collector, "preload"):
            collector.preload(self.history)
        self.app_cpu = {}       # App history: app id -> (name, icon, cpu seconds)
        self.dialog = None
        o = util.opts()
        self.expanded = o["nav_expanded"] if expanded is None else expanded

        # ------------------------------------------------------------ title bar
        handle = Gtk.WindowHandle()
        bar = TitleBar()
        bar.add_css_class("titlebar")
        start = Gtk.Box()
        start.append(icon("org.fenestra.TaskManager", 16, "title-icon"))
        start.append(label(_("Task Manager"), "title-label"))
        bar.set_start(start)
        self.search = Gtk.Entry()
        self.search.add_css_class("title-search")
        self.search.set_placeholder_text(_("Type a name, publisher, or PID to search"))
        self.search.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "tm-search-symbolic")
        self.search.set_valign(Gtk.Align.CENTER)
        self.search.connect("changed", self._on_search)
        bar.set_center(self.search)
        caps = Gtk.Box()
        caps.add_css_class("caption-buttons")
        caps.set_valign(Gtk.Align.START)
        for name, cb in (("minimize", lambda *_: self.minimize()),
                         ("maximize", lambda *_: self.unmaximize() if self.is_maximized() else self.maximize()),
                         ("close", lambda *_: self.close())):
            b = Gtk.Button()
            b.add_css_class("caption")
            b.add_css_class(name)
            b.set_child(Gtk.DrawingArea())
            b.get_child().set_draw_func(self._draw_caption, name)
            b.connect("clicked", cb)
            caps.append(b)
        bar.set_end(caps)
        handle.set_child(bar)
        self.set_titlebar(handle)

        # ------------------------------------------------------------ body
        self.overlay = Gtk.Overlay()
        self.set_child(self.overlay)
        body = Gtk.Box()
        body.add_css_class("body")
        self.overlay.set_child(body)

        self.nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.nav.add_css_class("nav")
        ham = Gtk.Button()
        ham.add_css_class("nav-item")
        ham.add_css_class("hamburger")
        hb = Gtk.Box()
        hb.append(Gtk.Box(css_classes=["nav-pill"]))
        hb.append(icon("tm-nav-symbolic", 20, "nav-icon"))
        ham.set_child(hb)
        ham.set_tooltip_text(_("Navigation"))
        ham.connect("clicked", lambda *_: self.set_expanded(not self.expanded))
        self.nav.append(ham)
        self.nav_items = {}
        for pid, ic, text in NAV:
            it = NavItem(pid, ic, text, self.navigate)
            self.nav_items[pid] = it
            self.nav.append(it)
        self.nav.append(Gtk.Box(vexpand=True))
        it = NavItem("settings", "tm-settings-symbolic", "Settings", self.navigate)
        it.add_css_class("nav-settings")
        self.nav_items["settings"] = it
        self.nav.append(it)
        body.append(self.nav)

        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.panel.add_css_class("panel")
        self.toolbar = Gtk.Box()
        self.toolbar.add_css_class("page-toolbar")
        self.page_title = label("", "page-title")
        self.toolbar.append(self.page_title)
        self.toolbar.append(Gtk.Box(hexpand=True))
        self.tool_slot = ToolSlot()
        self.tool_slot.set_hexpand(False)
        self.tool_slot.add_css_class("tool-slot")
        self.toolbar.append(self.tool_slot)
        self.more_btn = Gtk.Button()
        self.more_btn.add_css_class("tool-button")
        self.more_btn.add_css_class("more-button")
        self.more_btn.set_child(icon("tm-more-symbolic", 24))
        self.more_btn.set_tooltip_text(_("See more"))
        self.more_btn.connect("clicked", self._more)
        self.toolbar.append(self.more_btn)
        self.panel.append(self.toolbar)
        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_hhomogeneous(False)
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.panel.append(self.stack)
        body.append(self.panel)

        self.smoke = Gtk.Box()
        self.smoke.add_css_class("smoke")
        self.smoke.set_visible(False)
        self.overlay.add_overlay(self.smoke)

        if os.environ.get("FENESTRA_TASKMGR_DEBUG_INPUT"):
            dbg = Gtk.GestureClick(button=0)
            dbg.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

            def _dbg(g, n, x, y):
                w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
                chain = []
                while w is not None:
                    chain.append(type(w).__name__ + ("." + ".".join(w.get_css_classes()) if w.get_css_classes() else ""))
                    w = w.get_parent()
                print(f"PRESS t={GLib.get_monotonic_time()} {x:.0f},{y:.0f} n={n} -> {' < '.join(chain[:6])}", flush=True)
            dbg.connect("pressed", _dbg)
            self.add_controller(dbg)
            self.connect("notify::is-active", lambda *_: print(f"ACTIVE {self.is_active()} t={GLib.get_monotonic_time()}", flush=True))
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.set_expanded(self.expanded)
        self.navigate(start_page)

    # ------------------------------------------------------------ chrome
    def _draw_caption(self, area, cr, w, h, name):
        c = theme.get().c["fg"]
        if theme.get().dark:
            cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
        else:
            cr.set_source_rgba(0, 0, 0, 1)  # reference light caption glyphs are pure black
        cr.set_line_width(1.0)
        cx, cy = int(w / 2), int(h / 2) - 1
        if name == "minimize":
            cr.rectangle(cx - 4, cy + 0, 10, 1)
            cr.fill()
        elif name == "maximize":
            if self.is_maximized():
                cr.rectangle(cx - 4.5, cy - 2.5, 7, 7)
                cr.stroke()
                cr.move_to(cx - 2.5, cy - 4.5)
                cr.line_to(cx + 4.5, cy - 4.5)
                cr.line_to(cx + 4.5, cy + 2.5)
                cr.stroke()
            else:
                cr.rectangle(cx - 4.5, cy - 4.5, 9, 9)
                cr.stroke()
        else:
            # 10 x 10 px like the reference (through pixel centres, not 12 px of antialiasing)
            cr.move_to(cx - 4.5, cy - 4.5)
            cr.line_to(cx + 4.5, cy + 4.5)
            cr.move_to(cx + 4.5, cy - 4.5)
            cr.line_to(cx - 4.5, cy + 4.5)
            cr.stroke()

    def set_expanded(self, on):
        self.expanded = on
        if on:
            self.nav.add_css_class("expanded")
        else:
            self.nav.remove_css_class("expanded")
        for it in self.nav_items.values():
            it.lbl.set_visible(on)
        if not util.DEMO:
            util.opts().set("nav_expanded", on)

    # ------------------------------------------------------------ pages
    def get_page(self, pid):
        if pid not in self.pages:
            from .pages import PAGES
            cls = PAGES.get(pid) or PAGES["processes"]
            page = cls(self)
            self.pages[pid] = page
            self.stack.add_named(page, pid)
        return self.pages[pid]

    def navigate(self, pid):
        from .pages import PAGES
        if pid not in PAGES:
            pid = "processes"
        page = self.get_page(pid)
        if self.current is page:
            return
        self.current = page
        self.stack.set_visible_child(page)
        for k, it in self.nav_items.items():
            it.set_selected(k == pid)
        self.page_title.set_text(page.title)
        self.toolbar.set_visible(page.has_toolbar)
        if page.has_toolbar:  # Settings sits straight on the window background
            self.panel.remove_css_class("flat")
        else:
            self.panel.add_css_class("flat")
        child = self.tool_slot.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.tool_slot.remove(child)
            child = nxt
        for w in page.tools():
            self.tool_slot.append(w)
        self.search.set_visible(page.searchable)
        if page.searchable:
            page.set_filter(self.search.get_text())
        if self.snap is not None:
            page.update(self.snap)
        page.shown()

    def _on_search(self, entry):
        if self.current is not None and self.current.searchable:
            self.current.set_filter(entry.get_text())

    def _more(self, btn):
        m = Menu(btn)
        hidden = list(self.tool_slot.overflow)
        for b in hidden:
            m.add(b.text, lambda b=b: b.emit("clicked"), icon_name=b.icon_name, sensitive=b.get_sensitive())
        if hidden:
            m.add_separator()
        if self.current is not None:
            self.current.more_menu(m)
        m.add(_("Always on top"), lambda: self._toggle_opt("always_on_top"),
              check=util.opts()["always_on_top"])
        m.add(_("Settings"), lambda: self.navigate("settings"), icon_name="tm-settings-symbolic")
        m.set_position(Gtk.PositionType.BOTTOM)
        m.popup()

    def _toggle_opt(self, key):
        util.opts().set(key, not util.opts()[key])

    def _on_key(self, _c, keyval, keycode, state):
        name = Gdk.keyval_name(keyval) or ""
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if ctrl and name in ("f", "e") and self.search.get_visible():
            self.search.grab_focus()
            return True
        if name == "Escape" and self.dialog is not None:
            self.hide_dialog(self.dialog)
            return True
        if name == "Escape" and self.search.get_text() and self.get_focus() is not None \
                and self.get_focus().is_ancestor(self.search):
            self.search.set_text("")
            return True
        if name == "F5" and self.app.sampler is not None:
            self.app.sampler.refresh()
            return True
        if ctrl and name.isdigit() and 1 <= int(name) <= 7:
            self.navigate(NAV[int(name) - 1][0])
            return True
        return False

    # ------------------------------------------------------------ data
    def on_snapshot(self, snap):
        """Main-loop side of a sample.  Never raises: a failure is logged once per kind
        and the UI keeps running with the previous data."""
        self.snap = snap
        try:
            self.history.add_snapshot(snap)
            self._account_app_cpu(snap)
        except Exception as e:  # noqa: BLE001
            _log_once("history", f"history update failed: {e!r}")
        if self.current is not None:
            try:
                self.current.update(snap)
            except Exception as e:  # noqa: BLE001
                _log_once("page-" + self.current.pid, f"{self.current.pid} page update failed: {e!r}")
                import traceback
                traceback.print_exc()

    def _account_app_cpu(self, snap):
        """App history: CPU seconds per app = finished processes (folded into 'done')
        + live processes.  Dead pids are dropped so the table stays bounded."""
        live = {}
        for p in snap.procs.values():
            if p.app_id:
                live.setdefault(p.app_id, {})[(p.pid, p.start)] = p.cputime
        for aid, pids in live.items():
            if aid not in self.app_cpu:
                info = snap.apps.get(aid)
                name, ic = (info[0], info[1]) if info else (aid, None)
                self.app_cpu[aid] = {"name": name, "icon": ic, "pids": {}, "done": 0.0}
        for aid, rec in self.app_cpu.items():
            now = live.get(aid, {})
            for key, secs in rec["pids"].items():
                if key not in now:
                    rec["done"] = rec.get("done", 0.0) + secs
            rec["pids"] = now

    # ------------------------------------------------------------ dialogs
    def show_dialog(self, dlg):
        if self.dialog is not None:
            self.hide_dialog(self.dialog)
        self.dialog = dlg
        self.smoke.set_visible(True)
        self.overlay.add_overlay(dlg)

    def hide_dialog(self, dlg):
        if dlg.get_parent() is not None:
            self.overlay.remove_overlay(dlg)
        if self.dialog is dlg:
            self.dialog = None
            self.smoke.set_visible(False)

"""Entry point, command line and screenshot mode."""
from __future__ import annotations

import argparse
import os
import sys
import time

T0 = time.monotonic()

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gio, GLib, Graphene, Gsk, Gtk  # noqa: E402

from . import i18n, theme, util  # noqa: E402

PAGE_ALIASES = {"apps": "apphistory", "history": "apphistory", "app-history": "apphistory",
                "startup-apps": "startup", "perf": "performance"}
PERF_ALIASES = {"memory": "mem", "disk": "disk0", "ethernet": "net0", "wifi": "net0", "network": "net0",
                "cpu": "cpu", "gpu": "gpu0"}


def parse_args(argv):
    p = argparse.ArgumentParser(prog="fenestra-taskmgr", description="Fenestra Task Manager")
    p.add_argument("--page", default=None, help="processes, performance, apphistory, startup, users, "
                   "details, services, settings")
    p.add_argument("--perf", default=None, help="performance device: cpu, memory, disk, ethernet, gpu")
    p.add_argument("--screenshot", metavar="OUT.png", help="render the window to a PNG and quit")
    p.add_argument("--size", default=None, help="window size WxH (screenshot mode)")
    p.add_argument("--expanded", action="store_true", help="start with the navigation pane expanded")
    p.add_argument("--collapsed", action="store_true", help="start with the navigation pane collapsed")
    p.add_argument("--maximized", action="store_true", help="draw as maximised (no rounded corners)")
    p.add_argument("--dark", action="store_true")
    p.add_argument("--light", action="store_true")
    p.add_argument("--lang", default=None)
    p.add_argument("--demo-data", action="store_true", help="neutral sample data (implied by --screenshot)")
    p.add_argument("--read-only", action="store_true", help="never change anything")
    p.add_argument("--search", default=None, help="(screenshot) text typed in the search box")
    p.add_argument("--expand", default=None, help="(screenshot) comma separated row keys to expand")
    p.add_argument("--select", default=None, help="(screenshot) row key to select")
    p.add_argument("--timing", action="store_true", help="print startup timing")
    p.add_argument("--real-data", action="store_true", help="(screenshot) use real /proc data, for testing only")
    # gnome-system-monitor compatible tab options (Fenestra's wrapper forwards them)
    p.add_argument("-p", "--show-processes-tab", dest="gsm_p", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("-r", "--show-resources-tab", dest="gsm_r", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("-f", "--show-file-systems-tab", dest="gsm_f", action="store_true", help=argparse.SUPPRESS)
    o = p.parse_known_args(argv[1:])[0]
    if not o.page:
        o.page = "processes" if o.gsm_p else "performance" if (o.gsm_r or o.gsm_f) else None
    return o


class App(Gtk.Application):
    def __init__(self, opts):
        flags = Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        if opts.screenshot or os.environ.get("FENESTRA_TASKMGR_NON_UNIQUE"):
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=util.APP_ID, flags=flags)
        self.opts = opts
        self.win = None
        self.sampler = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        theme.init("dark" if self.opts.dark else "light" if self.opts.light else None)

    def do_command_line(self, cmdline):
        if self.win is not None:
            o = parse_args(cmdline.get_arguments())
            if o.page:
                self.win.navigate(PAGE_ALIASES.get(o.page, o.page))
            self.win.present()
            return 0
        self._create()
        return 0

    def _create(self):
        from .window import TaskWindow
        o = self.opts
        if util.DEMO:
            from .demo import DemoCollector
            collector = DemoCollector()
        else:
            from .procdata import Collector
            collector = Collector()
        page = PAGE_ALIASES.get(o.page, o.page) if o.page else util.opts()["start_page"]
        expanded = True if o.expanded else False if (o.collapsed or o.screenshot) else None
        if o.perf:
            TaskWindow.perf_start = PERF_ALIASES.get(o.perf, o.perf)
        self.win = TaskWindow(self, collector, page, expanded)
        if o.size:
            try:
                w, h = (int(x) for x in o.size.lower().split("x"))
                self.win.set_default_size(w, h)
                if o.screenshot:
                    self.win.set_resizable(False)  # keep mutter from auto-maximising
            except ValueError:
                pass
        if o.maximized:
            self.win.add_css_class("maximized-look")
        self.win.connect("close-request", self._on_close)
        self.win.present()
        if o.timing:
            clock = self.win.get_frame_clock()

            def first_frame(c):
                print(f"first frame after {(time.monotonic() - T0) * 1000:.0f} ms (epoch {time.time():.3f})",
                      flush=True)
                c.disconnect(self._ff)
                if os.environ.get("FENESTRA_TASKMGR_EXIT_AFTER_FIRST_FRAME"):
                    GLib.timeout_add(300, lambda: (self.quit(), False)[1])
            if clock:
                self._ff = clock.connect("after-paint", first_frame)
            GLib.idle_add(lambda: (print(f"mapped after {(time.monotonic() - T0) * 1000:.0f} ms",
                                         flush=True), False)[1])
        if o.screenshot:
            snap = collector.sample()
            if o.real_data:
                time.sleep(0.5)
                snap = collector.sample()
            self.win.on_snapshot(snap)
            if o.search:
                self.win.search.set_text(o.search)
            if o.expand or o.select:
                pg = self.win.current
                if hasattr(pg, "table"):
                    for k in (o.expand or "").split(","):
                        if k:
                            pg.table.expanded.add(k)
                    if o.select:
                        pg.table.select(o.select)
                        pg.table.header_focus = False
                    pg.refresh() if hasattr(pg, "refresh") else None
            GLib.timeout_add(int(os.environ.get("FENESTRA_SHOT_DELAY", "900")), self._shoot)
        else:
            from .sampler import Sampler
            speed = util.SPEEDS.get(util.opts()["speed"], 1.0)
            self.sampler = Sampler(collector, self.win.on_snapshot, speed)
            # Start sampling once the first frame is out: the /proc walk would otherwise
            # compete with window construction for the GIL (matters when the system is
            # saturated, which is exactly when Task Manager gets opened).
            started = []

            def start(*_a):
                if not started:
                    started.append(1)
                    self.sampler.start()
                return False
            clock = self.win.get_frame_clock()
            if clock is not None:
                hid = []
                hid.append(clock.connect("after-paint", lambda c: (c.disconnect(hid[0]), GLib.idle_add(start))))
            GLib.timeout_add(400, start)  # safety net
            cycle = os.environ.get("FENESTRA_TASKMGR_SOAK_CYCLE")
            if cycle:  # test hook: keep switching pages/devices (navigation only, no actions)
                self._soak_i = 0
                GLib.timeout_add(int(float(cycle) * 1000), self._soak_step)

    def _soak_step(self):
        steps = ["processes", "performance:cpu", "performance:mem", "performance:disk0",
                 "performance:net0", "apphistory", "startup", "users", "details", "services", "settings"]
        page = steps[self._soak_i % len(steps)]
        self._soak_i += 1
        pid, _, dev = page.partition(":")
        self.win.navigate(pid)
        if dev and "performance" in self.win.pages:
            self.win.pages["performance"].select(dev)
        if pid == "processes" and self._soak_i % 3 == 0:
            t = self.win.pages["processes"].table
            t.expanded |= {r.key for r in t.rows if r.expandable}
            self.win.pages["processes"].refresh()
        return True

    def set_speed(self, name):
        util.opts().set("speed", name)
        if self.sampler:
            self.sampler.set_interval(util.SPEEDS.get(name, 1.0))

    def _on_close(self, *_):
        if self.sampler:
            self.sampler.stop()
        return False

    def _shoot(self):
        win = self.win
        w, h = win.get_width(), win.get_height()
        paintable = Gtk.WidgetPaintable.new(win)
        snap = Gtk.Snapshot()
        paintable.snapshot(snap, w, h)
        node = snap.to_node()
        if node is None:
            self._tries = getattr(self, "_tries", 0) + 1
            if self._tries < 20:
                return True
            print("screenshot failed", file=sys.stderr)
            self.quit()
            return False
        rect = Graphene.Rect().init(0, 0, w, h)
        tex = None
        for make in (Gsk.GLRenderer.new, Gsk.CairoRenderer.new):
            try:
                r = make()
                r.realize_for_display(win.get_display())
                tex = r.render_texture(node, rect)
                r.unrealize()
                break
            except GLib.Error:
                continue
        tex.save_to_png(self.opts.screenshot)
        print(f"saved {self.opts.screenshot} ({w}x{h})")
        self.quit()
        return False


def main(argv=None):
    argv = argv or sys.argv
    opts = parse_args(argv)
    i18n.init(opts.lang)
    if (opts.screenshot and not opts.real_data) or opts.demo_data or os.environ.get("FENESTRA_TASKMGR_DEMO"):
        util.DEMO = True
    if util.DEMO or opts.read_only or opts.screenshot:
        util.READ_ONLY = True
    app = App(opts)
    return app.run(argv)

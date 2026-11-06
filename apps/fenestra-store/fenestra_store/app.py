"""Entry point, command line and screenshot mode."""
from __future__ import annotations

import argparse
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gio, GLib, Graphene, Gsk, Gtk  # noqa: E402

from . import i18n, theme, util  # noqa: E402

PAGES = ["home", "apps", "games", "library", "updates", "search", "sources", "category", "app"]
PAGE_ALIASES = {"installed": "library", "update": "updates", "settings": "sources", "repos": "sources",
                "overview": "home", "explore": "home", "details": "app"}


def parse_args(argv):
    p = argparse.ArgumentParser(prog="fenestra-store", description="Fenestra Store")
    p.add_argument("--page", default=None,
                   help="home, apps, games, library, updates, sources, category:KEY, search:TEXT or app:ID")
    p.add_argument("--app", default=None, help="open the page of this app (AppStream id, package name or name)")
    p.add_argument("--search", default=None, help="start with this text in the search box")
    p.add_argument("--screenshot", metavar="OUT.png", help="render the window to a PNG and quit (implies --demo-data)")
    p.add_argument("--size", default=None, help="window size WxH")
    p.add_argument("--dark", action="store_true", help="force dark mode (does not change the system)")
    p.add_argument("--light", action="store_true", help="force light mode (does not change the system)")
    p.add_argument("--lang", default=None, help="UI language (en, es); default: system locale")
    p.add_argument("--demo-data", action="store_true",
                   help="deterministic sample catalogue; operations are simulated (implied by --screenshot)")
    p.add_argument("--read-only", action="store_true", help="never install, remove or change sources")
    p.add_argument("--real-data", action="store_true",
                   help="(screenshot) use the real backends instead of demo data; implies --read-only. Testing only:"
                        " never publish such screenshots")
    p.add_argument("--list-backends", action="store_true", help="print the backends that would be used and exit")
    # GNOME Software compatible options, so a .desktop override / Settings link can point here later
    p.add_argument("--mode", default=None, help=argparse.SUPPRESS)          # updates | installed | overview
    p.add_argument("--details", default=None, help=argparse.SUPPRESS)       # app id
    p.add_argument("--search-text", dest="gs_search", default=None, help=argparse.SUPPRESS)
    o, rest = p.parse_known_args(argv[1:])
    for r in rest:  # appstream://ID or appstream:ID URIs (what GNOME Software is given by other apps)
        if r.startswith("appstream:") and not o.app:
            o.app = r.split(":", 1)[1].lstrip("/")
    if o.mode and not o.page:
        o.page = {"updates": "updates", "installed": "library", "updated": "library"}.get(o.mode, "home")
    if o.details and not o.app:
        o.app = o.details
    if o.gs_search and not o.search:
        o.search = o.gs_search
    return o


def start_target(o):
    """(page id, argument) from --page / --app / --search."""
    if o.app:
        return "app", o.app
    page = (o.page or "home").strip()
    pid, _sep, arg = page.partition(":")
    pid = PAGE_ALIASES.get(pid, pid)
    if pid == "search":
        o.search = o.search or arg
        return "home", None
    if pid not in PAGES:
        print(f"Unknown page '{page}'. Pages: {', '.join(PAGES)}", file=sys.stderr)
        return "home", None
    return pid, (arg or None)


class App(Gtk.Application):
    def __init__(self, opts):
        flags = Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        if opts.screenshot or util.DEMO:
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=util.APP_ID, flags=flags)
        self.opts = opts
        self.screenshot = opts.screenshot
        self.win = None
        self.store = None
        self.exit_code = 0

    def do_startup(self):
        Gtk.Application.do_startup(self)
        theme.init("dark" if self.opts.dark else "light" if self.opts.light else None)

    def do_command_line(self, cmdline):
        if self.win is not None:  # second launch: forward to the running window
            try:
                o = parse_args(cmdline.get_arguments())
            except SystemExit:
                o = None
            if o is not None:
                pid, arg = start_target(o)
                self.win.open_target(pid, arg)
                if o.search:
                    self.win.search_for(o.search)
            self.win.present()
            return 0
        self._create()
        return 0

    def _create(self):
        from .backends import choose
        from .store import Store
        from .window import StoreWindow
        o = self.opts
        self.store = Store(choose(util.DEMO))
        pid, arg = start_target(o)
        self.win = StoreWindow(self, self.store, pid, arg)
        if not o.size:
            self.win.preset_width(self.win.get_default_size()[0])
        if o.size:
            try:
                w, h = (int(x) for x in o.size.lower().split("x"))
                self.win.set_default_size(w, h)
                self.win.preset_width(w)
                if o.screenshot:
                    self.win.set_resizable(False)
            except ValueError:
                pass
        if self.screenshot:
            self.store.load(sync=True)   # the first frame must already show the page
        if o.search:
            self.win.search.set_text(o.search)
            if self.screenshot:
                self.win.search_for(o.search)
        self.win.present()
        if not self.screenshot:
            self.store.load()
        if not util.DEMO:
            self.store.connect("loaded", self._first_update_check)
        if self.screenshot:
            GLib.timeout_add(int(os.environ.get("FENESTRA_SHOT_DELAY", "1500")), self._shoot)

    def _first_update_check(self, store):
        if store.backends and not store.checking and not getattr(self, "_checked", False):
            self._checked = True
            GLib.timeout_add_seconds(2, lambda: (store.check_updates(), False)[1])

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
            print("screenshot failed: nothing rendered", file=sys.stderr)
            self.exit_code = 1
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
        if tex is None:
            tex = win.get_renderer().render_texture(node, rect)
        tex.save_to_png(self.screenshot)
        print(f"saved {self.screenshot} ({w}x{h})")
        self.quit()
        return False


def main(argv=None):
    argv = argv or sys.argv
    opts = parse_args(argv)
    i18n.init(opts.lang)
    if (opts.screenshot and not opts.real_data) or opts.demo_data or os.environ.get("FENESTRA_STORE_DEMO"):
        util.DEMO = True
    if opts.read_only or opts.real_data or os.environ.get("FENESTRA_STORE_READ_ONLY"):
        util.READ_ONLY = True
    if opts.list_backends:
        from .backends import choose
        for b in choose(util.DEMO):
            print(b.id, "-", b.label)
        return 0
    if os.geteuid() == 0 and not (util.DEMO or util.READ_ONLY):
        print("fenestra-store: do not run as root; installs ask for permission through polkit.", file=sys.stderr)
        return 1
    app = App(opts)
    rc = app.run(argv)
    return rc or app.exit_code

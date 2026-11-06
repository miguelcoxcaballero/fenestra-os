"""Application entry point and command line handling."""
from __future__ import annotations

import argparse
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import Gio, GLib, Graphene, Gsk, Gtk  # noqa: E402

from . import i18n, theme, util  # noqa: E402


# Friendly aliases (also covers gnome-control-center panel names).
ALIASES = {
    "bluetooth": "bt-devices", "devices": "devices", "network": "network", "wi-fi": "wifi",
    "wlan": "wifi", "sound": "sound", "audio": "sound", "power": "power", "battery": "power",
    "display": "display", "displays": "display", "notifications": "notifications",
    "background": "background", "wallpaper": "background", "appearance": "colors",
    "users": "accounts", "user-accounts": "accounts",
    "datetime": "datetime", "date-time": "datetime", "region": "language", "keyboard": "typing",
    "mouse": "mouse", "touchpad": "touchpad", "privacy": "privacy",
    "location": "location", "camera": "camera", "microphone": "microphone",
    "universal-access": "accessibility", "a11y": "accessibility", "applications": "apps",
    "default-apps": "defaultapps", "info-overview": "about", "info": "about", "system": "system",
    "updates": "update", "multitasking": "multitasking", "sharing": "fx-sharing",
    "search": "fx-search", "printers": "fx-hardware", "color": "fx-hardware", "wacom": "fx-hardware",
    "wwan": "network", "about": "about", "remote-desktop": "fx-sharing", "extensions": "fx-extensions",
    "shortcuts": "fx-shortcuts", "keyboard-shortcuts": "fx-shortcuts", "workspaces": "fx-workspaces",
    "online-accounts": "fx-online-accounts", "fenestra": "fenestra", "linux": "fenestra",
}


def resolve_page(page):
    from .pages.base import PAGES
    if not page:
        return None
    if page in PAGES:
        return page
    return ALIASES.get(page.lower())


def parse_args(argv):
    p = argparse.ArgumentParser(prog="fenestra-settings", description="Fenestra Settings")
    p.add_argument("--page", default=None, help="page id to open (e.g. display, about)")
    p.add_argument("--screenshot", metavar="OUT.png", help="render the window to a PNG and quit")
    p.add_argument("--dark", action="store_true", help="force dark mode (does not change system)")
    p.add_argument("--light", action="store_true", help="force light mode (does not change system)")
    p.add_argument("--size", default=None, help="window size WxH")
    p.add_argument("--lang", default=None, help="UI language (en, es)")
    p.add_argument("--read-only", action="store_true", help="never change system settings")
    p.add_argument("--demo-data", action="store_true",
                   help="show neutral sample data instead of the real user/device (implies --read-only;"
                        " implied by --screenshot)")
    p.add_argument("--search", default=None, help="(screenshot) type this into the search box")
    p.add_argument("--hello-demo", default=None,
                   help="(screenshot) show a Fenestra Hello wizard state: welcome, welcome-finger, face-1, face-2, "
                        "face-done, finger-1, finger-2, finger-edges, finger-done, error")
    p.add_argument("--resolve-page", default=None, metavar="NAME",
                   help="print the page id for a page id / GNOME panel name and exit (1 if unknown)")
    p.add_argument("--list-pages", action="store_true", help="print page ids and exit")
    p.add_argument("--export-search-index", action="store_true",
                   help="print the search index (pages and indexed rows, in the UI language) as JSON and exit;"
                        " Fenestra Shell's Search uses it")
    p.add_argument("page_pos", nargs="?", default=None, help=argparse.SUPPRESS)
    return p.parse_args(argv[1:])


class App(Gtk.Application):
    def __init__(self, opts):
        flags = Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        if opts.screenshot:
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=util.APP_ID, flags=flags)
        self.opts = opts
        self.screenshot = opts.screenshot
        self.win = None
        self.exit_code = 0

    def do_startup(self):
        Gtk.Application.do_startup(self)
        override = "dark" if self.opts.dark else "light" if self.opts.light else None
        theme.init(override)
        from . import pages  # noqa: F401  (registers pages)

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()
        try:
            o = parse_args(args)
            page = o.page or o.page_pos
        except SystemExit:
            page = None
        self._present(page)
        return 0

    def _present(self, page=None):
        from .window import SettingsWindow
        if page:
            resolved = resolve_page(page)
            if resolved is None:
                print(f"Unknown page '{page}'. Use --list-pages.", file=sys.stderr)
            page = resolved
        if self.win is None:
            self.win = SettingsWindow(self, page or "home", animate=not self.screenshot)
            if self.opts.size:
                try:
                    w, h = (int(x) for x in self.opts.size.lower().split("x"))
                    self.win.set_default_size(w, h)
                except ValueError:
                    pass
        elif page:
            self.win.navigate(page)
        self.win.present()
        if self.opts.hello_demo and util.DEMO:
            def show_hello():
                from .hello_wizard import HelloWizard
                st = self.opts.hello_demo
                kind = "face" if st.startswith(("face", "welcome")) and st != "welcome-finger" else "finger"
                self.win.show_dialog(HelloWizard(kind, demo_state=st))
                return False
            GLib.timeout_add(200, show_hello)
        if self.screenshot:
            if self.opts.search:
                GLib.timeout_add(300, lambda: (self.win.nav.entry.set_text(self.opts.search), False)[1])
            GLib.timeout_add(int(os.environ.get("FENESTRA_SHOT_DELAY", "1500")), self._shoot_first)

    def _shoot_first(self):
        GLib.timeout_add(250, self._shoot)
        return False

    def _shoot(self):
        win = self.win
        w, h = win.get_width(), win.get_height()
        paintable = Gtk.WidgetPaintable.new(win)
        snap = Gtk.Snapshot()
        paintable.snapshot(snap, w, h)
        # popovers are separate surfaces; render the search popover on top if open
        node = snap.to_node()
        if node is None:
            self._tries = getattr(self, "_tries", 0) + 1
            if self._tries < 20:
                return True  # window not drawn yet; try again
            print("screenshot failed: nothing rendered", file=sys.stderr)
            self.exit_code = 1
            self.quit()
            return False
        pop = win.nav.popover
        if pop.get_visible():
            ok, pt = win.nav.entry.compute_point(win, _pt(0, win.nav.entry.get_height() + 2))
            s2 = Gtk.Snapshot()
            s2.append_node(node)
            s2.translate(_pt(pt.x, pt.y))
            Gtk.WidgetPaintable.new(pop).snapshot(s2, pop.get_width(), pop.get_height())
            node = s2.to_node()
        rect = Graphene.Rect().init(0, 0, w, h)
        tex = None
        # The window's own (Vulkan) renderer may return an empty texture when
        # rendering off-screen; use a dedicated GL renderer, then Cairo.
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
        if os.environ.get("FENESTRA_SHOT_NODE"):
            node.write_to_file(os.environ["FENESTRA_SHOT_NODE"])
        print(f"saved {self.screenshot} ({w}x{h})")
        self.quit()
        return False


def _pt(x, y):
    p = Graphene.Point()
    p.x, p.y = x, y
    return p


def main(argv=None):
    argv = argv or sys.argv
    opts = parse_args(argv)
    i18n.init(opts.lang)
    if opts.resolve_page is not None:
        from . import pages  # noqa: F401
        pid = resolve_page(opts.resolve_page) if opts.resolve_page else "home"
        if pid:
            print(pid)
            return 0
        return 1
    if opts.list_pages:
        from . import pages  # noqa: F401
        from .pages.base import PAGES
        for pid, cls in PAGES.items():
            print(f"{pid:22} {cls.title}  (parent: {cls.parent or '-'})")
        return 0
    if opts.export_search_index:
        import json
        from . import pages  # noqa: F401
        from .search import build_index
        json.dump([{"page": e.page_id, "key": e.key, "title": e.title, "where": e.where, "icon": e.icon, "hay": e.hay}
                   for e in build_index()], sys.stdout, ensure_ascii=False)
        return 0
    if opts.screenshot or opts.demo_data or os.environ.get("FENESTRA_SETTINGS_DEMO"):
        util.DEMO = True
    if util.DEMO or opts.read_only or os.environ.get("FENESTRA_SETTINGS_READ_ONLY"):
        util.READ_ONLY = True
    app = App(opts)
    return app.run(argv)

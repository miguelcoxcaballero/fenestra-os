"""Command line entry point and Gtk.Application."""

import argparse
import logging
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, i18n, paths  # noqa: E402

log = logging.getLogger("fenestra-oobe")


def parse_args(argv):
    p = argparse.ArgumentParser(prog="fenestra-oobe", description="Fenestra first boot setup")
    p.add_argument("--existing-user", action="store_true",
                   help="first login of a new user (privacy, personalization, finale)")
    p.add_argument("--demo", action="store_true",
                   help="run the whole flow without changing the system")
    p.add_argument("--windowed", action="store_true", help="don't go full screen")
    p.add_argument("--page", help="start at this page id (debug/screenshots)")
    p.add_argument("--screenshot", metavar="OUT.png", help="render --page to a PNG and quit")
    p.add_argument("--size", default="1920x1080", help="window size for --screenshot/--windowed")
    p.add_argument("--lang", help="UI language (en, es)")
    p.add_argument("--country", help="override the guessed country code (debug/screenshots)")
    p.add_argument("--list-pages", action="store_true", help="print page ids and exit")
    p.add_argument("--debug", action="store_true")
    return p.parse_args(argv[1:])


def build_state(args):
    from .backends import locale as loc
    from .state import OobeState

    lang = i18n.language()
    lang_locale = loc.current_locale()
    base = lang_locale.split(".")[0]
    lang_locale = f"{base}.UTF-8" if "_" in base else "en_US.UTF-8"
    st = OobeState(ui_lang=lang, lang_locale=lang_locale)
    st.timezone = loc.current_timezone()
    st.country = (args.country or "").upper() or loc.guess_country(lang_locale, st.timezone)
    st.formats = loc.formats_for_country(st.country, loc.language_of(lang_locale))
    st.layouts = [loc.keyboard_for_country(st.country)]
    if args.screenshot:
        st.full_name, st.username, st.password = "Alex Rivera", "alex", "demo-password"
    return st


class OobeApp(Gtk.Application):
    def __init__(self, args):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.args = args
        self.window = None
        self.exit_code = 0

    def do_startup(self):
        Gtk.Application.do_startup(self)
        settings = Gtk.Settings.get_default()
        settings.props.gtk_application_prefer_dark_theme = False
        # GTK >= 4.20 follows the desktop color scheme; the OOBE is always light.
        if hasattr(Gtk, "InterfaceColorScheme"):
            try:
                settings.set_property("gtk-interface-color-scheme", Gtk.InterfaceColorScheme.LIGHT)
            except TypeError:
                pass
        # Symbolic icons must be predictable whatever theme the session uses.
        settings.props.gtk_icon_theme_name = os.environ.get("FENESTRA_OOBE_ICON_THEME", "Adwaita")
        provider = Gtk.CssProvider()
        provider.load_from_path(paths.data_file("style.css"))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def do_activate(self):
        from .backends import Backends
        from .window import OobeWindow

        args = self.args
        demo = args.demo or bool(args.screenshot)
        mode = "demo" if demo and not args.existing_user else ("existing" if args.existing_user else "system")
        if demo and args.existing_user:
            mode = "demo"
        state = build_state(args)
        backends = Backends(demo)
        win = OobeWindow(self, mode, state, backends, screenshot=bool(args.screenshot))
        self.window = win
        w, h = (int(x) for x in args.size.lower().split("x"))
        if args.screenshot or args.windowed:
            win.set_default_size(w, h)
            win.set_decorated(not args.screenshot)
            if args.screenshot:
                # mutter auto-maximizes very large windows; a fixed size avoids it
                win.set_resizable(False)
        else:
            win.fullscreen()
        start = args.page
        if start is None and demo and args.existing_user:
            start = "privacy"
        win.start(start)
        win.present()
        if args.screenshot:
            GLib.timeout_add(1300, self._take_screenshot)

    def _take_screenshot(self):
        try:
            if self.args.page and self.args.page.startswith("finale"):
                pass
            elif self.args.page == "network":
                page = self.window.current_page
                row = page.listbox.get_row_at_index(0)
                if row is not None:
                    page.listbox.select_row(row)
                GLib.timeout_add(500, self._really_capture)
                return False
            self._really_capture()
        except Exception as exc:  # noqa: BLE001
            log.error("screenshot failed: %s", exc)
            self.exit_code = 1
            self.quit()
        return False

    def _really_capture(self):
        win = self.window
        for orient in (0, 1):
            log.debug("root measure %s: %s", orient, win.get_child().measure(orient, -1))
        w, h = self.window.capture(self.args.screenshot)
        print(f"wrote {self.args.screenshot} ({w}x{h})")
        self.quit()
        return False


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="fenestra-oobe: %(levelname)s: %(message)s")
    if args.list_pages:
        from .window import ALL_PAGE_IDS
        print("\n".join(ALL_PAGE_IDS))
        return 0
    i18n.set_language(args.lang or i18n.detect_language())
    if args.screenshot:
        # Read-back of offscreen textures is unreliable with some Vulkan
        # drivers; the GL renderer is fine for one-off screenshots.
        os.environ.setdefault("GSK_RENDERER", "gl")
    if args.page and args.screenshot is None and not args.demo:
        log.info("--page without --demo: changes will be applied for real")
    app = OobeApp(args)
    rc = app.run([argv[0]])
    return app.exit_code or rc


if __name__ == "__main__":
    sys.exit(main())

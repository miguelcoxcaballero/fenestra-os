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


def parse_args(argv):
    p = argparse.ArgumentParser(prog="fenestra-paint", description="Fenestra Paint")
    p.add_argument("files", nargs="*", help="images to open")
    p.add_argument("--screenshot", metavar="OUT.png", help="render the window to a PNG and quit")
    p.add_argument("--size", default=None, help="window size WxH")
    p.add_argument("--maximized", action="store_true", help="draw as maximised (square corners)")
    p.add_argument("--dark", action="store_true")
    p.add_argument("--light", action="store_true")
    p.add_argument("--lang", default=None)
    p.add_argument("--menu", default=None, help="(screenshot) open a menu: file, edit, view, view-zoom, "
                   "selection, rotate, flip, brushes, outline, fill, file-saveas")
    p.add_argument("--layers", action="store_true", help="(screenshot) show the layers panel")
    p.add_argument("--settings", action="store_true", help="(screenshot) show the settings page")
    p.add_argument("--dialog", default=None, help="(screenshot) resize, properties, unsaved, rotate")
    p.add_argument("--demo", action="store_true", help="(screenshot) draw a demo picture")
    p.add_argument("--text", action="store_true", help="(screenshot) leave a text box open")
    p.add_argument("--select", action="store_true", help="(screenshot) leave a moved selection")
    p.add_argument("--zoom", type=float, default=None, help="(screenshot) zoom factor")
    return p.parse_known_args(argv[1:])[0]


class App(Gtk.Application):
    def __init__(self, opts):
        flags = Gio.ApplicationFlags.HANDLES_OPEN
        if opts.screenshot or os.environ.get("FENESTRA_PAINT_NON_UNIQUE"):
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=util.APP_ID, flags=flags)
        self.opts = opts
        self.windows = []

    def do_startup(self):
        Gtk.Application.do_startup(self)
        theme.init("dark" if self.opts.dark else "light" if self.opts.light else None)
        Gtk.Window.set_default_icon_name(util.APP_ID)

    def do_activate(self):
        self.new_window()

    def do_open(self, files, n, hint):
        for f in files:
            p = f.get_path()
            self.new_window(p)

    def new_window(self, path=None):
        from .window import PaintWindow
        o = self.opts
        win = PaintWindow(self, path)
        self.windows.append(win)
        if o.size:
            try:
                w, h = (int(x) for x in o.size.lower().split("x"))
                win.set_default_size(w, h)
                if o.screenshot:
                    win.set_resizable(False)
            except ValueError:
                pass
        if o.maximized:
            win.add_css_class("maximized")
        win.present()
        if o.screenshot:
            GLib.timeout_add(400, lambda: (self._prepare(win), False)[1])
        return win

    # ------------------------------------------------------------------ screenshots
    def _prepare(self, win):
        o = self.opts
        if o.zoom:
            win.canvas.set_zoom(o.zoom)
        else:
            win.canvas.set_zoom(min(1.0, win.canvas.fit_zoom()))
        if o.demo:
            from .demo import draw_demo
            draw_demo(win)
        if o.layers:
            win.toggle_layers()
        if o.settings:
            win.open_settings()
        if o.text:
            from .demo import open_text
            open_text(win)
        if o.select:
            from .demo import open_selection
            open_selection(win)
        GLib.timeout_add(250, lambda: (self._prepare2(win), False)[1])

    def _prepare2(self, win):
        o = self.opts
        if o.dialog:
            from . import dialogs
            d = o.dialog
            if d == "resize":
                win.resize_dialog()
            elif d == "properties":
                win.properties_dialog()
            elif d == "unsaved":
                dialogs.unsaved(win, lambda: None, lambda: None)
            elif d == "rotate":
                win.rotate_custom_dialog()
        if o.menu:
            m = o.menu
            if m in ("file", "edit", "view", "view-zoom", "file-saveas"):
                win.open_menu(m.split("-")[0])
                if m in ("view-zoom", "file-saveas"):
                    GLib.timeout_add(150, lambda: (self._open_sub(win, 0), False)[1])
            elif m == "selection":
                win.selection_menu(win.ribbon.sel_drop)
            elif m == "rotate":
                win.rotate_menu(win.ribbon.rot_drop)
            elif m == "flip":
                win.flip_menu(win.ribbon.flip_drop)
            elif m == "brushes":
                win.brushes_menu(win.ribbon.brush_drop)
            elif m == "outline":
                win.set_tool("shape")
                win.outline_menu(win.ribbon.outline_btn)
            elif m == "fill":
                win.set_tool("shape")
                win.fill_menu(win.ribbon.fill_btn)
        GLib.timeout_add(int(os.environ.get("FENESTRA_SHOT_DELAY", "700")), lambda: self._shoot(win))

    def _open_sub(self, win, _level):
        fl = win.flyouts
        if not fl.items:
            return
        menu = fl.items[0][0]
        target = "Zoom" if self.opts.menu == "view-zoom" else "Save as"
        from .i18n import _
        child = menu.get_first_child()
        while child is not None:
            lab = child.get_child()
            texts = []
            if lab is not None:
                c = lab.get_first_child()
                while c is not None:
                    if isinstance(c, Gtk.Label):
                        texts.append(c.get_text())
                    c = c.get_next_sibling()
            if _(target) in texts:
                child.emit("clicked")
                break
            child = child.get_next_sibling()

    def _shoot(self, win):
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
        win._closing = True
        self.quit()
        return False


def main(argv=None):
    argv = argv or sys.argv
    opts = parse_args(argv)
    i18n.init(opts.lang)
    if opts.screenshot:
        util.EPHEMERAL = True
        os.environ["FENESTRA_PAINT_DEFAULT_ACCENT"] = "1"
    app = App(opts)
    # GApplication must not see our options
    return app.run([argv[0]] + [os.path.abspath(f) for f in opts.files])



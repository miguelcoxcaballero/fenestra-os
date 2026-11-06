"""Entry point: single-instance application, command line, session handling, screenshots."""
from __future__ import annotations

import argparse
import os
import signal
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("GtkSource", "5")
gi.require_version("Pango", "1.0")

from gi.repository import Gio, GLib, Graphene, Gsk, Gtk, GtkSource  # noqa: E402

from . import i18n, session, theme, util  # noqa: E402

DEMO_TEXT = "Hello from Fenestra. This is a sample line of text.\nSecond line 1234567890"
DEMO_MD = ("# Fenestra Notepad\n\nNotepad keeps **plain text** plain, and gives *Markdown* files a "
           "formatting toolbar.\n\n- Tabs and sessions\n- Find and replace\n- ~~Nothing to install~~\n\n"
           "[Project website](https://github.com/miguelcoxcaballero/fenestra-os)\n")


def parse_args(argv):
    p = argparse.ArgumentParser(prog="fenestra-notepad", description="Fenestra Notepad")
    p.add_argument("files", nargs="*", help="files to open (as tabs of the running window)")
    p.add_argument("--new-window", action="store_true", help="open the files in a new window")
    p.add_argument("--screenshot", metavar="OUT.png", help="render the window to a PNG and quit")
    p.add_argument("--size", default="1428x746", help="window size WxH (screenshot mode)")
    p.add_argument("--shot", default="main", help="screenshot state: main, menu-file, menu-edit, menu-view, "
                   "menu-recent, menu-zoom, context, find, replace, settings, settings-font, goto, save, markdown, "
                   "tabs, dialog-error")
    p.add_argument("--dark", action="store_true")
    p.add_argument("--light", action="store_true")
    p.add_argument("--lang", default=None)
    p.add_argument("--demo", action="store_true", help="never read or write settings and session")
    o, _rest = p.parse_known_args(argv[1:])
    return o


class App(Gtk.Application):
    def __init__(self, opts):
        flags = Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        if opts.screenshot or os.environ.get("FENESTRA_NOTEPAD_NON_UNIQUE"):
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=util.APP_ID, flags=flags)
        self.opts = opts
        self.windows = []
        self.last_active = None
        self._save_id = 0
        self.started = False

    # ------------------------------------------------------------------ lifecycle
    def do_startup(self):
        Gtk.Application.do_startup(self)
        GtkSource.init()
        Gtk.Window.set_default_icon_name(util.APP_ID)
        theme.init("dark" if self.opts.dark else "light" if self.opts.light else None)
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self._on_signal)

    def _on_signal(self):
        self.save_session_now()
        for w in list(self.windows):
            w.closing = True
            w.destroy()
        self.quit()
        return False

    def do_shutdown(self):
        if self.windows:
            self.save_session_now()
        Gtk.Application.do_shutdown(self)

    def do_command_line(self, cmdline):
        o = parse_args(cmdline.get_arguments())
        cwd = cmdline.get_cwd() or os.getcwd()
        paths = [p if os.path.isabs(p) else os.path.join(cwd, p) for p in o.files]
        paths = [Gio.File.new_for_commandline_arg_and_cwd(p, cwd).get_path() or p for p in paths]
        if not self.started:
            self.started = True
            if self.opts.screenshot:
                self._screenshot_setup()
                return 0
            restored = False
            if util.settings()["startup"] == "continue" and not util.DEMO:
                restored = self.restore_session()
            elif not util.DEMO:
                session.clear()
            if not restored:
                w = self.create_window()
                if not paths:
                    w.new_tab()
            win = self.windows[-1] if self.windows else self.create_window()
            if paths:
                win.open_paths(paths)
            for w in self.windows:
                w.present()
            return 0
        # a second launch forwarded its command line
        if paths and (o.new_window or util.settings()["open_in"] == "window"):
            w = self.create_window()
            w.open_paths(paths)
            w.present()
        elif o.new_window:
            self.new_window()
        else:
            w = self.active_window()
            if w is None:
                w = self.create_window()
                if not paths:
                    w.new_tab()
            if paths:
                w.open_paths(paths)
            w.present()
        return 0

    def active_window(self):
        w = self.get_active_window()
        if w in self.windows and not w.closing:
            return w
        if self.last_active in self.windows and not self.last_active.closing:
            return self.last_active
        alive = [w for w in self.windows if not w.closing]
        return alive[-1] if alive else None

    def create_window(self):
        from .window import NotepadWindow
        w = NotepadWindow(self)
        self.windows.append(w)
        self.last_active = w
        if util.settings()["window_max"] and not self.opts.screenshot:
            w.maximize()
        return w

    def new_window(self):
        w = self.create_window()
        w.new_tab()
        w.present()
        return w

    def window_closed(self, win, save_session):
        if save_session:
            self.save_session_now()
        if win in self.windows:
            self.windows.remove(win)
        if self.last_active is win:
            self.last_active = None
        if not self.windows:
            if util.settings()["startup"] != "continue" and not util.DEMO:
                session.clear()
            elif not save_session and not util.DEMO:
                # the last window went away through prompts or its last tab: nothing to restore
                session.save([])
        elif not util.DEMO:
            self.schedule_session_save()

    def exit(self):
        """File > Exit: close every window (prompting only when sessions are off)."""
        s = util.settings()
        if s["startup"] == "continue" and not util.DEMO:
            self.save_session_now()
            for w in list(self.windows):
                w._remember_size()
                w.closing = True
                self.windows.remove(w)
                w.destroy()
            self.quit()
            return
        wins = list(self.windows)

        def step():
            if not wins:
                self.quit()
                return
            w = wins.pop(0)
            w.present()
            w.close_with_prompts(lambda: (w._finish_close(), step()))
        step()

    # ------------------------------------------------------------------ session
    def schedule_session_save(self):
        if util.DEMO or util.settings()["startup"] != "continue":
            return
        if self._save_id:
            GLib.source_remove(self._save_id)
        # big unsaved documents are written less often (each save copies the whole text)
        big = any(d.session_dirty and d.buffer.get_char_count() > 2_000_000
                  for w in self.windows for d in w.documents())
        self._save_id = GLib.timeout_add(8000 if big else 1500, self._save_timeout)

    def _save_timeout(self):
        self._save_id = 0
        self.save_session_now()
        return False

    def save_session_now(self):
        if self._save_id:
            GLib.source_remove(self._save_id)
            self._save_id = 0
        if util.DEMO or util.settings()["startup"] != "continue":
            return
        wins = [w for w in self.windows if w.pages]
        session.save(wins)

    def restore_session(self):
        from .document import Document
        data = session.load()
        if not data:
            return False
        for wd in data:
            w = self.create_window()
            try:
                w.set_default_size(int(wd.get("width", 1000)), int(wd.get("height", 640)))
            except (TypeError, ValueError):
                pass
            if wd.get("maximized"):
                w.maximize()
            for t in wd["tabs"]:
                doc = Document(markdown=bool(t.get("markdown")), uid=t.get("uid"))
                z = t.get("zoom", 100)
                doc.zoom = z if z in theme.ZOOM_LEVELS else 100
                path = t.get("path")
                if "text" in t:
                    doc.path = path
                    from . import textio
                    doc.encoding = t.get("encoding") if t.get("encoding") in textio.ENCODINGS else "utf-8"
                    doc.eol = t.get("eol") if t.get("eol") in textio.EOLS else "lf"
                    doc.bom = t.get("bom")
                    w.add_document(doc, activate=False)
                    doc.fill(t["text"], modified=bool(t.get("modified")) or path is None,
                             cursor=t.get("cursor"))
                elif path:
                    w.add_document(doc, activate=False)
                    doc.load(path)
                else:
                    w.add_document(doc, activate=False)
            docs = w.documents()
            if not docs:
                w.new_tab()
            else:
                w.set_current(docs[max(0, min(int(wd.get("active", 0)), len(docs) - 1))])
        return bool(self.windows)

    # ------------------------------------------------------------------ screenshots
    def _screenshot_setup(self):
        from .document import Document
        o = self.opts
        w = self.create_window()
        try:
            ww, hh = (int(x) for x in o.size.lower().split("x"))
        except ValueError:
            ww, hh = 1428, 746
        w.set_default_size(ww, hh)
        w.set_resizable(False)
        shot = o.shot
        if shot in ("markdown",):
            d = Document(markdown=True)
            w.add_document(d)
            d.fill(DEMO_MD)
            d.path = "/home/user/Documents/Notes.md"
            d.buffer.set_modified(False)
            d.emit("changed-meta")
        else:
            d = Document()
            w.add_document(d)
            d.fill(DEMO_TEXT, modified=True)
            d.encoding, d.eol = "utf-8", "crlf"
        if shot == "tabs":
            for name, text in (("todo.txt", "Buy milk\n"), ("notes.md", "# Notes\n")):
                e = Document(markdown=name.endswith(".md"))
                w.add_document(e, activate=False)
                e.fill(text)
                e.path = "/home/user/Documents/" + name
                e.emit("changed-meta")
        w.present()
        GLib.timeout_add(300, self._shot_state, w, d, shot)

    def _shot_state(self, w, d, shot):
        buf = d.buffer
        end = buf.get_end_iter()
        buf.place_cursor(end)
        w._update_status()
        delay = 500
        if shot == "menu-file":
            w.menu_buttons["file"].emit("clicked")
        elif shot == "menu-recent":
            util.settings()["recent"] = ["/home/user/Documents/todo.txt", "/home/user/Documents/Notes.md",
                                         "/home/user/Projects/readme.txt"]
            m = w._open_menu(w.menu_buttons["file"], w._build_file_menu)
            GLib.timeout_add(250, lambda: (m.open_submenu(self._find_item(m, "Recent")), False)[1])
            delay = 900
        elif shot == "menu-edit":
            w.menu_buttons["edit"].emit("clicked")
        elif shot == "menu-view":
            w.menu_buttons["view"].emit("clicked")
        elif shot == "menu-zoom":
            m = w._open_menu(w.menu_buttons["view"], w._build_view_menu)
            GLib.timeout_add(250, lambda: (m.open_submenu(self._find_item(m, "Zoom")), False)[1])
            delay = 900
        elif shot == "context":
            it = buf.get_iter_at_line_offset(0, 41)[1] if isinstance(buf.get_iter_at_line_offset(0, 41), tuple) \
                else buf.get_iter_at_line_offset(0, 41)
            buf.place_cursor(it)
            w._update_status()
            w._context_menu(w.current.view, 400, 18)
        elif shot in ("find", "replace"):
            it = buf.get_iter_at_line_offset(0, 41)
            it = it[1] if isinstance(it, tuple) else it
            buf.place_cursor(it)
            w.show_find(shot == "replace")
        elif shot == "settings":
            w.open_settings()
        elif shot == "settings-font":
            w.open_settings()
            w.settings_page.show_font()
            w.settings_page.theme_exp.set_expanded(True, animate=False)
        elif shot == "goto":
            w.goto_dialog()
        elif shot == "save":
            w.ask_save(d, lambda: None)
        elif shot == "markdown":
            it = buf.get_iter_at_line(0)
            buf.place_cursor(it[1] if isinstance(it, tuple) else it)
            w._update_toolbar()
        GLib.timeout_add(int(os.environ.get("FENESTRA_SHOT_DELAY", str(delay))), self._shoot, w)
        return False

    @staticmethod
    def _find_item(menu, text):
        from .i18n import _
        want = _(text)
        c = menu.box.get_first_child()
        while c is not None:
            lbls = []
            stack = [c]
            while stack:
                x = stack.pop()
                if isinstance(x, Gtk.Label):
                    lbls.append(x.get_label())
                ch = x.get_first_child()
                while ch is not None:
                    stack.append(ch)
                    ch = ch.get_next_sibling()
            if want in lbls:
                return c
            c = c.get_next_sibling()
        return None

    def _popovers(self, widget, out):
        c = widget.get_first_child()
        while c is not None:
            if isinstance(c, Gtk.Popover) and c.get_visible():
                out.append(c)
            self._popovers(c, out)
            c = c.get_next_sibling()
        return out

    def _shoot(self, win):
        w, h = win.get_width(), win.get_height()
        snap = Gtk.Snapshot()
        Gtk.WidgetPaintable.new(win).snapshot(snap, w, h)
        wx, wy = win.get_surface_transform()
        for pop in self._popovers(win, []):
            surf = pop.get_surface()
            if surf is None:
                continue
            # popup position is relative to its parent surface; walk up to the window
            x, y = surf.get_position_x(), surf.get_position_y()
            parent = surf.get_parent()
            while parent is not None and parent is not win.get_surface():
                x += parent.get_position_x()
                y += parent.get_position_y()
                parent = parent.get_parent() if hasattr(parent, "get_parent") else None
            px, py = pop.get_surface_transform()
            # parent popups' own shadow offsets are included in their positions
            ox, oy = x + px - wx, y + py - wy
            snap.save()
            pt = Graphene.Point()
            pt.x, pt.y = ox, oy
            snap.translate(pt)
            Gtk.WidgetPaintable.new(pop).snapshot(snap, pop.get_width(), pop.get_height())
            snap.restore()
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
        for x in list(self.windows):
            x.closing = True
            x.destroy()
        self.quit()
        return False


def main(argv=None):
    argv = argv or sys.argv
    opts = parse_args(argv)
    i18n.init(opts.lang)
    if opts.screenshot or opts.demo or os.environ.get("FENESTRA_NOTEPAD_DEMO"):
        util.DEMO = True
    app = App(opts)
    return app.run(argv)

"""Notepad main window: tab strip, menu bar + formatting toolbar, editor, status bar."""
from __future__ import annotations

import os
import time

import gi

gi.require_version("GtkSource", "5")
from gi.repository import Gdk, Gio, GLib, Gtk, GtkSource, Pango  # noqa: E402

from . import markdown, printing, textio, theme, util  # noqa: E402
from .document import Document  # noqa: E402
from .findbar import FindCard  # noqa: E402
from .i18n import _  # noqa: E402
from .settings_page import SettingsPage  # noqa: E402
from .tabbar import TabStrip  # noqa: E402
from .widgets import ContentDialog, Menu, flat_button, icon, label, menu_shortcut  # noqa: E402

ZOOM_STEPS = theme.ZOOM_LEVELS
SMALL_FILE = 4 * 1024 * 1024


class Page:
    """Per-tab view state: the document, its scrolled source view."""

    def __init__(self, doc, view, scroller):
        self.doc, self.view, self.scroller = doc, view, scroller


class NotepadWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "FenestraNotepadWindow"

    def __init__(self, app):
        super().__init__(application=app)
        self.app = app
        self.pages: list[Page] = []
        self.current: Page | None = None
        self.dialog = None
        self.closing = False
        s = util.settings()
        self.add_css_class("notepad")
        self.set_icon_name(util.APP_ID)
        self.set_default_size(s["window_w"], s["window_h"])
        self.set_size_request(360, 240)

        # ------------------------------------------------------------ title bar
        handle = Gtk.WindowHandle()
        self.title_stack = Gtk.Stack()
        self.title_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        bar = Gtk.Box()
        bar.add_css_class("titlebar-row")
        bar.append(icon(util.APP_ID, 16, "title-icon color-icon"))
        self.strip = TabStrip(self._select_doc, self.close_tab, self.new_tab)
        bar.append(self.strip)
        bar.append(Gtk.Box(hexpand=True))
        self.title_stack.add_named(bar, "tabs")
        sbar = Gtk.Box()
        sbar.add_css_class("titlebar-row")
        sbar.add_css_class("settings-titlebar")
        back = flat_button("np-arrow-left-symbolic", "title-back", _("Back"), self.close_settings)
        back.set_valign(Gtk.Align.START)
        sbar.append(back)
        ic2 = icon(util.APP_ID, 16, "title-icon2 color-icon")
        ic2.set_valign(Gtk.Align.START)
        sbar.append(ic2)
        sbar.append(label(_("Notepad"), "title-label"))
        sbar.append(Gtk.Box(hexpand=True))
        self.title_stack.add_named(sbar, "settings")
        outer = Gtk.Box()
        outer.append(self.title_stack)
        self.title_stack.set_hexpand(True)
        outer.append(self._caption_buttons())
        handle.set_child(outer)
        self.set_titlebar(handle)

        # ------------------------------------------------------------ body
        self.overlay = Gtk.Overlay()
        self.set_child(self.overlay)
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.overlay.set_child(self.main_stack)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.add_css_class("body")
        self.main_stack.add_named(body, "editor")
        body.append(self._menubar())
        self.editor_overlay = Gtk.Overlay()
        self.editor_overlay.set_vexpand(True)
        self.editor_stack = Gtk.Stack()
        self.editor_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.editor_stack.add_css_class("editor-stack")
        self.editor_overlay.set_child(self.editor_stack)
        self.find = FindCard(self)
        self.editor_overlay.add_overlay(self.find)
        body.append(self.editor_overlay)
        body.append(self._statusbar())
        self.settings_page = None

        self.smoke = Gtk.Box()
        self.smoke.add_css_class("smoke")
        self.smoke.set_visible(False)
        self.overlay.add_overlay(self.smoke)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

        s.listeners.append(self._on_setting)
        theme.get().listeners.append(self._on_theme)
        self.connect("close-request", self._on_close_request)
        self.connect("notify::default-width", self._on_resize)
        self.connect("notify::maximized", lambda *_: self._caps_redraw())
        self.connect("notify::is-active", lambda *_: self._on_active())
        self._apply_font()
        self._on_theme()
        self._on_resize()

    # ================================================================= chrome
    def _caption_buttons(self):
        caps = Gtk.Box()
        caps.add_css_class("caption-buttons")
        caps.set_valign(Gtk.Align.START)
        self._caps = []
        for name, cb, tip in (("minimize", lambda *_: self.minimize(), _("Minimize")),
                              ("maximize", lambda *_: self.unmaximize() if self.is_maximized() else self.maximize(),
                               _("Maximize")),
                              ("close", lambda *_: self.close(), _("Close"))):
            b = Gtk.Button()
            b.add_css_class("caption")
            b.add_css_class(name)
            b.set_focus_on_click(False)
            b.set_tooltip_text(tip)
            area = Gtk.DrawingArea()
            area.set_draw_func(self._draw_caption, name)
            b.set_child(area)
            b.connect("clicked", cb)
            caps.append(b)
            self._caps.append(area)
        return caps

    def _caps_redraw(self):
        for a in self._caps:
            a.queue_draw()

    def _draw_caption(self, area, cr, w, h, name):
        btn = area.get_parent()
        c = theme.get().c["fg"]
        if name == "close" and btn is not None and btn.get_state_flags() & Gtk.StateFlags.PRELIGHT:
            c = Gdk.RGBA()
            c.parse("#ffffff")
        cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
        cr.set_line_width(1.0)
        cx, cy = int(w / 2) - 1, int(h / 2)     # glyph boxes measured on the reference: x 16..25
        if name == "minimize":
            cr.rectangle(cx - 5, cy, 10, 1)
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
            # 10x10 px cross at x 17..26, y 9..18 (anti-aliased, no overshoot)
            cr.move_to(cx - 3.5, cy - 4.5)
            cr.line_to(cx + 5.5, cy + 4.5)
            cr.move_to(cx + 5.5, cy - 4.5)
            cr.line_to(cx - 3.5, cy + 4.5)
            cr.stroke()

    def _menubar(self):
        bar = Gtk.CenterBox()
        bar.add_css_class("menubar")
        left = Gtk.Box()
        left.add_css_class("menubar-items")
        self.menu_buttons = {}
        for key, text, build in (("file", _("File"), self._build_file_menu),
                                 ("edit", _("Edit"), self._build_edit_menu),
                                 ("view", _("View"), self._build_view_menu)):
            b = Gtk.Button(label=text)
            b.add_css_class("menubar-item")
            b.set_focus_on_click(False)
            b.connect("clicked", lambda btn, build=build: self._open_menu(btn, build))
            left.append(b)
            self.menu_buttons[key] = b
        bar.set_start_widget(left)
        self.toolbar = self._format_toolbar()
        bar.set_center_widget(self.toolbar)
        right = Gtk.Box()
        right.add_css_class("menubar-right")
        gear = flat_button("np-settings-symbolic", "tool-btn", _("Settings"), self.open_settings)
        right.append(gear)
        bar.set_end_widget(right)
        self.menubar = bar
        return bar

    def _format_toolbar(self):
        tb = Gtk.Box()
        tb.add_css_class("format-toolbar")
        self.fmt_heading = Gtk.Button()
        self.fmt_heading.add_css_class("tool-btn")
        self.fmt_heading.add_css_class("tool-drop")
        hb = Gtk.Box()
        self.heading_label = label("H1", "tool-text")
        hb.append(self.heading_label)
        hb.append(icon("np-chevron-down-symbolic", 12, "tool-chevron"))
        self.fmt_heading.set_child(hb)
        self.fmt_heading.set_tooltip_text(_("Heading"))
        self.fmt_heading.set_focus_on_click(False)
        self.fmt_heading.connect("clicked", lambda b: self._open_menu(b, self._build_heading_menu))
        tb.append(self.fmt_heading)

        self.fmt_list = Gtk.Button()
        self.fmt_list.add_css_class("tool-btn")
        self.fmt_list.add_css_class("tool-drop")
        lb = Gtk.Box()
        lb.append(icon("np-list-symbolic", 16))
        lb.append(icon("np-chevron-down-symbolic", 12, "tool-chevron"))
        self.fmt_list.set_child(lb)
        self.fmt_list.set_tooltip_text(_("List"))
        self.fmt_list.set_focus_on_click(False)
        self.fmt_list.connect("clicked", lambda b: self._open_menu(b, self._build_list_menu))
        tb.append(self.fmt_list)

        for ic, tip, cb in (("np-bold-symbolic", _("Bold") + " (Ctrl+B)", lambda: self._md(markdown.wrap, "**")),
                            ("np-italic-symbolic", _("Italic") + " (Ctrl+I)", lambda: self._md(markdown.wrap, "*")),
                            ("np-strike-symbolic", _("Strikethrough"), lambda: self._md(markdown.wrap, "~~")),
                            ("np-link-symbolic", _("Link") + " (Ctrl+K)", self.insert_link)):
            tb.append(flat_button(ic, "tool-btn", tip, cb))
        self.fmt_table = Gtk.Button()
        self.fmt_table.add_css_class("tool-btn")
        self.fmt_table.add_css_class("tool-drop")
        tbb = Gtk.Box()
        tbb.append(icon("np-table-symbolic", 16))
        tbb.append(icon("np-chevron-down-symbolic", 12, "tool-chevron"))
        self.fmt_table.set_child(tbb)
        self.fmt_table.set_tooltip_text(_("Insert table"))
        self.fmt_table.set_focus_on_click(False)
        self.fmt_table.connect("clicked", lambda b: self._table_picker(b))
        tb.append(self.fmt_table)
        tb.append(flat_button("np-clear-format-symbolic", "tool-btn", _("Clear formatting"),
                              lambda: self._md(markdown.clear_formatting, convert=False)))
        return tb

    def _statusbar(self):
        sb = Gtk.Box()
        sb.add_css_class("statusbar")
        self.st_pos = label("", "st-text")
        self.st_chars = label("", "st-text")
        self.st_kind = Gtk.Button()
        self.st_kind.add_css_class("st-btn")
        self.st_kind.set_focus_on_click(False)
        self.st_kind_lbl = label("", "st-text")
        self.st_kind.set_child(self.st_kind_lbl)
        self.st_kind.set_tooltip_text(_("Text format"))
        self.st_kind.connect("clicked", lambda b: self._open_menu(b, self._build_kind_menu, up=True))
        self.st_zoom = label("", "st-text")
        self.st_eol = Gtk.Button()
        self.st_eol.add_css_class("st-btn")
        self.st_eol.set_focus_on_click(False)
        self.st_eol_lbl = label("", "st-text")
        self.st_eol.set_child(self.st_eol_lbl)
        self.st_eol.set_tooltip_text(_("Line ending"))
        self.st_eol.connect("clicked", lambda b: self._open_menu(b, self._build_eol_menu, up=True))
        self.st_enc = Gtk.Button()
        self.st_enc.add_css_class("st-btn")
        self.st_enc.set_focus_on_click(False)
        self.st_enc_lbl = label("", "st-text")
        self.st_enc.set_child(self.st_enc_lbl)
        self.st_enc.set_tooltip_text(_("Encoding"))
        self.st_enc.connect("clicked", lambda b: self._open_menu(b, self._build_enc_menu, up=True))

        def seg(w, css):
            box = Gtk.Box()
            box.add_css_class("st-seg")
            box.add_css_class(css)
            box.append(w)
            return box

        def sep():
            s = Gtk.Box()
            s.add_css_class("st-sep")
            s.set_valign(Gtk.Align.CENTER)
            return s
        sb.append(seg(self.st_pos, "st-pos"))
        sb.append(sep())
        sb.append(seg(self.st_chars, "st-chars"))
        sb.append(sep())
        sb.append(seg(self.st_kind, "st-kind"))
        sb.append(Gtk.Box(hexpand=True))
        sb.append(sep())
        sb.append(seg(self.st_zoom, "st-zoom"))
        sb.append(sep())
        sb.append(seg(self.st_eol, "st-eol"))
        sb.append(sep())
        sb.append(seg(self.st_enc, "st-enc"))
        self.statusbar = sb
        sb.set_visible(util.settings()["status_bar"])
        return sb

    # ================================================================= menus
    def _open_menu(self, btn, build, up=False):
        m = Menu(btn, checks=getattr(build, "_checks", False))
        build(m)
        m.set_position(Gtk.PositionType.TOP if up else Gtk.PositionType.BOTTOM)
        m.set_halign(Gtk.Align.START)
        m.on_closed = lambda: GLib.idle_add(lambda: (m.unparent() if m.get_parent() else None, False)[1], priority=GLib.PRIORITY_DEFAULT)
        m.popup()
        first = m.box.get_first_child()
        while first is not None and not (first.get_sensitive() and first.get_focusable()):
            first = first.get_next_sibling()
        if first is not None:
            first.grab_focus()      # keyboard users can arrow through the menu right away
        self.open_menu = m
        return m

    def _build_file_menu(self, m):
        s = util.settings()
        m.shortcut_column = True
        m.add(_("New tab"), self.new_tab, menu_shortcut("Ctrl+N"))
        m.add(_("New window"), self.app.new_window, menu_shortcut("Ctrl+Shift+N"))
        if s["formatting"]:
            m.add(_("New Markdown tab"), lambda: self.new_tab(markdown=True))
        m.add(_("Open"), self.open_dialog, menu_shortcut("Ctrl+O"))
        m.add_submenu(_("Recent"), self._build_recent_menu, sensitive=s["recent_enabled"])
        m.add(_("Save"), self.save, menu_shortcut("Ctrl+S"))
        m.add(_("Save as"), self.save_as, menu_shortcut("Ctrl+Shift+S"))
        m.add(_("Save all"), self.save_all, menu_shortcut("Ctrl+Alt+S"))
        m.add_separator()
        m.add(_("Page setup"), lambda: printing.page_setup(self))
        m.add(_("Print"), self.print_doc, menu_shortcut("Ctrl+P"))
        m.add_separator()
        m.add(_("Close tab"), lambda: self.close_tab(self.doc), menu_shortcut("Ctrl+W"))
        m.add(_("Close window"), self.close, menu_shortcut("Ctrl+Shift+W"))
        m.add(_("Exit"), self.app.exit)

    def _build_recent_menu(self, m):
        rec = [p for p in util.settings()["recent"]]
        if not rec:
            m.add(_("No recent files"), sensitive=False)
            return
        for p in rec:
            b = m.add(util.display_path(p), lambda p=p: self.open_paths([p]))
            b.set_tooltip_text(p)
        m.add_separator()
        m.add(_("Clear recent files"), lambda: util.settings().set("recent", []))

    def _build_edit_menu(self, m):
        doc = self.doc
        buf = doc.buffer if doc else None
        has_sel = bool(buf and buf.get_has_selection())
        clip = self.get_clipboard()
        can_paste = clip.get_formats().contain_gtype(str) or clip.get_formats().contain_mime_type("text/plain")
        can_paste = can_paste or clip.get_formats().contain_mime_type("text/plain;charset=utf-8")
        fmt = bool(doc and doc.formatting)
        m.add(_("Undo"), self.undo, menu_shortcut("Ctrl+Z"), sensitive=bool(buf and buf.get_can_undo()))
        m.add_separator()
        m.add(_("Cut"), self.cut, menu_shortcut("Ctrl+X"), sensitive=has_sel)
        m.add(_("Copy"), self.copy, menu_shortcut("Ctrl+C"), sensitive=has_sel)
        m.add(_("Paste"), self.paste, menu_shortcut("Ctrl+V"), sensitive=bool(can_paste))
        m.add(_("Delete"), self.delete, menu_shortcut("Del"), sensitive=has_sel)
        m.add_separator()
        m.add(_("Clear formatting"), lambda: self._md(markdown.clear_formatting, convert=False),
              sensitive=fmt)
        m.add_separator()
        m.add(_("Find"), lambda: self.show_find(False), menu_shortcut("Ctrl+F"))
        m.add(_("Find next"), self.find_next, "F3")
        m.add(_("Find previous"), self.find_previous, menu_shortcut("Shift+F3"))
        m.add(_("Replace"), lambda: self.show_find(True), menu_shortcut("Ctrl+H"))
        m.add(_("Go to"), self.goto_dialog, menu_shortcut("Ctrl+G"))
        m.add_separator()
        m.add(_("Select all"), self.select_all, menu_shortcut("Ctrl+A"))
        m.add(_("Time/Date"), self.insert_time_date, "F5")
        m.add_separator()
        m.add(_("Font"), self.open_font_settings)

    def _build_view_menu(self, m):
        m.checks = True
        s = util.settings()
        m.add_submenu(_("Zoom"), self._build_zoom_menu)
        m.add(_("Status bar"), lambda: s.set("status_bar", not s["status_bar"]), check=s["status_bar"])
        m.add(_("Word wrap"), lambda: s.set("word_wrap", not s["word_wrap"]), check=s["word_wrap"])

    def _build_zoom_menu(self, m):
        m.add(_("Zoom in"), lambda: self.zoom(+1), menu_shortcut("Ctrl+Plus"))
        m.add(_("Zoom out"), lambda: self.zoom(-1), menu_shortcut("Ctrl+Minus"))
        m.add(_("Restore default zoom"), lambda: self.zoom(0), menu_shortcut("Ctrl+0"))

    def _build_heading_menu(self, m):
        m.checks = True
        cur = markdown.current_heading(self.doc.buffer) if self.doc else 0
        for lvl in range(1, 7):
            m.add(_("Heading %d") % lvl, lambda lvl=lvl: self._md(markdown.heading, lvl), check=(cur == lvl))
        m.add(_("Body text"), lambda: self._md(markdown.heading, 0), check=(cur == 0))

    def _build_list_menu(self, m):
        m.add(_("Bulleted list"), lambda: self._md(markdown.toggle_list, False), icon_name="np-list-symbolic")
        m.add(_("Numbered list"), lambda: self._md(markdown.toggle_list, True), icon_name="np-numbered-symbolic")

    def _build_kind_menu(self, m):
        m.checks = True
        md = bool(self.doc and self.doc.markdown)
        m.add(_("Plain text"), lambda: self.set_markdown(False), check=not md)
        m.add(_("Markdown"), lambda: self.set_markdown(True), check=md, sensitive=util.settings()["formatting"])

    def _build_eol_menu(self, m):
        m.checks = True
        for k in textio.EOL_ORDER:
            m.add(textio.EOL_LABELS[k], lambda k=k: self.doc and self.doc.set_eol(k),
                  check=bool(self.doc and self.doc.eol == k))

    def _build_enc_menu(self, m):
        m.checks = True
        for k in textio.ENCODING_ORDER:
            m.add(_(textio.ENCODINGS[k]), lambda k=k: self.set_encoding(k),
                  check=bool(self.doc and self.doc.encoding == k))

    def _table_picker(self, btn):
        m = Menu(btn)
        m.add_css_class("table-picker")
        grid = Gtk.Grid()
        grid.add_css_class("table-grid")
        info = label(_("Insert table"), "table-info", xalign=0.5)
        cells = {}

        def hover(r, c):
            for (rr, cc), w in cells.items():
                if rr <= r and cc <= c:
                    w.add_css_class("on")
                else:
                    w.remove_css_class("on")
            info.set_label(f"{c + 1} × {r + 1}")
        for r in range(6):
            for c in range(6):
                b = Gtk.Button()
                b.add_css_class("table-cell")
                b.set_focus_on_click(False)
                mo = Gtk.EventControllerMotion()
                mo.connect("enter", lambda *_a, r=r, c=c: hover(r, c))
                b.add_controller(mo)
                b.connect("clicked", lambda *_a, r=r, c=c: (m.popdown(), self._md(markdown.insert_table, r + 1, c + 1)))
                b.connect("notify::has-focus", lambda w, *_a, r=r, c=c: w.has_focus() and hover(r, c))
                cells[(r, c)] = b
                grid.attach(b, c, r, 1, 1)
        m.add_widget(info)
        m.add_widget(grid)
        m.set_position(Gtk.PositionType.BOTTOM)
        m.on_closed = lambda: GLib.idle_add(lambda: (m.unparent() if m.get_parent() else None, False)[1], priority=GLib.PRIORITY_DEFAULT)
        m.popup()
        self.open_menu = m

    def _context_menu(self, view, x, y):
        doc = self.doc
        buf = doc.buffer
        has_sel = buf.get_has_selection()
        m = Menu(view, css="context-menu")
        row = Gtk.Box(homogeneous=True)
        row.add_css_class("ctx-row")
        clip = self.get_clipboard()
        fm = clip.get_formats()
        can_paste = fm.contain_gtype(str) or fm.contain_mime_type("text/plain") or \
            fm.contain_mime_type("text/plain;charset=utf-8")
        for ic, text, cb, ok in (("np-cut-symbolic", _("Cut"), self.cut, has_sel),
                                 ("np-copy-symbolic", _("Copy"), self.copy, has_sel),
                                 ("np-paste-symbolic", _("Paste"), self.paste, can_paste),
                                 ("np-select-all-symbolic", _("Select all"), self.select_all, True),
                                 ("np-delete-symbolic", _("Delete"), self.delete, has_sel)):
            b = Gtk.Button()
            b.add_css_class("ctx-btn")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            v.append(icon(ic, 20))
            v.append(label(text, "ctx-label", xalign=0.5))
            b.set_child(v)
            b.set_sensitive(bool(ok))
            b.connect("clicked", lambda _b, cb=cb: (m.popdown(), GLib.idle_add(lambda: (cb(), False)[1], priority=GLib.PRIORITY_DEFAULT)))
            row.append(b)
        m.add_widget(row)
        m.add_separator()
        m.add(_("Undo"), self.undo, icon_name="np-undo-symbolic", sensitive=buf.get_can_undo())
        if doc.markdown and doc.formatting:
            m.add(_("Insert table"), lambda: self._md(markdown.insert_table, 3, 3), icon_name="np-table-edit-symbolic")
            m.add(_("Insert link"), self.insert_link, icon_name="np-link-symbolic")
        m.on_closed = lambda: GLib.idle_add(lambda: (m.unparent() if m.get_parent() else None, False)[1], priority=GLib.PRIORITY_DEFAULT)
        m.popup_at(x, y)
        self.open_menu = m
        return m

    # ================================================================= tabs
    def documents(self):
        return [p.doc for p in self.pages]

    @property
    def doc(self):
        return self.current.doc if self.current else None

    def active_index(self):
        return self.pages.index(self.current) if self.current in self.pages else 0

    def page_for(self, doc):
        return next((p for p in self.pages if p.doc is doc), None)

    def add_document(self, doc, activate=True, position=None):
        s = util.settings()
        view = GtkSource.View.new_with_buffer(doc.buffer)
        view.add_css_class("editor")
        view.set_left_margin(16)
        view.set_right_margin(16)
        view.set_top_margin(16)
        view.set_bottom_margin(16)
        view.set_pixels_below_lines(0)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if s["word_wrap"] else Gtk.WrapMode.NONE)
        view.set_monospace(False)
        view.set_tab_width(8)
        view.set_smart_backspace(False)
        view.set_auto_indent(False)
        view.set_highlight_current_line(False)
        view.set_show_line_numbers(False)
        view.set_enable_snippets(False)
        view.set_input_hints(Gtk.InputHints.NO_SPELLCHECK | Gtk.InputHints.NO_EMOJI)
        view.add_css_class("z%d" % doc.zoom)
        click = Gtk.GestureClick(button=3)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_view_right_click)
        view.add_controller(click)
        zoom_scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        zoom_scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        zoom_scroll.connect("scroll", self._on_scroll_zoom)
        view.add_controller(zoom_scroll)
        sw = Gtk.ScrolledWindow()
        sw.add_css_class("editor-scroller")
        sw.set_child(view)
        page = Page(doc, view, sw)
        if position is None or position >= len(self.pages):
            self.pages.append(page)
        else:
            self.pages.insert(position, page)
        self.editor_stack.add_child(sw)
        self.strip.add(doc, position)
        doc.set_scheme(theme.get().dark)
        doc.set_formatting(s["formatting"])
        self.find.configure(doc)
        doc._hids = [
            (doc, doc.connect("changed-meta", self._on_doc_meta)),
            (doc.buffer, doc.buffer.connect("mark-set", self._on_mark_set)),
            (doc.buffer, doc.buffer.connect("changed", self._on_buffer_changed)),
            (doc, doc.connect("loaded", self._on_doc_loaded)),
        ]
        if activate:
            self.set_current(doc)
        self.app.schedule_session_save()
        return page

    def set_current(self, doc):
        page = self.page_for(doc)
        if page is None:
            return
        self.current = page
        self.editor_stack.set_visible_child(page.scroller)
        self.strip.set_active(doc)
        self._update_title()
        self._update_status()
        self._update_toolbar()
        if self.main_stack.get_visible_child_name() == "editor" and self.dialog is None:
            page.view.grab_focus()

    def _select_doc(self, doc):
        if self.main_stack.get_visible_child_name() != "editor":
            self.close_settings()
        self.set_current(doc)

    def new_tab(self, markdown=False):
        doc = Document(markdown=markdown)
        self.add_document(doc)
        self.close_settings()
        return doc

    def _replaceable(self):
        """The single empty untitled tab is replaced when a file is opened (like Windows)."""
        if len(self.pages) == 1:
            d = self.pages[0].doc
            if d.path is None and d.is_empty() and not d.modified and not d.loading:
                return d
        return None

    def open_paths(self, paths):
        for p in paths:
            p = os.path.abspath(p)
            existing = next((d for d in self.documents() if d.path == p), None)
            if existing is not None:
                self.set_current(existing)
                continue
            if os.path.isdir(p):
                continue
            blank = self._replaceable()
            doc = Document()
            if not os.path.exists(p):
                # Windows Notepad offers to create it; open an empty tab bound to that path
                doc.path = p
                doc.markdown = p.lower().endswith((".md", ".markdown"))
                doc.apply_language()
                self.add_document(doc)
            else:
                self.add_document(doc)
                doc.load(p)
            if blank is not None:
                self._remove_doc(blank)
            util.settings().add_recent(p)
        self.close_settings()

    def _remove_doc(self, doc):
        page = self.page_for(doc)
        if page is None:
            return
        idx = self.pages.index(page)
        for obj, h in getattr(doc, "_hids", []):
            obj.disconnect(h)
        doc._hids = []
        self.pages.remove(page)
        self.editor_stack.remove(page.scroller)
        self.strip.remove(doc)
        if self.current is page:
            self.current = None
            if self.pages:
                self.set_current(self.pages[min(idx, len(self.pages) - 1)].doc)
        self.app.schedule_session_save()

    def close_tab(self, doc, then=None):
        """Close a tab, asking to save changes first. The window closes with its last tab."""
        if doc is None:
            return

        def really():
            self._remove_doc(doc)
            if not self.pages:
                self.closing = True
                self.app.window_closed(self, save_session=False)
                self.destroy()
            if then:
                then()
        if self._needs_saving(doc):
            self.set_current(doc)
            self.ask_save(doc, really)
        else:
            really()

    @staticmethod
    def _needs_saving(doc):
        if doc.loading:
            return False
        if doc.path is None:
            return not doc.is_empty()
        return doc.modified

    def next_tab(self, step):
        if len(self.pages) < 2 or self.current is None:
            return
        i = (self.pages.index(self.current) + step) % len(self.pages)
        self.set_current(self.pages[i].doc)

    # ================================================================= status / title
    def _update_title(self):
        d = self.doc
        if d is None:
            self.set_title(_("Notepad"))
            return
        self.set_title(f"{d.title} - {_('Notepad')}")

    def _on_doc_meta(self, doc):
        self.strip.refresh(doc)
        if doc is self.doc:
            self._update_title()
            self._update_status()
            self._update_toolbar()
        self.app.schedule_session_save()

    def _on_doc_loaded(self, doc, err):
        if err:
            path = doc.path
            self._remove_doc(doc)
            if not self.pages:
                self.new_tab()
            self.error(_("Unable to open file"), f"{path}\n{err}")
        elif doc is self.doc:
            self._update_status()

    def _on_mark_set(self, buf, _it, mark):
        if mark is buf.get_insert() and self.doc is not None and buf is self.doc.buffer:
            self._update_status_pos()
            if self.toolbar.get_visible():
                lvl = markdown.current_heading(buf)
                self.heading_label.set_label(f"H{lvl}" if lvl else "H1")

    def _on_buffer_changed(self, buf):
        if self.doc is not None and buf is self.doc.buffer and not self.doc.loading:
            self._update_status_pos()
        self.app.schedule_session_save()

    def _update_status_pos(self):
        d = self.doc
        if d is None:
            return
        buf = d.buffer
        it = buf.get_iter_at_mark(buf.get_insert())
        self.st_pos.set_label(_("Ln %d, Col %d") % (it.get_line() + 1, it.get_line_offset() + 1))
        total = buf.get_char_count()
        sel = buf.get_selection_bounds()
        if sel:
            n = abs(sel[1].get_offset() - sel[0].get_offset())
            self.st_chars.set_label(_("%s of %s characters") % (self._num(n), self._num(total)))
        else:
            self.st_chars.set_label((_("%s character") if total == 1 else _("%s characters")) % self._num(total))

    @staticmethod
    def _num(n):
        s = f"{n:,}"
        from . import i18n
        return s.replace(",", ".") if i18n.LANG == "es" else s

    def _update_status(self):
        d = self.doc
        if d is None:
            return
        if d.loading:
            self.st_pos.set_label(_("Loading…"))
            self.st_chars.set_label("")
        else:
            self._update_status_pos()
        self.st_kind_lbl.set_label(_("Markdown") if d.markdown else _("Plain text"))
        self.st_zoom.set_label(f"{d.zoom}%")
        self.st_eol_lbl.set_label(textio.EOL_LABELS[d.eol])
        self.st_enc_lbl.set_label(_(textio.ENCODINGS[d.encoding]))

    def _update_toolbar(self):
        d = self.doc
        # like Windows: the toolbar is there whenever formatting is on; using it on a plain-text
        # tab turns the tab into a Markdown one (see _md)
        on = bool(d and util.settings()["formatting"]
                  and self.main_stack.get_visible_child_name() == "editor")
        self.toolbar.set_visible(on)
        if on:
            lvl = markdown.current_heading(d.buffer)
            self.heading_label.set_label(f"H{lvl}" if lvl else "H1")

    # ================================================================= settings/theme
    def _on_setting(self, key):
        s = util.settings()
        if key == "word_wrap":
            for p in self.pages:
                p.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if s["word_wrap"] else Gtk.WrapMode.NONE)
        elif key == "status_bar":
            self.statusbar.set_visible(s["status_bar"])
        elif key.startswith("font_"):
            self._apply_font()
        elif key == "formatting":
            for p in self.pages:
                p.doc.set_formatting(s["formatting"])
            self._update_toolbar()
        elif key in ("match_case", "whole_word", "wrap_around"):
            for p in self.pages:
                self.find.configure(p.doc)

    def _apply_font(self):
        s = util.settings()
        theme.get().set_editor_font(s["font_family"], s["font_style"], s["font_size"])

    def _on_theme(self):
        dark = theme.get().dark
        for p in self.pages:
            p.doc.set_scheme(dark)
        self._caps_redraw()
        self.strip.queue_draw_tabs()

    def _on_resize(self, *_):
        w = self.get_width() or self.get_default_size()[0]
        self.find.set_size_request(max(300, min(860, w - 40)), -1)
        if self.settings_page is not None:
            self.settings_page.set_narrow(self.get_width() < 900)

    def _on_active(self):
        if self.is_active():
            self.app.last_active = self

    def open_settings(self):
        if self.settings_page is None:
            self.settings_page = SettingsPage(self)
            self.main_stack.add_named(self.settings_page, "settings")
        self.find.set_visible(False)
        self.settings_page.set_narrow((self.get_width() or 1000) < 900)
        self.main_stack.set_visible_child_name("settings")
        self.title_stack.set_visible_child_name("settings")
        self.add_css_class("in-settings")
        self.set_title(f"{_('Settings')} - {_('Notepad')}")

    def open_font_settings(self):
        self.open_settings()
        self.settings_page.show_font()

    def close_settings(self):
        if self.main_stack.get_visible_child_name() == "editor":
            return
        self.main_stack.set_visible_child_name("editor")
        self.title_stack.set_visible_child_name("tabs")
        self.remove_css_class("in-settings")
        self._update_title()
        self._update_toolbar()
        self.focus_editor()

    def focus_editor(self):
        if self.current is not None:
            self.current.view.grab_focus()

    # ================================================================= keyboard
    def _on_key(self, _c, keyval, _code, state):
        mods = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.ALT_MASK)
        C, S, A = Gdk.ModifierType.CONTROL_MASK, Gdk.ModifierType.SHIFT_MASK, Gdk.ModifierType.ALT_MASK
        k = Gdk.keyval_to_lower(keyval)
        name = Gdk.keyval_name(k) or ""
        if self.dialog is not None:
            return False
        table = {
            (C, "n"): self.new_tab, (C | S, "n"): self.app.new_window, (C, "o"): self.open_dialog,
            (C, "s"): self.save, (C | S, "s"): self.save_as, (C | A, "s"): self.save_all,
            (C, "p"): self.print_doc, (C, "w"): lambda: self.close_tab(self.doc), (C | S, "w"): self.close,
            (C, "f"): lambda: self.show_find(False), (C, "h"): lambda: self.show_find(True),
            (C, "g"): self.goto_dialog, (0, "F3"): self.find_next, (S, "F3"): self.find_previous,
            (0, "F5"): self.insert_time_date, (C, "plus"): lambda: self.zoom(1),
            (C, "equal"): lambda: self.zoom(1), (C, "KP_Add"): lambda: self.zoom(1),
            (C, "minus"): lambda: self.zoom(-1), (C, "KP_Subtract"): lambda: self.zoom(-1),
            (C, "0"): lambda: self.zoom(0), (C, "KP_0"): lambda: self.zoom(0),
            (C, "Tab"): lambda: self.next_tab(1), (C | S, "ISO_Left_Tab"): lambda: self.next_tab(-1),
            (C | S, "Tab"): lambda: self.next_tab(-1), (C, "Page_Down"): lambda: self.next_tab(1),
            (C, "Page_Up"): lambda: self.next_tab(-1), (C, "y"): self.redo, (C | S, "z"): self.redo,
            (A, "f"): lambda: self.menu_buttons["file"].emit("clicked"),
            (A, "e"): lambda: self.menu_buttons["edit"].emit("clicked"),
            (A, "v"): lambda: self.menu_buttons["view"].emit("clicked"),
        }
        if self.doc is not None and self.doc.markdown and util.settings()["formatting"] \
                and self.current.view.has_focus():
            table[(C, "b")] = lambda: self._md(markdown.wrap, "**")
            table[(C, "i")] = lambda: self._md(markdown.wrap, "*")
            table[(C, "k")] = self.insert_link
        if name in ("plus", "KP_Add", "KP_Subtract", "KP_0"):
            mods &= ~S          # Ctrl+Plus needs Shift on many layouts
        if (mods, name) == (0, "Escape"):
            if self.main_stack.get_visible_child_name() == "settings":
                self.close_settings()
                return True
            if self.find.get_visible() and self.current and self.current.view.has_focus():
                self.find.close_card()
                return True
        if (mods, name) in ((0, "Menu"), (S, "F10")) and self.current and self.current.view.has_focus():
            v = self.current.view
            buf = self.doc.buffer
            loc = v.get_iter_location(buf.get_iter_at_mark(buf.get_insert()))
            x, y = v.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, loc.x, loc.y + loc.height)
            self._context_menu(v, x, y)
            return True
        if C & mods and name.isdigit() and name != "0" and len(name) == 1 and not (S & mods):
            i = int(name) - 1
            if name == "9":
                i = len(self.pages) - 1
            if 0 <= i < len(self.pages):
                self.set_current(self.pages[i].doc)
            return True
        fn = table.get((mods, name))
        if fn is None and name in ("F3", "F5"):
            fn = table.get((mods, name))
        if fn is not None:
            fn()
            return True
        return False

    def _on_view_right_click(self, g, n, x, y):
        g.set_state(Gtk.EventSequenceState.CLAIMED)
        view = g.get_widget()
        buf = view.get_buffer()
        bx, by = view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        ok, it = view.get_iter_at_location(bx, by)
        sel = buf.get_selection_bounds()
        if ok and not (sel and sel[0].compare(it) <= 0 <= sel[1].compare(it)):
            buf.place_cursor(it)
        self._context_menu(view, x, y)

    def _on_scroll_zoom(self, ctl, _dx, dy):
        st = ctl.get_current_event_state()
        if st & Gdk.ModifierType.CONTROL_MASK:
            self.zoom(-1 if dy > 0 else 1)
            return True
        return False

    def _on_drop(self, _t, value, _x, _y):
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        if paths:
            self.open_paths(paths)
            return True
        return False

    # ================================================================= edit commands
    def undo(self):
        b = self.doc.buffer
        if b.get_can_undo():
            b.undo()

    def redo(self):
        b = self.doc.buffer
        if b.get_can_redo():
            b.redo()

    def cut(self):
        self.doc.buffer.cut_clipboard(self.get_clipboard(), True)

    def copy(self):
        self.doc.buffer.copy_clipboard(self.get_clipboard())

    def paste(self):
        self.doc.buffer.paste_clipboard(self.get_clipboard(), None, True)
        self.current.view.scroll_mark_onscreen(self.doc.buffer.get_insert())

    def delete(self):
        self.doc.buffer.delete_selection(True, True)

    def select_all(self):
        b = self.doc.buffer
        b.select_range(b.get_start_iter(), b.get_end_iter())
        self.focus_editor()

    def insert_time_date(self):
        from . import i18n
        t = time.localtime()
        if i18n.LANG == "es":
            s = time.strftime("%H:%M %d/%m/%Y", t)
        else:
            h = t.tm_hour % 12 or 12
            s = f"{h}:{t.tm_min:02d} {'AM' if t.tm_hour < 12 else 'PM'} {t.tm_mon}/{t.tm_mday}/{t.tm_year}"
        b = self.doc.buffer
        b.begin_user_action()
        b.delete_selection(True, True)
        b.insert_at_cursor(s, -1)
        b.end_user_action()
        self.current.view.scroll_mark_onscreen(b.get_insert())

    def zoom(self, step):
        d = self.doc
        if d is None:
            return
        if step == 0:
            z = 100
        else:
            i = ZOOM_STEPS.index(d.zoom) if d.zoom in ZOOM_STEPS else ZOOM_STEPS.index(100)
            z = ZOOM_STEPS[max(0, min(len(ZOOM_STEPS) - 1, i + step))]
        v = self.current.view
        v.remove_css_class("z%d" % d.zoom)
        d.zoom = z
        v.add_css_class("z%d" % z)
        self._update_status()

    def set_markdown(self, on):
        if self.doc is not None:
            self.doc.set_markdown(on)
            self._update_toolbar()

    def set_encoding(self, enc):
        d = self.doc
        if d is None:
            return
        if not textio.can_encode(d.get_text(), enc):
            self.error(_("Unable to change the encoding"),
                       _("This text contains characters that can't be saved in %s.") % _(textio.ENCODINGS[enc]))
            return
        d.set_encoding(enc)

    def _md(self, fn, *args, convert=True):
        d = self.doc
        if d is None:
            return
        if convert and not d.markdown:
            d.set_markdown(True)
        fn(d.buffer, *args)
        self._update_toolbar()
        self.focus_editor()

    def insert_link(self):
        buf = self.doc.buffer
        sel_text = markdown.selected_text(buf)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(label(_("Text"), "dialog-field"))
        t = Gtk.Entry()
        t.add_css_class("fluent-entry")
        t.set_text(sel_text)
        box.append(t)
        box.append(label(_("Link"), "dialog-field"))
        u = Gtk.Entry()
        u.add_css_class("fluent-entry")
        u.set_placeholder_text("https://")
        box.append(u)

        def ok():
            url = u.get_text().strip()
            if not url:
                return True
            if not self.doc.markdown:
                self.doc.set_markdown(True)
            markdown.insert_link(buf, t.get_text().strip(), url)
            self.focus_editor()
        d = ContentDialog(self, _("Insert link"), box,
                          [(_("Insert"), ok, "accent"), (_("Cancel"), self.focus_editor, "std")])
        u.connect("activate", lambda *_: d._done(ok))
        d.present(focus=u if sel_text else t)

    # ================================================================= find / replace
    def show_find(self, replace=False):
        if self.main_stack.get_visible_child_name() != "editor":
            self.close_settings()
        seed = None
        if self.doc is not None:
            sel = markdown.selected_text(self.doc.buffer)
            if sel and "\n" not in sel and len(sel) < 200:
                seed = sel
        self.find.open_card(replace, seed)

    BIG = 2_000_000

    def _set_needle(self, doc, text):
        """GtkSourceView scans the whole buffer for occurrences when a search text is set:
        big documents are searched with _search_big instead and get no search text."""
        big = doc.buffer.get_char_count() > self.BIG
        doc.search_settings.set_search_text(None if big or not text else text)

    def _regex(self, doc):
        import re
        ss = doc.search_settings
        pat = re.escape(self.find.text)
        if ss.get_at_word_boundaries():
            pat = r"(?<!\w)" + pat + r"(?!\w)"
        return re.compile(pat, 0 if ss.get_case_sensitive() else re.IGNORECASE)

    def search_text_changed(self):
        text = self.find.text
        for p in self.pages:
            self._set_needle(p.doc, text)
        if text and self.doc is not None and self.doc.buffer.get_char_count() < 2_000_000:
            # incremental search from the start of the selection (big files: on Enter only)
            buf = self.doc.buffer
            sel = buf.get_selection_bounds()
            start = sel[0] if sel else buf.get_iter_at_mark(buf.get_insert())
            self._search(start, forward=True, focus_editor=False)

    searching = False

    def _search(self, it, forward=True, focus_editor=False):
        d = self.doc
        ctx = d.search
        if d.buffer.get_char_count() > self.BIG:
            self._search_big(d, it.get_offset(), forward, focus_editor)
            return None
        if forward:
            ok, s, e, _wrapped = ctx.forward(it)
        else:
            ok, s, e, _wrapped = ctx.backward(it)
        self._search_result(d, ok, s, e, focus_editor)
        return ok

    def _search_big(self, d, start, forward, focus_editor):
        """Big documents: regular-expression search of a text snapshot in a worker thread,
        so the window keeps responding (GtkSourceView's own search is slow on 20 MB)."""
        import threading
        needle = self.find.text
        if not needle:
            return
        rx = self._regex(d)
        wrap = d.search_settings.get_wrap_around()
        text = d.cached_text()
        serial = d.change_serial
        self.searching = True

        def work():
            m = None
            if forward:
                m = rx.search(text, start)
                if m is None and wrap:
                    m = rx.search(text, 0, start + len(needle))
            else:
                last = None
                for last in rx.finditer(text, 0, start):
                    pass
                m = last
                if m is None and wrap:
                    for last in rx.finditer(text, start):
                        pass
                    m = last
            # default priority: GtkTextView's line validation (idle) must not delay the result
            GLib.idle_add(finish, m.span() if m else None, priority=GLib.PRIORITY_DEFAULT)

        def finish(span):
            self.searching = False
            if span is None or d.change_serial != serial:
                self._search_result(d, False, None, None, focus_editor)
            else:
                b = d.buffer
                self._search_result(d, True, b.get_iter_at_offset(span[0]), b.get_iter_at_offset(span[1]),
                                    focus_editor)
            return False
        threading.Thread(target=work, daemon=True).start()

    def _search_result(self, d, ok, s, e, focus_editor):
        self.find.set_no_match(not ok)
        if ok and d is self.doc:
            d.buffer.select_range(s, e)
            self.current.view.scroll_to_mark(d.buffer.get_insert(), 0.1, False, 0, 0)
        if focus_editor:
            self.focus_editor()

    def find_next(self):
        if self.doc is None:
            return
        if not self.find.text:
            self.show_find(self.find.replace_mode)
            return
        self._set_needle(self.doc, self.find.text)
        buf = self.doc.buffer
        sel = buf.get_selection_bounds()
        it = sel[1] if sel else buf.get_iter_at_mark(buf.get_insert())
        self._search(it, True)

    def find_previous(self):
        if self.doc is None:
            return
        if not self.find.text:
            self.show_find(self.find.replace_mode)
            return
        self._set_needle(self.doc, self.find.text)
        buf = self.doc.buffer
        sel = buf.get_selection_bounds()
        it = sel[0] if sel else buf.get_iter_at_mark(buf.get_insert())
        self._search(it, False)

    def replace_one(self, replacement):
        d = self.doc
        if d is None or not self.find.text:
            return
        buf = d.buffer
        sel = buf.get_selection_bounds()
        if sel:
            if buf.get_char_count() > self.BIG:
                if self._regex(d).fullmatch(buf.get_text(sel[0], sel[1], True)):
                    buf.begin_user_action()
                    buf.delete(sel[0], sel[1])
                    buf.insert_at_cursor(replacement, -1)
                    buf.end_user_action()
            else:
                self._set_needle(d, self.find.text)
                ok, s, e, _w = d.search.forward(sel[0])
                if ok and s.equal(sel[0]) and e.equal(sel[1]):
                    try:
                        d.search.replace(s, e, replacement, -1)
                    except GLib.Error:
                        pass
        self.find_next()

    def replace_all(self, replacement):
        d = self.doc
        if d is None or not self.find.text:
            return 0
        buf = d.buffer
        if buf.get_char_count() > self.BIG:
            new, n = self._regex(d).subn(lambda _m: replacement, d.cached_text())
            if n:
                buf.begin_user_action()
                buf.delete(buf.get_start_iter(), buf.get_end_iter())
                buf.insert(buf.get_start_iter(), new, -1)
                buf.end_user_action()
        else:
            self._set_needle(d, self.find.text)
            try:
                n = d.search.replace_all(replacement, -1)
            except GLib.Error:
                n = 0
        self.find.set_no_match(n == 0)
        return n

    # ================================================================= go to
    def goto_dialog(self):
        d = self.doc
        if d is None:
            return
        buf = d.buffer
        cur = buf.get_iter_at_mark(buf.get_insert()).get_line() + 1
        total = buf.get_line_count()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(label(_("Line number"), "dialog-field"))
        e = Gtk.Entry()
        e.add_css_class("fluent-entry")
        e.set_text(str(cur))
        e.set_input_purpose(Gtk.InputPurpose.DIGITS)
        box.append(e)
        err = label("", "dialog-error", wrap=True)
        err.set_visible(False)
        box.append(err)

        def go():
            try:
                n = int(e.get_text().strip())
            except ValueError:
                n = 0
            if n < 1 or n > total:
                err.set_label(_("The line number is beyond the total number of lines"))
                err.set_visible(True)
                return True
            it = buf.get_iter_at_line(n - 1)
            it = it[1] if isinstance(it, tuple) else it
            buf.place_cursor(it)
            self.current.view.scroll_to_mark(buf.get_insert(), 0.25, False, 0, 0)
            self.focus_editor()
        dlg = ContentDialog(self, _("Go to line"), box,
                            [(_("Go to"), go, "accent"), (_("Cancel"), self.focus_editor, "std")],
                            width=340, on_cancel=self.focus_editor)
        e.connect("activate", lambda *_: dlg._done(go))
        e.connect("changed", lambda *_: err.set_visible(False))
        dlg.present(focus=e)
        e.select_region(0, -1)
        return dlg

    # ================================================================= dialogs
    def show_dialog(self, dlg):
        if self.dialog is not None:
            self.hide_dialog(self.dialog)
        self.dialog = dlg
        self.smoke.set_visible(True)
        self.overlay.add_overlay(dlg)

    def hide_dialog(self, dlg):
        if dlg.get_parent() is self.overlay:
            self.overlay.remove_overlay(dlg)
        if self.dialog is dlg:
            self.dialog = None
            self.smoke.set_visible(False)

    def error(self, title, body):
        d = ContentDialog(self, title, body, [(_("OK"), None, "accent")])
        d.present()
        return d

    def ask_save(self, doc, after, cancelled=None):
        """Windows Notepad prompt: Save / Don't save / Cancel."""
        name = doc.path and os.path.basename(doc.path) or doc.title
        if doc.path is None:
            name = _("Untitled")

        def save():
            self.save(doc, then=after)

        def dont():
            after()

        def cancel():
            if cancelled:
                cancelled()
        dlg = ContentDialog(self, _("Notepad"), _("Do you want to save changes to %s?") % name,
                            [(_("Save"), save, "accent"), (_("Don't save"), dont, "std"), (_("Cancel"), cancel, "std")],
                            width=460, on_cancel=cancel)
        dlg.present()
        return dlg

    # ================================================================= files
    def open_dialog(self):
        fd = Gtk.FileDialog()
        fd.set_title(_("Open"))
        fd.set_filters(self._filters())
        if self.doc is not None and self.doc.path:
            fd.set_initial_folder(Gio.File.new_for_path(os.path.dirname(self.doc.path)))

        def done(dlg, res):
            try:
                files = dlg.open_multiple_finish(res)
            except GLib.Error:
                return
            paths = [files.get_item(i).get_path() for i in range(files.get_n_items())]
            self.open_paths([p for p in paths if p])
        fd.open_multiple(self, None, done)

    @staticmethod
    def _filters():
        store = Gio.ListStore.new(Gtk.FileFilter)
        f1 = Gtk.FileFilter()
        f1.set_name(_("Text documents"))
        f1.add_mime_type("text/*")
        f1.add_suffix("txt")
        f1.add_suffix("md")
        f1.add_suffix("log")
        f2 = Gtk.FileFilter()
        f2.set_name(_("All files"))
        f2.add_pattern("*")
        store.append(f1)
        store.append(f2)
        return store

    def save(self, doc=None, then=None):
        doc = doc or self.doc
        if doc is None:
            return
        if doc.path is None:
            self.save_as(doc, then)
            return
        if self._write(doc, doc.path) and then:
            then()

    def _write(self, doc, path):
        if not textio.can_encode(doc.get_text(), doc.encoding):
            # characters not representable: save as UTF-8 instead of losing them
            doc.encoding = "utf-8"
        try:
            doc.save(path)
        except (OSError, UnicodeEncodeError) as e:
            msg = getattr(e, "strerror", None) or str(e)
            self.error(_("Unable to save file"), f"{path}\n{msg}")
            return False
        util.settings().add_recent(doc.path)
        self.app.schedule_session_save()
        return True

    def save_as(self, doc=None, then=None):
        doc = doc or self.doc
        if doc is None:
            return
        fd = Gtk.FileDialog()
        fd.set_title(_("Save as"))
        fd.set_filters(self._filters())
        if doc.path:
            fd.set_initial_file(Gio.File.new_for_path(doc.path))
        else:
            base = doc.title if doc.title != _("Untitled") else _("Untitled")
            base = "".join(ch for ch in base if ch not in '/\\:*?"<>|').strip()[:40] or _("Untitled")
            fd.set_initial_name(base + (".md" if doc.markdown else ".txt"))
            fd.set_initial_folder(Gio.File.new_for_path(os.path.expanduser("~/Documents")
                                                        if os.path.isdir(os.path.expanduser("~/Documents"))
                                                        else os.path.expanduser("~")))

        def done(dlg, res):
            try:
                f = dlg.save_finish(res)
            except GLib.Error:
                return
            if f is None or f.get_path() is None:
                return
            if self._write(doc, f.get_path()) and then:
                then()
        fd.save(self, None, done)

    def save_all(self):
        docs = [d for d in self.documents() if self._needs_saving(d)]

        def step():
            if docs:
                d = docs.pop(0)
                self.set_current(d)
                self.save(d, then=step)
        step()

    def print_doc(self):
        if self.doc is not None:
            printing.print_document(self, self.doc, lambda m: self.error(_("Unable to print"), m))

    # ================================================================= closing
    def _on_close_request(self, *_):
        if self.closing:
            return False
        s = util.settings()
        others = [w for w in self.app.windows if w is not self and not w.closing]
        if s["startup"] == "continue" and not others and not util.DEMO:
            # last window: keep everything (including unsaved text) for next time
            self.closing = True
            self._remember_size()
            self.app.window_closed(self, save_session=True)
            return False
        self.close_with_prompts(lambda: self._finish_close())
        return True

    def _finish_close(self):
        self.closing = True
        self._remember_size()
        self.app.window_closed(self, save_session=False)
        self.destroy()

    def close_with_prompts(self, done, cancelled=None):
        pending = [d for d in self.documents() if self._needs_saving(d)]

        def step():
            if not pending:
                done()
                return
            d = pending.pop(0)
            self.set_current(d)
            self.ask_save(d, step, cancelled)
        step()

    def _remember_size(self):
        if util.DEMO:
            return
        s = util.settings()
        if not self.is_maximized():
            w, h = self.get_width(), self.get_height()
            if w > 100 and h > 100:
                s.set("window_w", w, notify=False)
                s.set("window_h", h, notify=False)
        s.set("window_max", bool(self.is_maximized()), notify=False)

    def do_unrealize(self):
        s = util.settings()
        if self._on_setting in s.listeners:
            s.listeners.remove(self._on_setting)
        th = theme.get()
        if self._on_theme in th.listeners:
            th.listeners.remove(self._on_theme)
        Gtk.ApplicationWindow.do_unrealize(self)


__all__ = ["NotepadWindow", "Pango"]

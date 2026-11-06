"""Main window: title bar, menu bar, toolbar, workspace, layers panel and status bar."""
from __future__ import annotations

import os

import cairo
from gi.repository import Gdk, Gio, GLib, Gtk

from . import dialogs, fileio, raster, theme, util
from .canvas import Canvas, Ruler
from .document import Document
from .i18n import _
from .panels import LayersPanel, SettingsPage, SideSliders, StatusBar, ThumbnailView, Toast
from .ribbon import Ribbon, TextBar, brushes_menu, rgba_hex, size_menu, style_menu
from .shapes import FILLS, OUTLINES
from .tools import make_tools
from .widgets import Menu, button, icon, label, popup_menu

DEFAULT_W, DEFAULT_H = 1152, 648


class PaintWindow(Gtk.ApplicationWindow):
    def __init__(self, app, path=None):
        super().__init__(application=app)
        self.app = app
        self.add_css_class("paint")
        self.set_icon_name(util.APP_ID)
        self.set_default_size(1280, 800)
        self.set_size_request(640, 420)
        self.path = None
        self.fmt = None
        self.primary = (0.0, 0.0, 0.0, 1.0)
        self.secondary = (1.0, 1.0, 1.0, 1.0)
        self.active_slot = 0
        self.sizes = {"pencil": 1, "brush": 5, "eraser": 10, "shape": 3}
        self.opacity = 1.0
        self.brush = "brush"
        self.shape = "rectangle"
        self.outline_style = "solid"
        self.fill_style = "none"
        self.transparent_selection = False
        self.text_props = {"family": "Segoe UI", "size": 18, "bold": False, "italic": False,
                           "underline": False, "strike": False, "align": "left", "background": False}
        self.custom_colors = list(util.opts()["custom_colors"])
        self.layers_visible = False
        self.dialog = None
        self.clip_surface = None
        self.toolbar_peek = False
        self.page_setup = None
        self.print_settings = None
        self.doc = Document(DEFAULT_W, DEFAULT_H)
        self.tools = make_tools(self)
        self.tool_name = "pencil"
        self.prev_tool = "pencil"
        self._build()
        self.canvas.set_document(self.doc)
        self.doc.connect(self._on_doc)
        self.set_tool("brush")
        self._sync_history()
        self.connect("close-request", self._close_request)
        self.connect("notify::maximized", lambda *_a: self._sync_max())
        self.connect("notify::fullscreened", lambda *_a: self._sync_fullscreen())
        theme.get().connect(self._on_theme)
        self._apply_view_options()
        self._sync_title()
        if path:
            GLib.idle_add(lambda: (self.open_path(path), False)[1])
        else:
            GLib.idle_add(lambda: (self._initial_zoom(), False)[1])

    # ================================================================== build
    def _build(self):
        # ---- title bar (icon, title, caption buttons)
        handle = Gtk.WindowHandle()
        bar = Gtk.Box()
        bar.add_css_class("titlebar")
        bar.append(icon(util.APP_ID, 16, "title-icon"))
        self.title_label = label("", "title-label")
        bar.append(self.title_label)
        bar.append(Gtk.Box(hexpand=True))
        caps = Gtk.Box()
        caps.add_css_class("caption-buttons")
        caps.set_valign(Gtk.Align.START)
        for name, cb, tip in (("minimize", lambda *_a: self.minimize(), _("Minimize")),
                              ("maximize", lambda *_a: self.unmaximize() if self.is_maximized() else self.maximize(),
                               _("Maximize")),
                              ("close", lambda *_a: self.close(), _("Close"))):
            b = Gtk.Button()
            b.add_css_class("caption")
            b.add_css_class(name)
            b.set_tooltip_text(tip)
            da = Gtk.DrawingArea()
            da.set_draw_func(self._draw_caption, name)
            b.set_child(da)
            b.connect("clicked", cb)
            caps.append(b)
            if name == "maximize":
                self.max_area = da
        bar.append(caps)
        handle.set_child(bar)
        self.set_titlebar(handle)

        # ---- root overlay: page stack + dialogs + flyouts
        from .widgets import FlyoutLayer
        root = Gtk.Overlay()
        self.set_child(root)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        root.set_child(self.stack)
        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack.add_named(editor, "editor")
        self.settings_page = None

        # ---- menu bar
        mh = Gtk.WindowHandle()
        mb = Gtk.Box()
        mb.add_css_class("menubar")
        self.menu_buttons = {}
        for key, text in (("file", _("File")), ("edit", _("Edit")), ("view", _("View"))):
            b = button(text, "menu-button", cb=lambda key=key: self.open_menu(key))
            self.menu_buttons[key] = b
            mb.append(b)
        mb.append(self._vsep())
        self.save_btn = button(icon("save", 20), "bar-button", tooltip=_("Save (Ctrl+S)"), cb=self.save)
        mb.append(self.save_btn)
        mb.append(self._vsep())
        self.undo_btn = button(icon("undo", 20), "bar-button", tooltip=_("Undo (Ctrl+Z)"), cb=self.undo)
        self.redo_btn = button(icon("redo", 20), "bar-button", tooltip=_("Redo (Ctrl+Y)"), cb=self.redo)
        mb.append(self.undo_btn)
        mb.append(self.redo_btn)
        mb.append(Gtk.Box(hexpand=True))
        self.show_tb_btn = button(icon("chevron-down", 16), "bar-button", tooltip=_("Show toolbar"),
                                  cb=self._peek_toolbar)
        mb.append(self.show_tb_btn)
        mb.append(button(icon("settings", 20), "bar-button", "settings-button", tooltip=_("Settings"),
                         cb=self.open_settings))
        mh.set_child(mb)
        self.menubar = mh
        editor.append(mh)

        # ---- ribbon
        self.ribbon = Ribbon(self)
        self.ribbon_rev = Gtk.Revealer()
        self.ribbon_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.ribbon_rev.set_transition_duration(120)
        rsc = Gtk.ScrolledWindow()
        rsc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        rsc.set_propagate_natural_height(True)
        rsc.add_css_class("ribbon-scroller")
        rsc.set_child(self.ribbon)
        self.ribbon_rev.set_child(rsc)
        self.ribbon_rev.set_reveal_child(True)
        editor.append(self.ribbon_rev)

        # ---- body: workspace + layers panel
        body = Gtk.Box()
        body.set_vexpand(True)
        editor.append(body)
        self.workspace = Gtk.Overlay()
        self.workspace.add_css_class("workspace")
        self.workspace.set_hexpand(True)
        body.append(self.workspace)
        grid = Gtk.Grid()
        self.workspace.set_child(grid)
        self.canvas = Canvas(self)
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.add_css_class("canvas-scroller")
        self.scroller.set_hexpand(True)
        self.scroller.set_vexpand(True)
        vp = Gtk.Viewport()
        vp.set_child(self.canvas)
        vp.set_scroll_to_focus(False)
        self.scroller.set_child(vp)
        self.canvas.hadj = self.scroller.get_hadjustment()
        self.canvas.vadj = self.scroller.get_vadjustment()
        for adj in (self.canvas.hadj, self.canvas.vadj):
            adj.connect("value-changed", lambda *_a: self._scrolled())
        self.hruler = Ruler(self.canvas, Gtk.Orientation.HORIZONTAL)
        self.vruler = Ruler(self.canvas, Gtk.Orientation.VERTICAL)
        self.corner = Gtk.Box()
        self.corner.add_css_class("ruler-corner")
        self.corner.set_size_request(20, 20)
        grid.attach(self.corner, 0, 0, 1, 1)
        grid.attach(self.hruler, 1, 0, 1, 1)
        grid.attach(self.vruler, 0, 1, 1, 1)
        grid.attach(self.scroller, 1, 1, 1, 1)
        self.sliders = SideSliders(self)
        self.workspace.add_overlay(self.sliders)
        self.textbar = TextBar(self)
        self.textbar_rev = Gtk.Revealer()
        self.textbar_rev.set_child(self.textbar)
        self.textbar_rev.set_halign(Gtk.Align.CENTER)
        self.textbar_rev.set_valign(Gtk.Align.START)
        self.textbar_rev.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.workspace.add_overlay(self.textbar_rev)
        self.thumb = ThumbnailView(self)
        self.thumb.set_visible(False)
        self.workspace.add_overlay(self.thumb)
        self.bubble = label("", "value-bubble")
        self.bubble.set_halign(Gtk.Align.START)
        self.bubble.set_valign(Gtk.Align.START)
        self.bubble.set_can_target(False)
        self.bubble.set_visible(False)
        self.workspace.add_overlay(self.bubble)
        self.toast = Toast()
        self.workspace.add_overlay(self.toast)

        self.layers_panel = LayersPanel(self)
        self.layers_rev = Gtk.Revealer()
        self.layers_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.layers_rev.set_transition_duration(120)
        self.layers_rev.set_child(self.layers_panel)
        self.layers_rev.set_reveal_child(False)
        body.append(self.layers_rev)

        # ---- status bar
        self.status = StatusBar(self)
        editor.append(self.status)

        # ---- overlays
        self.dialog_layer = Gtk.Box()
        self.dialog_layer.add_css_class("smoke")
        self.dialog_layer.set_visible(False)
        root.add_overlay(self.dialog_layer)
        self.flyouts = FlyoutLayer()
        self.flyouts.on_close.append(self._menus_closed)
        root.add_overlay(self.flyouts)

        # ---- input
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        ck = Gtk.EventControllerKey()
        self.im = Gtk.IMMulticontext()
        self.im.connect("commit", lambda _im, s: self.tools["text"].insert(s))
        ck.connect("key-pressed", self._canvas_key)
        self.canvas.add_controller(ck)
        self.canvas_keys = ck
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.set_gtypes([Gdk.FileList, Gdk.Texture])
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)
        press = Gtk.GestureClick()
        press.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        press.connect("pressed", self._canvas_pressed)
        self.canvas.add_controller(press)

    @staticmethod
    def _vsep():
        s = Gtk.Box()
        s.add_css_class("vsep")
        return s

    def _draw_caption(self, area, cr, w, h, name):
        c = area.get_color()
        cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
        cr.set_line_width(1.0)
        cx, cy = int(w / 2), int(h / 2) - 2
        if name == "minimize":
            cr.rectangle(cx - 4, cy, 10, 1)
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
            cr.move_to(cx - 5, cy - 5)
            cr.line_to(cx + 5, cy + 5)
            cr.move_to(cx + 5, cy - 5)
            cr.line_to(cx - 5, cy + 5)
            cr.stroke()

    def _sync_max(self):
        if self.is_maximized():
            self.add_css_class("maximized")
        else:
            self.remove_css_class("maximized")
        self.max_area.queue_draw()

    def _on_theme(self):
        self.queue_draw()
        self.canvas.queue_draw()
        self.ribbon.sync()

    # ================================================================== document events
    def _on_doc(self, kind, rect):
        if kind == "history":
            self._sync_title()
            self._sync_history()
        elif kind == "structure":
            self.layers_panel.rebuild()
            self.update_status()
            self.ribbon.sync()
        if kind in ("damage", "structure"):
            if self.layers_visible:
                self.layers_panel.refresh_thumbs()
            self.thumb.refresh()

    def _sync_title(self):
        name = util.display_name(self.path)
        t = ("*" if self.doc.modified else "") + _("%s - Paint") % name
        self.set_title(t)
        self.title_label.set_text(t)

    def _sync_history(self):
        tool = self.tool
        pending = tool.pending if tool else False
        self.undo_btn.set_sensitive(self.doc.history.can_undo() or pending)
        self.redo_btn.set_sensitive(self.doc.history.can_redo())

    # ================================================================== tools
    @property
    def tool(self):
        return self.tools.get(self.tool_name)

    def commit_tool(self):
        t = self.tool
        if t is not None:
            t.commit()

    def set_tool(self, name):
        if name not in self.tools:
            return
        if name != self.tool_name:
            self.commit_tool()
            if name == "picker":
                self.prev_tool = self.tool_name
            self.tool_name = name
            self.tool.activate()
        self.ribbon.sync()
        self.sliders.sync()
        self.canvas.queue_draw()
        self.canvas.set_cursor_from_name(self.tool.cursor)
        self.update_status()

    def restore_previous_tool(self):
        self.set_tool(self.prev_tool if self.prev_tool != "picker" else "pencil")

    def set_brush(self, bid):
        self.brush = bid
        self.set_tool("brush")
        self.ribbon.sync()

    def set_shape(self, sid):
        if self.tool_name == "shape":
            self.commit_tool()
        self.shape = sid
        self.set_tool("shape")
        self.ribbon.sync()

    def set_select_mode(self, mode):
        self.tools["select"].mode = mode
        self.set_tool("select")

    @property
    def size_key(self):
        n = self.tool_name
        if n in ("pencil", "eraser", "shape"):
            return n
        return "brush" if n == "brush" else "brush"

    def size_for(self, key):
        return self.sizes.get(key, 5)

    def set_size(self, v, from_slider=False):
        self.sizes[self.size_key] = max(1, int(round(v)))
        if not from_slider:
            self.sliders.sync()
        else:
            self._show_bubble(self.sliders.size, f"{self.sizes[self.size_key]}px")
        self.tool.refresh()

    def set_opacity(self, v, from_slider=False):
        self.opacity = max(0.01, min(1.0, v))
        if not from_slider:
            self.sliders.sync()
        else:
            self._show_bubble(self.sliders.opacity, f"{round(self.opacity * 100)}%")
        self.tool.refresh()

    def _show_bubble(self, slider, text):
        self.bubble.set_text(text)
        ok, b = slider.compute_bounds(self.workspace)
        if ok:
            f = slider.frac()
            y = b.get_y() + 10 + (1 - f) * (b.get_height() - 20)
            self.bubble.set_margin_start(int(b.get_x() + b.get_width() + 14))
            self.bubble.set_margin_top(max(0, int(y - 14)))
        self.bubble.set_visible(True)

    def hide_bubble(self):
        self.bubble.set_visible(False)

    def show_canvas_handles(self):
        return self.dialog is None and not self.is_fullscreen()

    # ================================================================== colours
    def set_primary(self, rgba):
        self.primary = tuple(rgba)
        self.ribbon.sync()
        self.tool.refresh()

    def set_secondary(self, rgba):
        self.secondary = tuple(rgba)
        self.ribbon.sync()
        self.tool.refresh()

    def set_active_slot(self, slot):
        self.active_slot = slot
        self.ribbon.sync()

    def set_active_color(self, rgba):
        if self.active_slot == 0:
            self.set_primary(rgba)
        else:
            self.set_secondary(rgba)

    def edit_colors(self):
        dlg = Gtk.ColorDialog()
        dlg.set_title(_("Edit colors"))
        dlg.set_with_alpha(False)
        cur = self.primary if self.active_slot == 0 else self.secondary
        c = Gdk.RGBA()
        c.red, c.green, c.blue, c.alpha = cur
        dlg.choose_rgba(self, c, None, self._color_chosen)

    def _color_chosen(self, dlg, res):
        try:
            c = dlg.choose_rgba_finish(res)
        except GLib.Error:
            return
        self.add_custom_color((c.red, c.green, c.blue, 1.0))

    def add_custom_color(self, rgba):
        hx = rgba_hex(rgba)
        cols = [x for x in self.custom_colors if x != hx]
        cols.insert(0, hx)
        self.custom_colors = cols[:10]
        util.opts().set("custom_colors", self.custom_colors)
        self.ribbon.refresh_custom()
        self.set_active_color(rgba)

    # ================================================================== text
    def show_text_bar(self, on):
        self.textbar_rev.set_reveal_child(on)
        if on:
            self.canvas_keys.set_im_context(self.im)
            self.im.set_client_widget(self.canvas)
            self.im.focus_in()
        else:
            self.im.focus_out()
            self.canvas_keys.set_im_context(None)

    def set_text_prop(self, key, value):
        if self.text_props.get(key) == value:
            return
        self.text_props[key] = value
        self.tools["text"].refresh()
        self.canvas.grab_focus()

    def toggle_text_prop(self, key):
        self.set_text_prop(key, not self.text_props[key])
        self.textbar.sync()

    # ================================================================== status
    def update_status(self, selection=None, resize=None):
        p = self.canvas.pointer
        doc = self.doc
        if p is not None and 0 <= p[0] < doc.width and 0 <= p[1] < doc.height:
            self.status.pos.set_text(_("%d, %dpx") % (int(p[0]), int(p[1])))
        else:
            self.status.pos.set_text("")
        sel = selection
        if sel is None:
            st = self.tools["select"]
            if st.sel is not None:
                sel = st.sel.box
            elif self.tool_name == "shape" and self.tools["shape"].s is not None:
                sel = self.tools["shape"].s["box"]
        if sel is not None:
            w, h = abs(round(sel[2] - sel[0])), abs(round(sel[3] - sel[1]))
            self.status.sel.set_text(_("%d × %dpx") % (w, h))
        else:
            self.status.sel.set_text("")
        cw, ch = resize if resize else (doc.width, doc.height)
        self.status.size.set_text(_("%d × %dpx") % (cw, ch))
        self.hruler.queue_draw() if self.hruler.get_visible() else None
        self.vruler.queue_draw() if self.vruler.get_visible() else None

    def on_zoom_changed(self):
        self.status.set_zoom(self.canvas.zoom)
        self.hruler.queue_draw()
        self.vruler.queue_draw()

    def _scrolled(self):
        self.canvas.queue_draw()
        if self.hruler.get_visible():
            self.hruler.queue_draw()
            self.vruler.queue_draw()

    def on_selection_changed(self):
        self.ribbon.sync()
        self.update_status()
        self._sync_history()
        self.canvas.queue_draw()

    def notify(self, text):
        self.toast.show(text)

    def zoom_fit(self):
        self.canvas.set_zoom(self.canvas.fit_zoom())

    # ================================================================== menus
    def open_menu(self, key):
        self.commit_tool_soft()
        b = self.menu_buttons[key]
        b.add_css_class("open")
        m = getattr(self, f"_{key}_menu")()
        popup_menu(self, m, b, dy=-3)

    def commit_tool_soft(self):
        pass

    def _menus_closed(self):
        for b in self.menu_buttons.values():
            b.remove_css_class("open")

    def _file_menu(self):
        m = Menu(self, width=262)
        m.add(_("New"), self.new, "new", _("Ctrl+N"))
        m.add(_("Open"), self.open_dialog, "open", _("Ctrl+O"))
        m.add(_("Import to canvas"), icon_name="import", submenu=self._import_menu)
        recent = [p for p in util.opts()["recent"] if os.path.exists(p)]
        m.add(_("Recent"), icon_name="recent", submenu=self._recent_menu, sensitive=bool(recent))
        m.add(_("Save"), self.save, "save", _("Ctrl+S"))
        m.add(_("Save as"), icon_name="saveas", submenu=self._save_as_menu)
        m.add_separator()
        m.add(_("Print"), icon_name="print", submenu=self._print_menu)
        m.add_separator()
        m.add(_("Set as desktop background"), icon_name="wallpaper", submenu=self._wallpaper_menu)
        m.add_separator()
        m.add(_("Image properties"), self.properties_dialog, "props", _("Ctrl+E"))
        m.add_separator()
        m.add(_("Exit"), self.close, "exit")
        return m

    def _import_menu(self, level):
        m = Menu(self, level, width=200)
        m.add(_("From a file"), self.import_dialog, "picture")
        return m

    def _recent_menu(self, level):
        m = Menu(self, level, width=320)
        for p in [p for p in util.opts()["recent"] if os.path.exists(p)][:10]:
            m.add(os.path.basename(p), lambda p=p: self.confirm_then(lambda: self.open_path(p)), "picture")
        return m

    def _save_as_menu(self, level):
        m = Menu(self, level, width=220)
        for f in fileio.save_formats():
            m.add(_(f[1]), lambda f=f: self.save_as(f), "picture")
        return m

    def _print_menu(self, level):
        m = Menu(self, level, width=200)
        m.add(_("Print"), self.print_image, "print", _("Ctrl+P"))
        m.add(_("Page setup"), self.page_setup_dialog, "page-setup")
        return m

    def _wallpaper_menu(self, level):
        m = Menu(self, level, width=160)
        for opt, text in (("zoom", _("Fill")), ("wallpaper", _("Tile")), ("centered", _("Center"))):
            m.add(_(text), lambda opt=opt: self.set_wallpaper(opt))
        return m

    def _edit_menu(self):
        st = self.tools["select"]
        m = Menu(self, width=262)
        m.add(_("Cut"), self.cut, "cut", _("Ctrl+X"))
        m.add(_("Copy"), self.copy, "copy", _("Ctrl+C"))
        m.add(_("Paste"), self.paste, "paste", _("Ctrl+V"), sensitive=self.can_paste())
        m.add_separator()
        m.add(_("Copy visible layers"), self.copy_visible, "copy-layers", _("Ctrl+Shift+C"))
        return m

    def _view_menu(self):
        o = util.opts()
        m = Menu(self, width=240)
        m.add(_("Zoom"), icon_name="zoom", submenu=self._zoom_menu)
        m.add_separator()
        m.add(_("Rulers"), lambda: self.toggle_option("rulers"), check=o["rulers"], shortcut=_("Ctrl+R"))
        m.add(_("Gridlines"), lambda: self.toggle_option("gridlines"), check=o["gridlines"], shortcut=_("Ctrl+G"))
        m.add(_("Status bar"), lambda: self.toggle_option("statusbar"), check=o["statusbar"])
        m.add_separator()
        m.add(_("Always show toolbar"), lambda: self.set_autohide(False), check=not o["autohide_toolbar"])
        m.add(_("Automatically hide toolbar"), lambda: self.set_autohide(True), check=o["autohide_toolbar"])
        m.add_separator()
        m.add(_("Full screen"), self.toggle_fullscreen, "full-screen", _("F11"))
        m.add(_("Thumbnail"), lambda: self.set_thumbnail(not self.thumb.get_visible()), "thumbnail")
        return m

    def _zoom_menu(self, level):
        m = Menu(self, level, width=230)
        m.add(_("Zoom in"), lambda: self.canvas.zoom_step(1), "zoom-in", _("Ctrl+Plus"))
        m.add(_("Zoom out"), lambda: self.canvas.zoom_step(-1), "zoom-out", _("Ctrl+Minus"))
        m.add(_("Fit to window"), self.zoom_fit, "fit", _("Ctrl+0"))
        m.add(_("Actual size"), lambda: self.canvas.set_zoom(1.0), "actual-size", _("Ctrl+1"))
        return m

    def selection_menu(self, anchor):
        st = self.tools["select"]
        m = Menu(self, width=208)
        m.add(_("Rectangle"), lambda: self.set_select_mode("rect"), "rect-select",
              selected=st.mode == "rect")
        m.add(_("Free-form"), lambda: self.set_select_mode("free"), "lasso", selected=st.mode == "free")
        m.add_separator()
        m.add(_("Select all"), self.select_all, "select-all", _("Ctrl+A"))
        m.add(_("Invert selection"), self.invert_selection, "invert-sel", sensitive=st.has_selection)
        m.add(_("Transparent selection"), self.toggle_transparent, check=self.transparent_selection)
        m.add(_("Delete"), self.delete_selection, "delete", _("Delete"), sensitive=st.has_selection)
        popup_menu(self, m, anchor, dy=2)

    def rotate_menu(self, anchor):
        m = Menu(self, width=156)
        m.add(_("Rotate right 90°"), lambda: self.rotate("rot90"), "rotate-right")
        m.add(_("Rotate left 90°"), lambda: self.rotate("rot270"), "rotate-left")
        m.add(_("Rotate 180°"), lambda: self.rotate("rot180"), "rotate-180")
        m.add(_("Rotate custom"), self.rotate_custom_dialog, "rotate-custom")
        popup_menu(self, m, anchor, dx=-80, dy=2)

    def flip_menu(self, anchor):
        m = Menu(self, width=156)
        m.add(_("Flip vertical"), lambda: self.flip("flip_v"), "flip-v")
        m.add(_("Flip horizontal"), lambda: self.flip("flip_h"), "flip-h")
        popup_menu(self, m, anchor, dx=-80, dy=2)

    def brushes_menu(self, anchor):
        brushes_menu(self, anchor)

    def outline_menu(self, anchor):
        style_menu(self, anchor, OUTLINES, self.outline_style, self._set_outline)

    def fill_menu(self, anchor):
        style_menu(self, anchor, FILLS, self.fill_style, self._set_fill)

    def _set_outline(self, s):
        self.outline_style = s
        self.tool.refresh()

    def _set_fill(self, s):
        self.fill_style = s
        self.tool.refresh()

    def size_menu(self, anchor):
        size_menu(self, anchor)

    # ================================================================== view options
    def toggle_option(self, key):
        o = util.opts()
        o.set(key, not o[key])
        self._apply_view_options()

    def _apply_view_options(self):
        o = util.opts()
        r = o["rulers"]
        for w in (self.hruler, self.vruler, self.corner):
            w.set_visible(r)
        self.canvas.gridlines = o["gridlines"]
        self.canvas.queue_draw()
        self.status.set_visible(o["statusbar"] and not self.is_fullscreen())
        self.ribbon_rev.set_reveal_child((not o["autohide_toolbar"] or self.toolbar_peek) and not self.is_fullscreen())
        self.show_tb_btn.set_visible(o["autohide_toolbar"] and not self.toolbar_peek)
        self.thumb.set_visible(o["thumbnail"])

    def set_autohide(self, on):
        util.opts().set("autohide_toolbar", on)
        self.toolbar_peek = False
        self._apply_view_options()

    def _peek_toolbar(self):
        self.toolbar_peek = True
        self._apply_view_options()

    def _canvas_pressed(self, *_a):
        if self.toolbar_peek:
            self.toolbar_peek = False
            self._apply_view_options()

    def set_thumbnail(self, on):
        util.opts().set("thumbnail", on)
        self._apply_view_options()
        self.thumb.refresh()

    def toggle_fullscreen(self):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    def _sync_fullscreen(self):
        fs = self.is_fullscreen()
        self.menubar.set_visible(not fs)
        self.sliders.set_visible(not fs)
        self._apply_view_options()
        self.canvas.queue_draw()

    def toggle_layers(self):
        self.layers_visible = not self.layers_visible
        self.layers_rev.set_reveal_child(self.layers_visible)
        if self.layers_visible:
            self.layers_panel.rebuild()
        self.ribbon.sync()

    def select_layer(self, idx):
        self.commit_tool()
        self.doc.set_active(idx)

    # ================================================================== settings
    def open_settings(self):
        self.commit_tool()
        if self.settings_page is None:
            self.settings_page = SettingsPage(self)
            self.stack.add_named(self.settings_page, "settings")
        self.settings_page.sync()
        self.stack.set_visible_child_name("settings")

    def close_settings(self):
        self.stack.set_visible_child_name("editor")

    def set_app_theme(self, key):
        util.opts().set("theme", key)
        theme.get().override = None if key == "system" else key
        theme.get().apply()

    # ================================================================== dialogs
    def show_dialog(self, d):
        self.flyouts.close_all()
        if self.dialog is not None:
            self.hide_dialog(self.dialog)
        self.dialog = d
        self.dialog_layer.append(d)
        self.dialog_layer.set_visible(True)
        d.set_hexpand(True)
        d.set_vexpand(True)
        self.canvas.queue_draw()

    def hide_dialog(self, d):
        if d.get_parent() is self.dialog_layer:
            self.dialog_layer.remove(d)
        if self.dialog is d:
            self.dialog = None
        self.dialog_layer.set_visible(self.dialog is not None)
        self.canvas.queue_draw()
        self.canvas.grab_focus()

    def confirm_then(self, action):
        """Run action, asking to save unsaved changes first (Save / Don't save / Cancel)."""
        self.commit_tool()
        if not self.doc.modified:
            action()
            return

        def do_save():
            self.save(after=action)
        dialogs.unsaved(self, do_save, action)

    # ================================================================== keyboard
    def _canvas_key(self, _c, keyval, _code, state):
        t = self.tool
        if t is not None and self.dialog is None and t.key(keyval, state):
            self.canvas.queue_draw()
            self._sync_history()
            return True
        return False

    def _on_key(self, _c, keyval, _code, state):
        if self.flyouts.is_open:
            if keyval == Gdk.KEY_Escape:
                self.flyouts.close_all()
                return True
            return False
        if self.dialog is not None:
            return False
        c = bool(state & Gdk.ModifierType.CONTROL_MASK)
        s = bool(state & Gdk.ModifierType.SHIFT_MASK)
        k = Gdk.keyval_to_lower(keyval)
        if self.stack.get_visible_child_name() == "settings":
            if keyval == Gdk.KEY_Escape:
                self.close_settings()
                return True
            return False
        if c:
            table = {
                Gdk.KEY_n: self.new, Gdk.KEY_o: self.open_dialog, Gdk.KEY_p: self.print_image,
                Gdk.KEY_e: self.properties_dialog, Gdk.KEY_w: self.resize_dialog, Gdk.KEY_z: self.undo,
                Gdk.KEY_y: self.redo, Gdk.KEY_x: self.cut, Gdk.KEY_v: self.paste, Gdk.KEY_a: self.select_all,
                Gdk.KEY_r: lambda: self.toggle_option("rulers"), Gdk.KEY_g: lambda: self.toggle_option("gridlines"),
                Gdk.KEY_s: self.save, Gdk.KEY_c: self.copy,
                Gdk.KEY_plus: lambda: self.canvas.zoom_step(1), Gdk.KEY_equal: lambda: self.canvas.zoom_step(1),
                Gdk.KEY_KP_Add: lambda: self.canvas.zoom_step(1), Gdk.KEY_minus: lambda: self.canvas.zoom_step(-1),
                Gdk.KEY_KP_Subtract: lambda: self.canvas.zoom_step(-1), Gdk.KEY_0: self.zoom_fit,
                Gdk.KEY_1: lambda: self.canvas.set_zoom(1.0),
                Gdk.KEY_Page_Up: lambda: self.canvas.zoom_step(1), Gdk.KEY_Page_Down: lambda: self.canvas.zoom_step(-1),
            }
            shifted = {Gdk.KEY_z: self.redo, Gdk.KEY_c: self.copy_visible, Gdk.KEY_x: self.crop,
                       Gdk.KEY_i: self.invert_colors, Gdk.KEY_s: lambda: self.save_as(fileio.FORMATS[0]),
                       Gdk.KEY_n: lambda: self.doc.add_layer()}
            fn = (shifted.get(k) if s else None) or table.get(k)
            if fn is not None:
                fn()
                return True
            return False
        if keyval == Gdk.KEY_F11:
            self.toggle_fullscreen()
            return True
        if keyval == Gdk.KEY_Escape and self.is_fullscreen():
            self.unfullscreen()
            return True
        if keyval == Gdk.KEY_Delete and self.tools["select"].has_selection and self.tool_name == "select":
            self.delete_selection()
            return True
        if keyval == Gdk.KEY_Escape:
            self.commit_tool()
            self.canvas.queue_draw()
            return True
        return False

    # ================================================================== history / clipboard
    def undo(self):
        t = self.tool
        if t is not None and t.pending:
            t.cancel()
        elif self.tools["select"].sel is not None and self.tool_name == "select":
            self.tools["select"].commit()
            self.doc.history.undo()
        else:
            self.doc.history.undo()
        self.canvas.queue_draw()
        self._sync_history()

    def redo(self):
        self.commit_tool()
        self.doc.history.redo()
        self.canvas.queue_draw()

    def _selection_content(self):
        st = self.tools["select"]
        return st.content() if st.has_selection else None

    def _set_clipboard(self, surf):
        self.clip_surface = surf
        try:
            self.get_clipboard().set_texture(raster.texture_from_surface(surf))
        except Exception:  # noqa: BLE001 - clipboard may be unavailable (headless)
            pass

    def can_paste(self):
        if self.clip_surface is not None:
            return True
        f = self.get_clipboard().get_formats()
        return bool(f.contain_gtype(Gdk.Texture) or f.contain_gtype(Gdk.FileList)
                    or any(m.startswith("image/") for m in (f.get_mime_types() or [])))

    def copy(self):
        """Copy the selection (or, without one, the whole active layer)."""
        surf = self._selection_content()
        if surf is None:
            self.commit_tool()
            surf = raster.copy_surface(self.doc.layer.surface)
        self._set_clipboard(surf)

    def cut(self):
        st = self.tools["select"]
        if not st.has_selection:
            self.commit_tool()
            self._set_clipboard(raster.copy_surface(self.doc.layer.surface))
            self.doc.modify_layer((0, 0, self.doc.width, self.doc.height),
                                  lambda cr: (cr.set_operator(cairo.OPERATOR_CLEAR), cr.paint()), _("Cut"))
            return
        surf = self._selection_content()
        if surf is not None:
            self._set_clipboard(surf)
            st.delete()

    def copy_visible(self):
        st = self.tools["select"]
        flat = self.doc.flatten()
        if st.has_selection:
            r = raster.clip_rect(st.sel.rect, self.doc.width, self.doc.height)
            if r is not None:
                flat = raster.copy_surface(flat, *r)
        self._set_clipboard(flat)

    def paste(self):
        cb = self.get_clipboard()
        formats = cb.get_formats()
        if formats.contain_gtype(Gdk.Texture) or any(m.startswith("image/") for m in (formats.get_mime_types() or [])):
            cb.read_texture_async(None, self._paste_done)
        elif formats.contain_gtype(Gdk.FileList) or formats.contain_mime_type("text/uri-list"):
            cb.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, self._paste_files)
        elif self.clip_surface is not None:
            self.paste_surface(raster.copy_surface(self.clip_surface))

    def _paste_done(self, cb, res):
        try:
            tex = cb.read_texture_finish(res)
        except GLib.Error:
            tex = None
        if tex is not None:
            self.paste_surface(raster.surface_from_texture(tex))
        elif self.clip_surface is not None:
            self.paste_surface(raster.copy_surface(self.clip_surface))

    def _paste_files(self, cb, res):
        try:
            fl = cb.read_value_finish(res)
        except GLib.Error:
            return
        for f in fl.get_files() if fl else []:
            p = f.get_path()
            if p:
                try:
                    self.paste_surface(fileio.load(p))
                except GLib.Error:
                    pass
                return

    def paste_surface(self, surf):
        self.commit_tool()
        doc = self.doc
        sw, sh = surf.get_width(), surf.get_height()
        if sw > doc.width or sh > doc.height:
            doc.resize_canvas(max(sw, doc.width), max(sh, doc.height), 0, 0, _("Paste"))
            x, y = 0, 0
        else:
            x, y = self.canvas.visible_img_origin()
            x, y = min(x, doc.width - sw), min(y, doc.height - sh)
        self.set_tool("select")
        self.tools["select"].float_surface(surf, x, y)

    def _on_drop(self, _t, value, _x, _y):
        if isinstance(value, Gdk.Texture):
            self.paste_surface(raster.surface_from_texture(value))
            return True
        files = value.get_files() if value is not None else []
        for f in files:
            p = f.get_path()
            if p:
                self.confirm_then(lambda p=p: self.open_path(p))
                return True
        return False

    # ================================================================== selection ops
    def select_all(self):
        self.set_tool("select")
        self.tools["select"].select_all()

    def invert_selection(self):
        self.tools["select"].invert()

    def toggle_transparent(self):
        self.transparent_selection = not self.transparent_selection
        st = self.tools["select"]
        if st.sel is not None and st.sel.floating is not None and self.transparent_selection:
            st.transform_floating(lambda s: raster.key_out(s, self.secondary))

    def delete_selection(self):
        self.tools["select"].delete()

    def _with_selection(self):
        st = self.tools["select"]
        return st if st.has_selection else None

    def crop(self):
        st = self._with_selection()
        if st is None:
            return
        sel = st.sel
        if sel.floating is not None:
            st.commit()
            r = raster.clip_rect(sel.rect, self.doc.width, self.doc.height)
            mask = None
        else:
            st.sel = None
            r = raster.clip_rect(sel.rect, self.doc.width, self.doc.height)
            mask = sel.mask if sel.kind == "free" else None
        if r is None:
            self.on_selection_changed()
            return
        x, y, w, h = r

        def fn(s):
            out = raster.copy_surface(s, x, y, w, h)
            if mask is not None:
                cr = cairo.Context(out)
                cr.set_operator(cairo.OPERATOR_DEST_IN)
                cr.mask_surface(mask, sel.rect[0] - x, sel.rect[1] - y)
                out.flush()
            return out
        self.doc.map_layers(fn, _("Crop"))
        self.on_selection_changed()

    def rotate(self, op):
        st = self._with_selection()
        if st is not None:
            st.transform_floating(lambda s: raster.transformed(s, op))
            return
        self.commit_tool()
        self.doc.map_layers(lambda s: raster.transformed(s, op), _("Rotate"))

    def flip(self, op):
        self.rotate(op)

    def rotate_custom_dialog(self):
        def apply(deg):
            if abs(deg) < 1e-6:
                return
            st = self._with_selection()
            if st is not None:
                st.transform_floating(lambda s: raster.rotated(s, deg))
            else:
                self.commit_tool()
                self.doc.map_layers(lambda s: raster.rotated(s, deg), _("Rotate"))
        dialogs.rotate_custom(self, apply)

    def resize_dialog(self):
        st = self._with_selection()
        if st is not None:
            r = st.sel.rect
            w, h = r[2], r[3]
        else:
            self.commit_tool()
            w, h = self.doc.width, self.doc.height

        def apply(nw, nh, sx, sy):
            def fn(s):
                out = s
                if (nw, nh) != (s.get_width(), s.get_height()):
                    out = raster.scaled(out, nw, nh)
                if sx or sy:
                    out = raster.skewed(out, sx, sy)
                return out
            st2 = self._with_selection()
            if st2 is not None:
                st2.transform_floating(fn)
            else:
                self.doc.map_layers(fn, _("Resize"))
        dialogs.resize_skew(self, w, h, apply)

    def invert_colors(self):
        st = self._with_selection()
        if st is not None:
            def inv(s):
                out = raster.copy_surface(s)
                raster.invert_colors(out)
                return out
            st.transform_floating(inv)
            return
        self.commit_tool()
        layer = self.doc.layer
        self.doc.modify_layer((0, 0, self.doc.width, self.doc.height),
                              lambda cr: self._invert_into(cr, layer), _("Invert colors"))

    @staticmethod
    def _invert_into(cr, layer):
        tmp = raster.copy_surface(layer.surface)
        raster.invert_colors(tmp)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_surface(tmp, 0, 0)
        cr.paint()

    def properties_dialog(self):
        self.commit_tool()

        def apply(w, h, bw):
            if (w, h) != (self.doc.width, self.doc.height):
                self.doc.resize_canvas(w, h, 0, 0)
            if bw:
                self.doc.map_layers(raster.to_black_white, _("Black and white"))
        dialogs.properties(self, apply)

    # ================================================================== files
    def _reset(self, surface=None, path=None):
        self.tools["select"].sel = None
        for t in self.tools.values():
            if t.pending:
                t.cancel()
        if surface is None:
            surface = raster.new_surface(DEFAULT_W, DEFAULT_H)
            self.doc.replace_all(surface)
            self.doc.bg_visible = True
        else:
            self.doc.replace_all(surface)
            # transparent images start with the background hidden (checkerboard)
            a = surface.get_data()[3::4] if surface.get_stride() == surface.get_width() * 4 else b"\xff"
            self.doc.bg_visible = min(a) == 255 if len(a) else True
            if not self.doc.bg_visible:
                self.doc.damage()
        self.path = path
        self.fmt = fileio.format_for_path(path) if path else None
        self.doc.notify("structure")
        self._sync_title()
        self._sync_history()
        GLib.idle_add(lambda: (self._initial_zoom(), False)[1])

    def _initial_zoom(self):
        # A new blank canvas opens at 100 % showing its top-left corner; images are fitted.
        fz = 1.0 if self.path is None else self.canvas.fit_zoom()
        self.canvas.set_zoom(min(1.0, fz))
        self.canvas.show_origin()
        self.status.set_zoom(self.canvas.zoom)

    def new(self):
        self.confirm_then(lambda: self._reset())

    def open_dialog(self):
        def run():
            dlg = Gtk.FileDialog()
            dlg.set_title(_("Open"))
            filters = Gio.ListStore.new(Gtk.FileFilter)
            f = Gtk.FileFilter()
            f.set_name(_("All picture files"))
            for mt in fileio.OPEN_MIME:
                f.add_mime_type(mt)
            for ext in fileio.OPEN_EXT:
                f.add_suffix(ext)
            filters.append(f)
            dlg.set_filters(filters)
            dlg.set_default_filter(f)
            dlg.open(self, None, self._open_done)
        self.confirm_then(run)

    def _open_done(self, dlg, res):
        try:
            gf = dlg.open_finish(res)
        except GLib.Error:
            return
        if gf is not None and gf.get_path():
            self.open_path(gf.get_path())

    def open_path(self, path):
        try:
            surf = fileio.load(path)
        except (GLib.Error, OSError) as e:
            dialogs.message(self, _("Paint"), _("Paint cannot read this file.") + "\n" + str(getattr(e, "message", e)))
            return False
        self._reset(surf, path)
        util.opts().add_recent(os.path.abspath(path))
        return True

    def import_dialog(self):
        dlg = Gtk.FileDialog()
        dlg.set_title(_("Import to canvas"))
        dlg.open(self, None, self._import_done)

    def _import_done(self, dlg, res):
        try:
            gf = dlg.open_finish(res)
        except GLib.Error:
            return
        if gf is not None and gf.get_path():
            self.import_path(gf.get_path())

    def import_path(self, path):
        try:
            self.paste_surface(fileio.load(path))
        except (GLib.Error, OSError):
            dialogs.message(self, _("Paint"), _("Paint cannot read this file."))

    def save(self, after=None):
        self.commit_tool()
        if self.path and self.fmt is not None:
            if self.save_to(self.path, self.fmt) and after:
                after()
            return
        self.save_as(fileio.FORMATS[0], after)

    def save_as(self, fmt, after=None):
        self.commit_tool()
        dlg = Gtk.FileDialog()
        dlg.set_title(_("Save as"))
        base = os.path.splitext(util.display_name(self.path))[0]
        dlg.set_initial_name(f"{base}.{fmt[2][0]}")
        if self.path:
            dlg.set_initial_folder(Gio.File.new_for_path(os.path.dirname(self.path)))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter()
        f.set_name(_(fmt[1]))
        for ext in fmt[2]:
            f.add_suffix(ext)
        filters.append(f)
        dlg.set_filters(filters)

        def done(d, res):
            try:
                gf = d.save_finish(res)
            except GLib.Error:
                return
            p = gf.get_path() if gf else None
            if not p:
                return
            if not os.path.splitext(p)[1]:
                p += "." + fmt[2][0]
            if self.save_to(p, fileio.format_for_path(p) or fmt) and after:
                after()
        dlg.save(self, None, done)

    def save_to(self, path, fmt):
        try:
            fileio.save(self.doc.flatten(), path, fmt)
        except (GLib.Error, OSError) as e:
            dialogs.message(self, _("Paint"), _("Paint cannot save this file.") + "\n" + str(getattr(e, "message", e)))
            return False
        self.path = path
        self.fmt = fmt
        self.doc.mark_saved()
        util.opts().add_recent(os.path.abspath(path))
        self._sync_title()
        return True

    def set_wallpaper(self, option):
        self.commit_tool()
        if self.path and not self.doc.modified and self.fmt and self.fmt[0] in ("png", "jpeg", "bmp", "webp", "tiff"):
            path = self.path
        else:
            path = fileio.wallpaper_copy(self.doc.flatten())
        if fileio.set_wallpaper(path, option):
            self.notify(_("Desktop background set."))
        else:
            self.notify(_("The desktop background could not be changed."))
        return path

    # ---- printing
    def _print_op(self):
        op = Gtk.PrintOperation()
        op.set_n_pages(1)
        op.set_job_name(util.display_name(self.path))
        op.set_embed_page_setup(True)
        if self.page_setup is not None:
            op.set_default_page_setup(self.page_setup)
        if self.print_settings is not None:
            op.set_print_settings(self.print_settings)
        flat = self.doc.flatten()

        def draw(_op, ctx, _n):
            cr = ctx.get_cairo_context()
            pw, ph = ctx.get_width(), ctx.get_height()
            iw, ih = flat.get_width(), flat.get_height()
            dpi = ctx.get_dpi_x() or 96
            s = min(pw / iw, ph / ih, dpi / 96)
            cr.translate((pw - iw * s) / 2, 0)
            cr.scale(s, s)
            cr.set_source_surface(flat, 0, 0)
            cr.paint()
        op.connect("draw-page", draw)
        return op

    def print_image(self):
        self.commit_tool()
        op = self._print_op()
        try:
            res = op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self)
        except GLib.Error as e:
            dialogs.message(self, _("Paint"), str(e.message))
            return
        if res == Gtk.PrintOperationResult.APPLY:
            self.print_settings = op.get_print_settings()

    def page_setup_dialog(self):
        self.page_setup = Gtk.print_run_page_setup_dialog(self, self.page_setup, self.print_settings or
                                                          Gtk.PrintSettings())

    # ================================================================== closing
    def _close_request(self, *_a):
        if getattr(self, "_closing", False):
            return False
        self.commit_tool()
        if not self.doc.modified:
            return False

        def discard():
            self._closing = True
            self.close()

        def do_save():
            self.save(after=discard)
        dialogs.unsaved(self, do_save, discard)
        return True



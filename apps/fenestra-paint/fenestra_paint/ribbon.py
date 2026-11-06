"""The toolbar ("ribbon"): Selection, Image, Tools, Brushes, Shapes, Colors and Layers
groups, plus the floating text-formatting bar shown while the Text tool is active."""
from __future__ import annotations

import gi

gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, PangoCairo  # noqa: E402

from . import brushes, shapes, theme  # noqa: E402
from .i18n import _  # noqa: E402
from .widgets import (ColorWheel, Glyph, Menu, Swatch, button, icon, label, popup_menu,  # noqa: E402
                      surface_picture, tinted_icon)

PALETTE = [
    "#000000", "#7f7f7f", "#880015", "#ed1c24", "#ff7f27", "#fff200", "#22b14c", "#00a2e8", "#3f48cc", "#a349a4",
    "#ffffff", "#c3c3c3", "#b97a57", "#ffaec9", "#ffc90e", "#efe4b0", "#b5e61d", "#99d9ea", "#7092be", "#c8bfe7",
]


def hex_rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 1.0)


def rgba_hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c[:3])


def _dashed_rect(cr, w, h, th):
    cr.set_line_width(1.3)
    cr.set_dash([3, 2])
    cr.rectangle(1.5, 2.5, w - 3, h - 5)
    cr.stroke()


def _letter_a(cr, w, h, th):
    cr.set_line_width(1.1)
    cr.move_to(1.5, h - 1.5)
    cr.line_to(w / 2, 1.5)
    cr.line_to(w - 1.5, h - 1.5)
    cr.move_to(4.6, h - 6.5)
    cr.line_to(w - 4.6, h - 6.5)
    cr.stroke()


def _chevron(cr, w, h, th):
    cr.set_line_width(1)
    cr.move_to(w / 2 - 4, h / 2 - 2)
    cr.line_to(w / 2, h / 2 + 2)
    cr.line_to(w / 2 + 4, h / 2 - 2)
    cr.stroke()


def chevron(w=12, h=10):
    g = Glyph(_chevron, w, h)
    g.add_css_class("chev")
    return g


class Group(Gtk.Box):
    def __init__(self, title, content, width, last=False, start=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("rgroup")
        self.set_hexpand(False)
        if last:
            self.add_css_class("last")
        self.set_size_request(width, -1)
        wrap = Gtk.Box()
        wrap.set_vexpand(True)
        content.set_valign(Gtk.Align.CENTER)
        if start is None:
            content.set_halign(Gtk.Align.CENTER)
            content.set_hexpand(True)
        else:  # measured offset from the group's left edge
            content.set_halign(Gtk.Align.START)
            content.set_margin_start(start)
        wrap.append(content)
        self.append(wrap)
        self.append(label(title, "rgroup-label", xalign=0.5))


class Ribbon(Gtk.Box):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.add_css_class("ribbon")
        self.set_vexpand(False)
        self.tool_buttons = {}
        self.shape_buttons = {}
        self._build()
        theme.get().connect(self._theme_changed)

    # ------------------------------------------------------------------ build
    def _tool_btn(self, name, child, tip):
        b = button(child, "tool-button", tooltip=tip, cb=lambda: self.win.set_tool(name))
        self.tool_buttons[name] = b
        return b

    def _build(self):
        w = self.win
        # ---- Selection
        sel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sel.add_css_class("split-v")
        self.sel_glyph = Gtk.Stack()
        self.sel_glyph.add_named(Glyph(_dashed_rect, 24, 26), "rect")
        self.sel_glyph.add_named(icon("lasso", 22), "free")
        self.sel_main = button(self.sel_glyph, "big-button", "split-top", tooltip=_("Selection"),
                               cb=lambda: w.set_tool("select"))
        self.sel_drop = button(chevron(), "split-bottom", tooltip=_("Selection options"),
                               cb=lambda: w.selection_menu(self.sel_drop))
        sel.append(self.sel_main)
        sel.append(self.sel_drop)
        self.sel_box = sel
        self.append(Group(_("Selection"), sel, 75))

        # ---- Image
        img = Gtk.Grid(column_spacing=0, row_spacing=8)
        self.crop_btn = button(tinted_icon("crop", "grey"), "tool-button", tooltip=_("Crop (Ctrl+Shift+X)"),
                               cb=w.crop)
        img.attach(self.crop_btn, 0, 0, 1, 1)
        self.invert_btn = button(icon("invert-colors", 20), "tool-button", tooltip=_("Invert colors (Ctrl+Shift+I)"),
                                 cb=w.invert_colors)
        img.attach(self.invert_btn, 0, 1, 1, 1)
        rot = Gtk.Box()
        rot.append(button(tinted_icon("rotate", "blue"), "tool-button", "half-left",
                          tooltip=_("Rotate right 90°"), cb=lambda: w.rotate("rot90")))
        self.rot_drop = button(chevron(10, 10), "drop-button", tooltip=_("Rotate"),
                               cb=lambda: w.rotate_menu(self.rot_drop))
        rot.append(self.rot_drop)
        img.attach(rot, 1, 0, 1, 1)
        flip = Gtk.Box()
        flip.append(button(tinted_icon("flip", "blue"), "tool-button", "half-left",
                           tooltip=_("Flip vertical"), cb=lambda: w.flip("flip_v")))
        self.flip_drop = button(chevron(10, 10), "drop-button", tooltip=_("Flip"),
                                cb=lambda: w.flip_menu(self.flip_drop))
        flip.append(self.flip_drop)
        img.attach(flip, 1, 1, 1, 1)
        rs = button(icon("resize", 28, "blue-glyph"), "big-button", "resize-button",
                    tooltip=_("Resize and skew (Ctrl+W)"), cb=w.resize_dialog)
        rs.set_valign(Gtk.Align.CENTER)
        img.attach(rs, 2, 0, 1, 2)
        self.append(Group(_("Image"), img, 159, start=8))

        # ---- Tools
        tg = Gtk.Grid(column_spacing=0, row_spacing=8)
        tg.attach(self._tool_btn("pencil", tinted_icon("pencil", "yellow"), _("Pencil")), 0, 0, 1, 1)
        tg.attach(self._tool_btn("fill", tinted_icon("bucket", "blue"), _("Fill")), 1, 0, 1, 1)
        tg.attach(self._tool_btn("text", Glyph(_letter_a, 16, 18), _("Text")), 2, 0, 1, 1)
        tg.attach(self._tool_btn("eraser", tinted_icon("eraser", "pink"), _("Eraser")), 0, 1, 1, 1)
        tg.attach(self._tool_btn("picker", tinted_icon("picker", "blue"), _("Color picker")), 1, 1, 1, 1)
        tg.attach(self._tool_btn("magnifier", icon("magnifier", 20), _("Magnifier")), 2, 1, 1, 1)
        self.append(Group(_("Tools"), tg, 137))

        # ---- Brushes
        bb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bb.add_css_class("split-v")
        bb.add_css_class("brush-split")
        self.brush_main = button(tinted_icon("brush", "grey", 24), "split-top", tooltip=_("Brushes"),
                                 cb=lambda: w.set_tool("brush"))
        self.brush_drop = button(chevron(), "split-bottom", tooltip=_("Brushes"),
                                 cb=lambda: w.brushes_menu(self.brush_drop))
        bb.append(self.brush_main)
        bb.append(self.brush_drop)
        self.brush_box = bb
        self.append(Group(_("Brushes"), bb, 68))

        # ---- Shapes
        sh = Gtk.Box(spacing=0)
        gal = Gtk.ScrolledWindow()
        gal.add_css_class("shape-gallery")
        gal.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        gal.set_overlay_scrolling(True)
        gal.set_size_request(175, 80)
        gal.set_propagate_natural_height(False)
        gal.set_max_content_height(78)
        grid = Gtk.Grid()
        grid.add_css_class("shape-grid")
        for i, (sid, tip) in enumerate(shapes.SHAPES):
            g = Glyph(lambda cr, ww, hh, th, sid=sid: shapes.draw_icon(cr, sid, 16), 16, 16)
            b = button(g, "shape-button", tooltip=_(tip), cb=lambda sid=sid: w.set_shape(sid))
            self.shape_buttons[sid] = b
            grid.attach(b, i % 7, i // 7, 1, 1)
        gal.set_child(grid)
        sh.append(gal)
        styles = Gtk.Grid(row_spacing=7)
        styles.set_valign(Gtk.Align.START)
        styles.add_css_class("shape-styles")
        ob = Gtk.Box()
        ob.append(tinted_icon("outline", "grey", 20))
        ob.append(chevron(12, 10))
        self.outline_btn = button(ob, "drop-pair", tooltip=_("Shape outline"),
                                  cb=lambda: w.outline_menu(self.outline_btn))
        fb = Gtk.Box()
        fb.append(tinted_icon("fill", "grey", 20))
        fb.append(chevron(12, 10))
        self.fill_btn = button(fb, "drop-pair", tooltip=_("Shape fill"), cb=lambda: w.fill_menu(self.fill_btn))
        styles.attach(self.outline_btn, 0, 0, 1, 1)
        styles.attach(self.fill_btn, 0, 1, 1, 1)
        sz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sz.append(icon("size", 24))
        sz.append(chevron(12, 10))
        self.size_btn = button(sz, "size-button", tooltip=_("Size"), cb=lambda: w.size_menu(self.size_btn))
        self.size_btn.set_valign(Gtk.Align.CENTER)
        styles.attach(self.size_btn, 1, 0, 1, 2)
        sh.append(styles)
        self.append(Group(_("Shapes"), sh, 289, start=8))

        # ---- Colors
        cg = Gtk.Box()
        cur = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cur.add_css_class("current-colors")
        self.primary_sw = Swatch(w.primary, 24, ring=True)
        self.secondary_sw = Swatch(w.secondary, 24, ring=True)
        self.primary_btn = button(self.primary_sw, "swatch-button", "current", tooltip=_("Color 1"),
                                  cb=lambda: w.set_active_slot(0))
        self.secondary_btn = button(self.secondary_sw, "swatch-button", "current", tooltip=_("Color 2"),
                                    cb=lambda: w.set_active_slot(1))
        cur.append(self.primary_btn)
        cur.append(self.secondary_btn)
        cg.append(cur)
        pal = Gtk.Grid()
        pal.add_css_class("palette")
        for i, hx in enumerate(PALETTE):
            pal.attach(self._swatch_button(hex_rgba(hx), hx), i % 10, i // 10, 1, 1)
        self.custom_btns = []
        for i in range(10):
            b = self._swatch_button(None, "")
            self.custom_btns.append(b)
            pal.attach(b, i, 2, 1, 1)
        cg.append(pal)
        self.wheel_btn = button(ColorWheel(), "tool-button", "wheel-button", tooltip=_("Edit colors"),
                                cb=w.edit_colors)
        self.wheel_btn.set_valign(Gtk.Align.CENTER)
        cg.append(self.wheel_btn)
        self.append(Group(_("Colors"), cg, 353, start=12))

        # ---- Layers
        self.layers_btn = button(icon("layers", 24), "tool-button", "layers-button", tooltip=_("Layers"),
                                 cb=w.toggle_layers)
        self.append(Group(_("Layers"), self.layers_btn, 65, last=True))

        sp = Gtk.Box(hexpand=True)
        self.append(sp)
        self.hide_btn = button(chevron(12, 10), "collapse-button", tooltip=_("Automatically hide toolbar"),
                               cb=lambda: w.set_autohide(True))
        self.hide_btn.set_valign(Gtk.Align.END)
        self.append(self.hide_btn)
        self.refresh_custom()

    def _swatch_button(self, rgba, hx):
        sw = Swatch(rgba, 16)
        b = Gtk.Button()
        b.set_child(sw)
        b.add_css_class("swatch-button")
        if hx:
            b.set_tooltip_text(hx.upper())
        g = Gtk.GestureClick(button=3)
        g.connect("pressed", lambda *_a: sw.rgba is not None and self.win.set_secondary(sw.rgba))
        b.add_controller(g)
        b.connect("clicked", lambda *_a: sw.rgba is not None and self.win.set_active_color(sw.rgba))
        b.sw = sw
        return b

    def refresh_custom(self):
        cols = self.win.custom_colors
        for i, b in enumerate(self.custom_btns):
            c = hex_rgba(cols[i]) if i < len(cols) else None
            b.sw.set_rgba(c)
            b.set_tooltip_text(cols[i].upper() if c else _("Custom color"))

    def _theme_changed(self):
        pass

    # ------------------------------------------------------------------ state
    def sync(self):
        w = self.win
        name = w.tool_name
        for k, b in self.tool_buttons.items():
            (b.add_css_class if k == name else b.remove_css_class)("selected")
        (self.sel_box.add_css_class if name == "select" else self.sel_box.remove_css_class)("selected")
        (self.brush_box.add_css_class if name == "brush" else self.brush_box.remove_css_class)("selected")
        for k, b in self.shape_buttons.items():
            (b.add_css_class if name == "shape" and k == w.shape else b.remove_css_class)("selected")
        self.sel_glyph.set_visible_child_name(w.tools["select"].mode)
        shape_on = name == "shape"
        self.outline_btn.set_sensitive(shape_on)
        self.fill_btn.set_sensitive(shape_on)
        self.size_btn.set_sensitive(shape_on)  # the side slider sizes the other tools
        self.crop_btn.set_sensitive(w.tools["select"].has_selection)
        self.primary_sw.set_rgba(w.primary)
        self.secondary_sw.set_rgba(w.secondary)
        self.primary_sw.set_selected(w.active_slot == 0)
        self.secondary_sw.set_selected(w.active_slot == 1)
        (self.layers_btn.add_css_class if w.layers_visible else self.layers_btn.remove_css_class)("selected")


# =========================================================================== text bar

def font_families():
    fm = PangoCairo.FontMap.get_default()
    return sorted({f.get_name() for f in fm.list_families()}, key=str.lower)


class TextBar(Gtk.Box):
    """Floating text formatting bar (font, size, bold/italic/underline/strikethrough,
    alignment, background fill)."""

    def __init__(self, win):
        super().__init__(spacing=4)
        self.win = win
        self.add_css_class("text-bar")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        p = win.text_props
        self.families = font_families() or ["Sans"]
        fam = Gtk.StringList.new(self.families)
        self.font = Gtk.DropDown.new(fam, None)
        self.font.set_enable_search(True)
        exp = Gtk.PropertyExpression.new(Gtk.StringObject, None, "string")
        self.font.set_expression(exp)
        self.font.add_css_class("fluent-dropdown")
        self.font.set_size_request(180, -1)
        self.font.set_tooltip_text(_("Font family"))
        self._select_family(p["family"])
        self.font.connect("notify::selected", self._family_changed)
        self.append(self.font)
        self.size = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.size.set_value(p["size"])
        self.size.set_width_chars(3)
        self.size.add_css_class("fluent-spin")
        self.size.set_tooltip_text(_("Font size"))
        self.size.connect("value-changed", lambda sp: self.win.set_text_prop("size", sp.get_value()))
        self.append(self.size)
        self.append(self._sep())
        self.toggles = {}
        for key, ic, tip in (("bold", "bold", _("Bold (Ctrl+B)")), ("italic", "italic", _("Italic (Ctrl+I)")),
                             ("underline", "underline", _("Underline (Ctrl+U)")),
                             ("strike", "strike", _("Strikethrough"))):
            t = Gtk.ToggleButton()
            t.set_child(icon(ic, 18))
            t.add_css_class("tool-button")
            t.add_css_class("text-toggle")
            t.set_tooltip_text(tip)
            t.set_active(p[key])
            t.connect("toggled", lambda b, k=key: self.win.set_text_prop(k, b.get_active()))
            self.toggles[key] = t
            self.append(t)
        self.append(self._sep())
        self.aligns = {}
        first = None
        for key, ic, tip in (("left", "align-left", _("Align left")), ("center", "align-center", _("Center")),
                             ("right", "align-right", _("Align right"))):
            t = Gtk.ToggleButton()
            t.set_child(icon(ic, 18))
            t.add_css_class("tool-button")
            t.add_css_class("text-toggle")
            t.set_tooltip_text(tip)
            if first is None:
                first = t
            else:
                t.set_group(first)
            t.set_active(p["align"] == key)
            t.connect("toggled", lambda b, k=key: b.get_active() and self.win.set_text_prop("align", k))
            self.aligns[key] = t
            self.append(t)
        self.append(self._sep())
        bg = Gtk.ToggleButton()
        bg.set_child(icon("text-bg", 18))
        bg.add_css_class("tool-button")
        bg.add_css_class("text-toggle")
        bg.set_tooltip_text(_("Fill background with color 2"))
        bg.set_active(p["background"])
        bg.connect("toggled", lambda b: self.win.set_text_prop("background", b.get_active()))
        self.toggles["background"] = bg
        self.append(bg)

    @staticmethod
    def _sep():
        s = Gtk.Box()
        s.add_css_class("vsep")
        return s

    def _select_family(self, fam):
        low = [f.lower() for f in self.families]
        for cand in (fam, "Segoe UI", "Noto Sans", "Cantarell", "Sans"):
            if cand.lower() in low:
                self.font.set_selected(low.index(cand.lower()))
                return

    def _family_changed(self, *_a):
        i = self.font.get_selected()
        if 0 <= i < len(self.families):
            self.win.set_text_prop("family", self.families[i])

    def sync(self):
        p = self.win.text_props
        for k, t in self.toggles.items():
            if t.get_active() != p[k]:
                t.set_active(p[k])


# =========================================================================== menus

def brushes_menu(win, anchor):
    m = Menu(win, width=240)
    col = (0.1, 0.1, 0.1, 1.0) if not theme.get().dark else (0.95, 0.95, 0.95, 1.0)
    for bid, text in brushes.BRUSHES:
        pic = surface_picture(brushes.preview_surface(bid, col))
        pic.add_css_class("brush-preview")
        # The reference highlights no entry here.
        m.add(_(text), lambda bid=bid: win.set_brush(bid), extra=pic)
    m.add_css_class("brush-menu")
    popup_menu(win, m, anchor, dx=-1, dy=4)


def style_menu(win, anchor, items, current, cb):
    m = Menu(win, width=200)
    for sid, text in items:
        m.add(_(text), lambda sid=sid: cb(sid), selected=(sid == current))
    popup_menu(win, m, anchor)


def size_menu(win, anchor):
    m = Menu(win, width=160)
    cur = win.size_for(win.size_key)
    for px in (1, 3, 5, 8):
        g = Glyph(lambda cr, ww, hh, th, px=px: (cr.set_line_width(px), cr.move_to(4, hh / 2),
                                                 cr.line_to(ww - 4, hh / 2), cr.stroke()), 80, 16)
        m.add(_("%d px") % px, lambda px=px: win.set_size(px), extra=g, selected=(round(cur) == px))
    popup_menu(win, m, anchor)


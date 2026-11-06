"""Edit colours dialog: hue/saturation spectrum, value slider, preview, hex and RGB/HSV
fields, basic and custom colour grids.  Layout measured on the reference dialog."""
from __future__ import annotations

import colorsys
import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Graphene, Gtk  # noqa: E402

from . import theme  # noqa: E402
from .i18n import _  # noqa: E402
from .widgets import Dialog, Menu, button, icon, label, popup_menu  # noqa: E402

# The 48 basic colours, as displayed by the reference (4 rows of 12).
BASIC = [
    "#f08784", "#eb3324", "#774342", "#8e403a", "#3a0603", "#9ffcfd", "#73fbfd", "#3282f6", "#0023f5", "#00129a",
    "#16417c", "#000c7b", "#fffe91", "#fffd55", "#f09b59", "#f08650", "#784315", "#817f26", "#7e84f7", "#732bf5",
    "#3580bb", "#00023d", "#58135e", "#3a083e", "#a1fb8e", "#a1fa4f", "#75f94d", "#75fa61", "#75fa8d", "#818049",
    "#ef88be", "#ee8af8", "#ea3ff7", "#ea3680", "#7f82bb", "#75163f", "#377d22", "#377e47", "#367e7f", "#507f80",
    "#183e0c", "#173f3f", "#741b7c", "#39107b", "#000000", "#808080", "#c0c0c0", "#ffffff",
]
CUSTOM_SLOTS = 24
SPEC = 256


def _hex(c):
    return "#%02X%02X%02X" % tuple(int(round(max(0, min(1, v)) * 255)) for v in c[:3])


def _parse(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


_SPECTRUM = None


def _spectrum_surface():
    """Hue left to right, saturation top (full) to bottom (white), value 1."""
    global _SPECTRUM
    if _SPECTRUM is None:
        s = cairo.ImageSurface(cairo.FORMAT_RGB24, SPEC, SPEC)
        stride = s.get_stride()
        buf = bytearray(stride * SPEC)
        hues = [colorsys.hsv_to_rgb(x / SPEC, 1, 1) for x in range(SPEC)]
        for y in range(SPEC):
            sat = 1 - y / (SPEC - 1)
            row = bytearray(stride)
            for x, (r, g, b) in enumerate(hues):
                o = x * 4
                row[o] = int(255 * (1 - sat + sat * b))
                row[o + 1] = int(255 * (1 - sat + sat * g))
                row[o + 2] = int(255 * (1 - sat + sat * r))
            buf[y * stride:(y + 1) * stride] = row
        s.get_data()[:] = bytes(buf)
        s.mark_dirty()
        _SPECTRUM = s
    return _SPECTRUM


class _Area(Gtk.Widget):
    __gtype_name__ = "FenestraPaintColorArea"

    def __init__(self, dlg, kind, w, h):
        super().__init__()
        self.dlg, self.kind, self.w, self.h = dlg, kind, w, h
        if kind in ("spectrum", "value"):
            g = Gtk.GestureDrag()
            g.connect("drag-begin", lambda _g, x, y: self._pick(x, y))
            g.connect("drag-update", lambda g_, dx, dy: self._pick(*self._start(g_, dx, dy)))
            self.add_controller(g)

    @staticmethod
    def _start(g, dx, dy):
        ok, x, y = g.get_start_point()
        return x + dx, y + dy

    def do_measure(self, orientation, for_size):
        n = self.w if orientation == Gtk.Orientation.HORIZONTAL else self.h
        return n, n, -1, -1

    def _pick(self, x, y):
        d = self.dlg
        if self.kind == "spectrum":
            d.h = max(0.0, min(1.0, x / self.w)) % 1.0 if x < self.w else 0.9999
            d.s = 1 - max(0.0, min(1.0, y / self.h))
            if d.v == 0:
                d.v = 1.0
        else:
            d.v = 1 - max(0.0, min(1.0, y / self.h))
        d.changed()

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        cr = snap.append_cairo(Graphene.Rect().init(-8, -8, w + 16, h + 16))
        d = self.dlg
        if self.kind == "spectrum":
            cr.save()
            _rounded(cr, 0, 0, w, h, 4)
            cr.clip()
            cr.scale(w / SPEC, h / SPEC)
            cr.set_source_surface(_spectrum_surface(), 0, 0)
            cr.paint()
            cr.restore()
            cr.set_source_rgba(0, 0, 0, 0.1)
            cr.set_line_width(1)
            _rounded(cr, 0.5, 0.5, w - 1, h - 1, 3.5)
            cr.stroke()
            _rounded(cr, 0, 0, w, h, 4)
            cr.clip()
            x, y = d.h * w, (1 - d.s) * h
            cr.arc(x, y, 7, 0, 2 * math.pi)
            cr.set_line_width(2)
            cr.set_source_rgb(1, 1, 1)
            cr.stroke_preserve()
            cr.set_line_width(1)
            cr.set_source_rgb(0, 0, 0)
            cr.arc(x, y, 8, 0, 2 * math.pi)
            cr.stroke()
        elif self.kind == "preview":
            _rounded(cr, 0, 0, w, h, 4)
            cr.set_source_rgb(*d.rgb())
            cr.fill()
        else:
            _rounded(cr, 0, 0, w, h, w / 2)
            top = colorsys.hsv_to_rgb(d.h, d.s, 1)
            pat = cairo.LinearGradient(0, 0, 0, h)
            pat.add_color_stop_rgb(0, *top)
            pat.add_color_stop_rgb(1, 0, 0, 0)
            cr.set_source(pat)
            cr.fill()
            y = max(6, min(h - 6, (1 - d.v) * h))
            cr.arc(w / 2, y, 6.5, 0, 2 * math.pi)
            cr.set_source_rgb(*theme.get().rgb("thumb")[:3])
            cr.fill_preserve()
            cr.set_line_width(1)
            cr.set_source_rgba(0, 0, 0, 0.35)
            cr.stroke()
            cr.arc(w / 2, y, 3.5, 0, 2 * math.pi)
            cr.set_source_rgb(*theme.get().rgb("fg")[:3])
            cr.fill()


class _Dot(Gtk.Widget):
    """20 px colour circle (or dashed empty slot) in a 30 px cell."""
    __gtype_name__ = "FenestraPaintColorDot"

    def __init__(self, rgb):
        super().__init__()
        self.rgb = rgb

    def do_measure(self, orientation, for_size):
        return 20, 20, -1, -1

    def do_snapshot(self, snap):
        th = theme.get()
        cr = snap.append_cairo(Graphene.Rect().init(0, 0, 20, 20))
        cr.arc(10, 10, 9.5, 0, 2 * math.pi)
        if self.rgb is None:
            cr.set_dash([3, 2.2])
            cr.set_line_width(1)
            cr.set_source_rgba(*th.rgb("dot-empty"))
            cr.stroke()
            return
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_line_width(1)
        cr.set_source_rgba(*th.rgb("dot-line"))
        cr.stroke()


class EditColors:
    def __init__(self, win, rgb, on_ok):
        self.win = win
        self.on_ok = on_ok
        self.h, self.s, self.v = colorsys.rgb_to_hsv(*rgb[:3])
        self.model = "rgb"
        self._busy = False
        from .dialogs import NumberBox
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top = Gtk.Box()
        top.add_css_class("ec-top")
        self.spectrum = _Area(self, "spectrum", SPEC, SPEC)
        self.preview = _Area(self, "preview", 44, SPEC)
        self.value = _Area(self, "value", 12, SPEC)
        self.preview.add_css_class("ec-preview")
        self.value.add_css_class("ec-value")
        for wdg in (self.spectrum, self.preview, self.value):
            wdg.set_valign(Gtk.Align.START)
            top.append(wdg)
        fields = Gtk.Grid(row_spacing=12, column_spacing=10)
        fields.add_css_class("ec-fields")
        self.hex = Gtk.Entry()
        self.hex.add_css_class("fluent-box")
        self.hex.set_size_request(118, -1)
        self.hex.set_width_chars(1)
        self.hex.set_max_width_chars(1)
        self.hex.connect("changed", self._hex_changed)
        fields.attach(self.hex, 0, 0, 1, 1)
        mb = Gtk.Box()
        self.model_label = label("RGB", "ec-model-label")
        self.model_label.set_hexpand(True)
        mb.append(self.model_label)
        mb.append(icon("chevron-down", 12, "zoom-chev"))
        self.model_btn = button(mb, "zoom-combo", "ec-model", cb=self._model_menu)
        self.model_btn.set_hexpand(False)
        self.hex.set_hexpand(False)
        fields.attach(self.model_btn, 0, 1, 1, 1)
        self.boxes, self.names = [], []
        for i in range(3):
            nb = NumberBox(0, 0, 255, 118)
            nb.connect("value-changed", lambda *_a: self._field_changed())
            self.boxes.append(nb)
            lb = label("", "dialog-label")
            self.names.append(lb)
            fields.attach(nb, 0, 2 + i, 1, 1)
            fields.attach(lb, 1, 2 + i, 1, 1)
        fields.set_valign(Gtk.Align.START)
        top.append(fields)
        body.append(top)

        heads = Gtk.Box()
        heads.add_css_class("ec-heads")
        lb = label(_("Basic colors"), "dialog-label", "ec-head")
        lb.set_size_request(383, -1)
        heads.append(lb)
        heads.append(label(_("Custom colors"), "dialog-label", "ec-head"))
        heads.append(Gtk.Box(hexpand=True))
        add = button(icon("add", 20), "ec-add", tooltip=_("Add to custom colors"), cb=self._add_custom)
        heads.append(add)
        body.append(heads)

        grids = Gtk.Box()
        grids.add_css_class("ec-grids")
        basic = Gtk.Grid()
        basic.add_css_class("ec-basic")
        for i, hx in enumerate(BASIC):
            basic.attach(self._dot_button(_parse(hx)), i % 12, i // 12, 1, 1)
        grids.append(basic)
        self.custom = Gtk.Grid()
        self.custom.add_css_class("ec-custom")
        grids.append(self.custom)
        body.append(grids)
        self._fill_custom()

        self.dialog = Dialog(win, _("Edit colors"), body,
                             [(_("OK"), self._ok, True), (_("Cancel"), None, False)], width=666, smoke=False)
        self.dialog.add_css_class("resize-dialog")
        self.dialog.add_css_class("colors-dialog")
        self.dialog.editor = self
        self._set_model("rgb")
        self.changed()

    # ------------------------------------------------------------------ parts
    def _dot_button(self, rgb):
        b = Gtk.Button()
        b.add_css_class("ec-dot")
        b.set_child(_Dot(rgb))
        if rgb is not None:
            b.set_tooltip_text(_hex(rgb))
            b.connect("clicked", lambda *_a: self.set_rgb(rgb))
        return b

    def _fill_custom(self):
        c = self.custom.get_first_child()
        while c is not None:
            n = c.get_next_sibling()
            self.custom.remove(c)
            c = n
        cols = [_parse(h) for h in self.win.custom_colors][:CUSTOM_SLOTS]
        for i in range(CUSTOM_SLOTS):
            self.custom.attach(self._dot_button(cols[i] if i < len(cols) else None), i % 6, i // 6, 1, 1)

    def _add_custom(self):
        self.win.add_custom_color(tuple(self.rgb()) + (1.0,), activate=False)
        self._fill_custom()

    def _model_menu(self):
        m = Menu(self.win, width=118)
        m.add("RGB", lambda: self._set_model("rgb"), selected=self.model == "rgb")
        m.add("HSV", lambda: self._set_model("hsv"), selected=self.model == "hsv")
        popup_menu(self.win, m, self.model_btn, dy=-34)

    def _set_model(self, model):
        self.model = model
        self.model_label.set_text(model.upper())
        names = (_("Red"), _("Green"), _("Blue")) if model == "rgb" else (_("Hue"), _("Saturation"), _("Value"))
        rng = (255, 255, 255) if model == "rgb" else (359, 100, 100)
        for lb, nb, n, hi in zip(self.names, self.boxes, names, rng):
            lb.set_text(n)
            nb.set_range(0, hi)
        self._sync_fields()

    # ------------------------------------------------------------------ state
    def rgb(self):
        return colorsys.hsv_to_rgb(self.h, self.s, self.v)

    def set_rgb(self, rgb):
        self.h, self.s, self.v = colorsys.rgb_to_hsv(*rgb[:3])
        self.changed()

    def changed(self):
        for wdg in (self.spectrum, self.preview, self.value):
            wdg.queue_draw()
        self._sync_fields()

    def _sync_fields(self):
        self._busy = True
        r, g, b = self.rgb()
        if self.model == "rgb":
            vals = [round(r * 255), round(g * 255), round(b * 255)]
        else:
            vals = [round(self.h * 360) % 360, round(self.s * 100), round(self.v * 100)]
        for nb, v in zip(self.boxes, vals):
            nb.set_value(v)
        if not self.hex.has_focus():
            self.hex.set_text(_hex((r, g, b)))
        self._busy = False

    def _field_changed(self):
        if self._busy:
            return
        a, b, c = (nb.get_value() for nb in self.boxes)
        if self.model == "rgb":
            self.h, self.s, self.v = colorsys.rgb_to_hsv(a / 255, b / 255, c / 255)
        else:
            self.h, self.s, self.v = (a % 360) / 360, b / 100, c / 100
        self.changed()

    def _hex_changed(self, *_a):
        if self._busy:
            return
        rgb = _parse(self.hex.get_text())
        if rgb is not None:
            self.h, self.s, self.v = colorsys.rgb_to_hsv(*rgb)
            self._busy = True
            GLib.idle_add(lambda: (setattr(self, "_busy", False), self.changed(), False)[2])

    def _ok(self):
        self.on_ok(tuple(self.rgb()) + (1.0,))


def edit_colors(win, rgba, on_ok):
    ed = EditColors(win, rgba, on_ok)
    win.show_dialog(ed.dialog)
    return ed

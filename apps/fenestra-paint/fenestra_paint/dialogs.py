"""Content dialogs: resize and skew, rotate custom, image properties, unsaved changes."""
from __future__ import annotations

import os
import time

from gi.repository import GObject, Gtk

from . import util
from .i18n import N_, _
from .widgets import Dialog, checkbox, label, radio_group, spin_entry


def _row(text, widget, unit=None):
    b = Gtk.Box(spacing=12)
    b.add_css_class("dialog-row")
    lb = label(text, "dialog-label")
    lb.set_size_request(110, -1)
    b.append(lb)
    b.append(widget)
    if unit:
        b.append(label(unit, "dialog-unit"))
    return b


class NumberBox(Gtk.Entry):
    """Fluent text box holding a number with an optional unit ("0°"); SpinButton-like API."""
    __gsignals__ = {"value-changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, value, lo, hi, width, unit=""):
        super().__init__()
        self.lo, self.hi, self.unit = lo, hi, unit
        self._value = value
        self._busy = False
        self.add_css_class("fluent-box")
        self.set_size_request(width, -1)
        self.set_width_chars(1)
        self.set_max_width_chars(1)
        self.set_hexpand(False)
        self._show()
        self.connect("changed", self._changed)
        fc = Gtk.EventControllerFocus()
        fc.connect("leave", lambda *_a: self._show())
        self.add_controller(fc)
        self.connect("activate", lambda *_a: self._show())

    def _show(self):
        self._busy = True
        self.set_text(f"{self._value:g}{self.unit}")
        self._busy = False

    def _changed(self, *_a):
        if self._busy:
            return
        t = self.get_text().replace(self.unit, "").replace(",", ".").strip()
        try:
            v = float(t)
        except ValueError:
            return
        v = max(self.lo, min(self.hi, v))
        if v != self._value:
            self._value = v
            self.emit("value-changed")

    def get_value(self):
        return self._value

    def set_value(self, v):
        v = max(self.lo, min(self.hi, v))
        changed = v != self._value
        self._value = v
        self._show()
        if changed:
            self.emit("value-changed")

    def set_range(self, lo, hi):
        self.lo, self.hi = lo, hi


def _link_glyph(cr, w, h, _th):
    """Two linked chain loops (own drawing)."""
    cr.set_line_width(1.2)
    for x0 in (1.5, 7.5):
        r = 2.5
        x1, y0, y1 = x0 + 7, h / 2 - r, h / 2 + r
        cr.new_sub_path()
        cr.arc(x0 + r, h / 2, r, 0.5 * 3.14159, 1.5 * 3.14159)
        cr.line_to(x1 - r, y0)
        cr.arc(x1 - r, h / 2, r, -0.5 * 3.14159, 0.5 * 3.14159)
        cr.close_path()
    cr.stroke()


def resize_skew(win, w, h, apply, title=None):
    """apply(new_w, new_h, skew_x_deg, skew_y_deg).  Layout measured on the reference dialog."""
    from .widgets import Glyph
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    body.add_css_class("resize-body")
    body.append(label(_("Resize"), "dialog-section", "rs-head"))
    state = {"mode": "percent", "busy": False}
    hs = NumberBox(100, 1, 10000, 115)
    vs = NumberBox(100, 1, 10000, 115)
    keep = Gtk.ToggleButton()
    keep.add_css_class("link-toggle")
    keep.set_child(Glyph(_link_glyph, 16, 16))
    keep.set_tooltip_text(_("Maintain aspect ratio"))
    keep.set_active(True)
    keep.set_valign(Gtk.Align.CENTER)

    def set_mode(m):
        if m == state["mode"]:
            return
        state["busy"] = True
        hv, vv = hs.get_value(), vs.get_value()
        if m == "pixels":
            hs.set_range(1, 50000)
            vs.set_range(1, 50000)
            hs.set_value(round(w * hv / 100))
            vs.set_value(round(h * vv / 100))
        else:
            hs.set_value(round(hv / w * 100))
            vs.set_value(round(vv / h * 100))
            hs.set_range(1, 10000)
            vs.set_range(1, 10000)
        state["mode"] = m
        state["busy"] = False
    modes = radio_group([("percent", _("Percentage")), ("pixels", _("Pixels"))], "percent", set_mode)
    modes.set_orientation(Gtk.Orientation.HORIZONTAL)
    modes.set_spacing(0)
    modes.add_css_class("rs-modes")
    modes.btns["percent"].set_size_request(130, -1)
    body.append(modes)

    def sync(src, dst, sw, dw):
        if state["busy"] or not keep.get_active():
            return
        state["busy"] = True
        if state["mode"] == "percent":
            dst.set_value(src.get_value())
        else:
            dst.set_value(max(1, round(src.get_value() * dw / sw)))
        state["busy"] = False
    hs.connect("value-changed", lambda *_a: sync(hs, vs, w, h))
    vs.connect("value-changed", lambda *_a: sync(vs, hs, h, w))

    def pair_grid(a, b, mid=None, spacing=8):
        g = Gtk.Grid(column_spacing=spacing, row_spacing=0)
        g.add_css_class("rs-grid")
        g.attach(label(_("Horizontal"), "dialog-label", "rs-label"), 0, 0, 1, 1)
        g.attach(label(_("Vertical"), "dialog-label", "rs-label"), 2 if mid else 1, 0, 1, 1)
        g.attach(a, 0, 1, 1, 1)
        if mid:
            g.attach(mid, 1, 1, 1, 1)
        g.attach(b, 2 if mid else 1, 1, 1, 1)
        return g
    body.append(pair_grid(hs, vs, keep, 6))
    body.append(label(_("Skew"), "dialog-section", "rs-head", "rs-skew"))
    sx = NumberBox(0, -89, 89, 131, "°")
    sy = NumberBox(0, -89, 89, 131, "°")
    body.append(pair_grid(sx, sy))

    def ok():
        if state["mode"] == "percent":
            nw, nh = w * hs.get_value() / 100, h * vs.get_value() / 100
        else:
            nw, nh = hs.get_value(), vs.get_value()
        apply(max(1, round(nw)), max(1, round(nh)), sx.get_value(), sy.get_value())
    d = Dialog(win, title or _("Resize and skew"), body,
               [(_("OK"), ok, True), (_("Cancel"), None, False)], width=317, smoke=False)
    d.add_css_class("resize-dialog")
    win.show_dialog(d)
    d.hs, d.vs, d.sx, d.sy, d.keep, d.modes = hs, vs, sx, sy, keep, modes
    return d


def rotate_custom(win, apply):
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    ang = spin_entry(0, -360, 360, digits=1)
    body.append(_row(_("Angle:"), ang, "°"))
    body.append(label(_("Positive angles rotate clockwise."), "dialog-hint", wrap=True))
    d = Dialog(win, _("Rotate custom"), body, [(_("OK"), lambda: apply(ang.get_value()), True),
                                              (_("Cancel"), None, False)], width=360)
    win.show_dialog(d)
    ang.grab_focus()
    d.angle = ang
    return d


UNITS = [("inches", N_("Inches")), ("cm", N_("Centimeters")), ("pixels", N_("Pixels"))]
DPI = 96.0


def properties(win, apply):
    """apply(new_w, new_h, black_and_white)."""
    doc = win.doc
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    body.append(label(_("Attributes"), "dialog-section"))
    path = win.path
    if path and os.path.exists(path):
        st = os.stat(path)
        saved = time.strftime("%x %X", time.localtime(st.st_mtime))
        size = util.fmt_size(st.st_size)
    else:
        saved = size = _("Not available")
    grid = Gtk.Grid(column_spacing=16, row_spacing=4)
    for i, (k, v) in enumerate(((_("Last saved:"), saved), (_("Size on disk:"), size),
                                (_("Resolution:"), _("%d DPI") % DPI))):
        grid.attach(label(k, "dialog-label"), 0, i, 1, 1)
        grid.attach(label(v, "dialog-value"), 1, i, 1, 1)
    body.append(grid)
    state = {"unit": "pixels", "busy": False}
    ws = spin_entry(doc.width, 1, 50000, digits=0)
    hs = spin_entry(doc.height, 1, 50000, digits=0)

    def to_unit(px, u):
        return px / DPI if u == "inches" else px / DPI * 2.54 if u == "cm" else px

    def from_unit(v, u):
        return v * DPI if u == "inches" else v / 2.54 * DPI if u == "cm" else v

    def set_unit(u):
        pw, ph = from_unit(ws.get_value(), state["unit"]), from_unit(hs.get_value(), state["unit"])
        state["unit"] = u
        digits = 0 if u == "pixels" else 2
        for sp, v in ((ws, pw), (hs, ph)):
            sp.set_digits(digits)
            sp.set_increments(1 if u == "pixels" else 0.01, 10)
            sp.set_range(0.01, 50000)
            sp.set_value(to_unit(v, u))
    body.append(label(_("Units"), "dialog-section"))
    units = radio_group([(k, _(t)) for k, t in UNITS], "pixels", set_unit)
    units.set_orientation(Gtk.Orientation.HORIZONTAL)
    units.set_spacing(20)
    body.append(units)
    body.append(label(_("Colors"), "dialog-section"))
    colors = radio_group([("bw", _("Black and white")), ("color", _("Color"))], "color", lambda k: None)
    colors.set_orientation(Gtk.Orientation.HORIZONTAL)
    colors.set_spacing(20)
    body.append(colors)
    body.append(_row(_("Width:"), ws))
    body.append(_row(_("Height:"), hs))

    def ok():
        nw = round(from_unit(ws.get_value(), state["unit"]))
        nh = round(from_unit(hs.get_value(), state["unit"]))
        apply(max(1, nw), max(1, nh), colors.btns["bw"].get_active())

    def defaults():
        units.btns["pixels"].set_active(True)
        ws.set_value(1152)
        hs.set_value(648)
        colors.btns["color"].set_active(True)
        return True
    d = Dialog(win, _("Image properties"), body,
               [(_("Default"), defaults, False), (_("OK"), ok, True), (_("Cancel"), None, False)], width=420)
    win.show_dialog(d)
    d.ws, d.hs, d.units, d.colors = ws, hs, units, colors
    return d


def unsaved(win, on_save, on_discard, on_cancel=None):
    name = util.display_name(win.path)
    d = Dialog(win, _("Paint"), _("Do you want to save changes to %s?") % name,
               [(_("Save"), on_save, True), (_("Don't save"), on_discard, False), (_("Cancel"), on_cancel, False)],
               width=420, on_close=on_cancel)
    win.show_dialog(d)
    return d


def message(win, title, text):
    d = Dialog(win, title, text, [(_("OK"), None, True)], width=400)
    win.show_dialog(d)
    return d

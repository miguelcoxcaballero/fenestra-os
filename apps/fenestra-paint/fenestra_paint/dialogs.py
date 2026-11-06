"""Content dialogs: resize and skew, rotate custom, image properties, unsaved changes."""
from __future__ import annotations

import os
import time

from gi.repository import Gtk

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


def resize_skew(win, w, h, apply, title=None):
    """apply(new_w, new_h, skew_x_deg, skew_y_deg)."""
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    body.append(label(_("Resize"), "dialog-section"))
    state = {"mode": "percent", "busy": False}
    hs = spin_entry(100, 1, 10000)
    vs = spin_entry(100, 1, 10000)
    keep = checkbox(_("Maintain aspect ratio"), True)

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
    modes.set_spacing(24)
    body.append(_row(_("By:"), modes))

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
    body.append(_row(_("Horizontal:"), hs))
    body.append(_row(_("Vertical:"), vs))
    body.append(keep)
    body.append(label(_("Skew (degrees)"), "dialog-section"))
    sx = spin_entry(0, -89, 89)
    sy = spin_entry(0, -89, 89)
    body.append(_row(_("Horizontal:"), sx, "°"))
    body.append(_row(_("Vertical:"), sy, "°"))

    def ok():
        if state["mode"] == "percent":
            nw, nh = w * hs.get_value() / 100, h * vs.get_value() / 100
        else:
            nw, nh = hs.get_value(), vs.get_value()
        apply(max(1, round(nw)), max(1, round(nh)), sx.get_value(), sy.get_value())
    d = Dialog(win, title or _("Resize and skew"), body,
               [(_("OK"), ok, True), (_("Cancel"), None, False)], width=400)
    win.show_dialog(d)
    hs.grab_focus()
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

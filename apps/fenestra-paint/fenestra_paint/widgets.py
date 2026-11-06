"""Small Fluent-style building blocks: icons, in-window flyout menus, content dialogs,
sliders and colour swatches.

Menus and dialogs live inside the main window (an overlay layer), like WinUI flyouts:
they are styled exactly like the rest of the app, can be captured in screenshots and
need no extra surfaces."""
from __future__ import annotations

import math

import cairo
from gi.repository import Gdk, GLib, GObject, Graphene, Gsk, Gtk

from . import theme
from .i18n import _


def icon(name, size=20, *classes):
    im = Gtk.Image.new_from_icon_name(name if name.endswith("-symbolic") or "." in name else f"pt-{name}-symbolic")
    im.set_pixel_size(size)
    for c in classes:
        im.add_css_class(c)
    return im


def tinted_icon(name, tint, size=20):
    """Two-tone glyph: the filled shape in a tint colour under the regular outline."""
    ov = Gtk.Overlay()
    base = icon(f"pt-{name}-fill-symbolic", size, "tint", f"tint-{tint}")
    ov.set_child(base)
    top = icon(name, size)
    ov.add_overlay(top)
    ov.set_halign(Gtk.Align.CENTER)
    ov.set_valign(Gtk.Align.CENTER)
    return ov


def label(text, *classes, xalign=0.0, wrap=False, ellipsize=False):
    lb = Gtk.Label(label=text, xalign=xalign)
    for c in classes:
        lb.add_css_class(c)
    if wrap:
        lb.set_wrap(True)
        lb.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
    if ellipsize:
        from gi.repository import Pango
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    return lb


def button(child=None, *classes, tooltip=None, cb=None):
    b = Gtk.Button()
    if isinstance(child, str):
        b.set_label(child)
    elif child is not None:
        b.set_child(child)
    for c in classes:
        b.add_css_class(c)
    if tooltip:
        b.set_tooltip_text(tooltip)
    if cb:
        b.connect("clicked", lambda *_a: cb())
    return b


def _pt(x, y):
    p = Graphene.Point()
    p.x, p.y = x, y
    return p


# =========================================================================== flyout layer

class FlyoutLayer(Gtk.Widget):
    """Full-window overlay hosting open menus; a click outside closes them."""
    __gtype_name__ = "FenestraPaintFlyoutLayer"

    def __init__(self):
        super().__init__()
        self.items = []         # [(widget, x, y)]
        self.set_visible(False)
        g = Gtk.GestureClick(button=0)
        g.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        g.connect("pressed", self._pressed)
        self.add_controller(g)
        self.on_close = []

    def _pressed(self, g, n, x, y):
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        while w is not None and w is not self:
            if any(w is it[0] for it in self.items):
                return
            w = w.get_parent()
        g.set_state(Gtk.EventSequenceState.CLAIMED)
        self.close_all()

    def show(self, widget, x, y, level=0):
        # close deeper levels
        while len(self.items) > level:
            self._pop()
        widget.set_parent(self)
        self.items.append((widget, x, y))
        self.set_visible(True)
        self.queue_allocate()
        GLib.idle_add(lambda: (widget.grab_focus_first() if hasattr(widget, "grab_focus_first") else None, False)[1])

    def _pop(self):
        w, _x, _y = self.items.pop()
        if hasattr(w, "on_closed"):
            w.on_closed()
        w.unparent()

    def close_level(self, level):
        while len(self.items) > level:
            self._pop()
        if not self.items:
            self.set_visible(False)
            for cb in list(self.on_close):
                cb()

    def close_all(self):
        self.close_level(0)

    @property
    def is_open(self):
        return bool(self.items)

    def do_measure(self, orientation, for_size):
        return 0, 0, -1, -1

    def do_size_allocate(self, w, h, baseline):
        for widget, x, y in self.items:
            _mn, nat, _a, _b = widget.measure(Gtk.Orientation.HORIZONTAL, -1)
            ww = nat
            _mn, hh, _a, _b = widget.measure(Gtk.Orientation.VERTICAL, ww)
            if callable(x):
                x = x(ww)
            px = max(4, min(int(x), w - ww - 4))
            py = int(y(hh)) if callable(y) else int(y)
            if py + hh > h - 4:
                py = max(4, h - hh - 4)
            widget.allocate(ww, hh, -1, Gsk.Transform().translate(_pt(px, py)))

    def do_snapshot(self, snap):
        for widget, _x, _y in self.items:
            self.snapshot_child(widget, snap)


class Menu(Gtk.Box):
    """Fluent flyout menu (File / Edit / View / selection / brushes ...)."""

    def __init__(self, win, level=0, width=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.level = level
        self.add_css_class("flyout")
        self.set_focusable(False)
        if width:
            self.set_size_request(width, -1)
        self.sub = None
        self._first = None
        self._hover_id = 0
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)

    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.win.flyouts.close_level(self.level)
            return True
        if keyval == Gdk.KEY_Left and self.level > 0:
            self.win.flyouts.close_level(self.level)
            return True
        return False

    def grab_focus_first(self):
        if self._first is not None and self.get_root() is not None:
            self._first.grab_focus()

    def add(self, text, cb=None, icon_name=None, shortcut=None, sensitive=True, check=None,
            selected=False, extra=None, submenu=None, keep_open=False):
        b = Gtk.Button()
        b.add_css_class("menu-item")
        if selected:
            b.add_css_class("selected")
        box = Gtk.Box()
        pill = Gtk.Box()
        pill.add_css_class("menu-pill")
        pill.set_valign(Gtk.Align.CENTER)
        box.append(pill)
        if icon_name is None and extra is None:
            b.add_css_class("compact")
        if check is not None:
            im = icon("check", 20, "menu-icon")
            im.set_opacity(1.0 if check else 0.0)
            box.append(im)
        elif icon_name is not None:
            box.append(icon(icon_name, 20, "menu-icon") if isinstance(icon_name, str) else icon_name)
        else:
            sp = Gtk.Box()
            sp.add_css_class("menu-icon-space")
            box.append(sp)
        lb = label(text, "menu-label")
        lb.set_hexpand(True)
        box.append(lb)
        if extra is not None:
            box.append(extra)
        if shortcut:
            box.append(label(shortcut, "menu-shortcut", xalign=1.0))
        if submenu is not None:
            box.append(icon("chevron-right", 12, "menu-chevron"))
        b.set_child(box)
        b.set_sensitive(sensitive)
        if self._first is None and sensitive:
            self._first = b

        if submenu is not None:
            def open_sub(*_a):
                self._open_sub(b, submenu)
            b.connect("clicked", open_sub)
            mc = Gtk.EventControllerMotion()

            def enter(*_a):
                if self._hover_id:
                    GLib.source_remove(self._hover_id)
                self._hover_id = GLib.timeout_add(250, lambda: (open_sub(), setattr(self, "_hover_id", 0), False)[2])

            def leave(*_a):
                if self._hover_id:
                    GLib.source_remove(self._hover_id)
                    self._hover_id = 0
            mc.connect("enter", enter)
            mc.connect("leave", leave)
            b.add_controller(mc)
            kc = Gtk.EventControllerKey()
            kc.connect("key-pressed", lambda _c, kv, _k, _s: (open_sub(), True)[1]
                       if kv in (Gdk.KEY_Right, Gdk.KEY_Return) else False)
            b.add_controller(kc)
        else:
            mc = Gtk.EventControllerMotion()
            mc.connect("enter", lambda *_a: self.win.flyouts.close_level(self.level + 1)
                       if len(self.win.flyouts.items) > self.level + 1 else None)
            b.add_controller(mc)

            def clicked(*_a):
                if not keep_open:
                    self.win.flyouts.close_all()
                if cb:
                    GLib.idle_add(lambda: (cb(), False)[1])
            b.connect("clicked", clicked)
        self.append(b)
        return b

    def _open_sub(self, item, builder):
        fl = self.win.flyouts
        ok, b = item.compute_bounds(fl)
        if not ok:
            return
        menu = builder(self.level + 1)
        x = b.get_x() + b.get_width() + 2
        fl.show(menu, x, b.get_y() - 4, self.level + 1)

    def add_separator(self):
        s = Gtk.Box()
        s.add_css_class("menu-sep")
        self.append(s)

    def add_widget(self, w):
        self.append(w)


def popup_menu(win, menu, anchor, below=True, dx=0, dy=0, align="start", above=False):
    """Show menu under (or beside) anchor widget."""
    fl = win.flyouts
    ok, b = anchor.compute_bounds(fl)
    if not ok:
        return
    if align == "end":
        x = (lambda ww: b.get_x() + b.get_width() - ww + dx)
    elif align == "center":
        x = (lambda ww: b.get_x() + b.get_width() / 2 - ww / 2 + dx)
    else:
        x = b.get_x() + dx
    if above:
        y = (lambda hh: b.get_y() - hh - 2 + dy)
    else:
        y = b.get_y() + b.get_height() + 2 + dy if below else b.get_y() + dy
    fl.show(menu, x, y, 0)


def popup_at(win, menu, x, y):
    win.flyouts.show(menu, x, y, 0)


# =========================================================================== dialog

class Dialog(Gtk.Box):
    """Windows 11 content dialog shown over a smoke layer inside the window."""

    def __init__(self, win, title, body=None, buttons=(), width=440, on_close=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.on_close = on_close
        self.add_css_class("dialog-card")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_size_request(width, -1)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.add_css_class("dialog-top")
        top.append(label(title, "dialog-title", wrap=True))
        if isinstance(body, str):
            top.append(label(body, "dialog-body", wrap=True))
        elif body is not None:
            top.append(body)
        self.content = top
        self.append(top)
        foot = Gtk.Box(spacing=8, homogeneous=True)
        foot.add_css_class("dialog-foot")
        self.buttons = []
        for text, cb, primary in buttons:
            b = Gtk.Button(label=text)
            b.add_css_class("dialog-button")
            if primary:
                b.add_css_class("accent")
            b.connect("clicked", self._clicked, cb)
            foot.append(b)
            self.buttons.append(b)
        self.append(foot)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)

    def _clicked(self, _b, cb):
        keep = cb() if cb else None
        if keep is not True:
            self.close()

    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            if self.on_close:
                self.on_close()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            for b in self.buttons:
                if b.has_css_class("accent"):
                    b.emit("clicked")
                    return True
        return False

    def close(self):
        self.win.hide_dialog(self)


# =========================================================================== slider

class Slider(Gtk.Widget):
    """Fluent slider (accent-filled track, white thumb with an accent dot)."""
    __gtype_name__ = "FenestraPaintSlider"
    __gsignals__ = {
        "value-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "released": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, orientation=Gtk.Orientation.HORIZONTAL, lo=0.0, hi=1.0, value=0.0, length=130,
                 mapping=None):
        super().__init__()
        self.orientation = orientation
        self.lo, self.hi = lo, hi
        self.value = value
        self.length = length
        self.mapping = mapping  # (to_frac, from_frac) for non-linear sliders
        self.hover = False
        self.dragging = False
        self.set_focusable(True)
        self.add_css_class("fluent-slider")
        g = Gtk.GestureDrag()
        g.connect("drag-begin", self._begin)
        g.connect("drag-update", self._update)
        g.connect("drag-end", self._end)
        self.add_controller(g)
        self._g = g
        mc = Gtk.EventControllerMotion()
        mc.connect("enter", lambda *_a: self._set_hover(True))
        mc.connect("leave", lambda *_a: self._set_hover(False))
        self.add_controller(mc)
        sc = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        sc.connect("scroll", self._scroll)
        self.add_controller(sc)
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", self._key)
        self.add_controller(kc)
        theme.get().connect(self.queue_draw)

    def _set_hover(self, h):
        self.hover = h
        self.queue_draw()

    def frac(self, v=None):
        v = self.value if v is None else v
        if self.mapping:
            return self.mapping[0](v)
        return (v - self.lo) / (self.hi - self.lo) if self.hi != self.lo else 0

    def from_frac(self, f):
        f = max(0.0, min(1.0, f))
        if self.mapping:
            return self.mapping[1](f)
        return self.lo + f * (self.hi - self.lo)

    def set_value(self, v, emit=False):
        v = max(self.lo, min(self.hi, v))
        if v != self.value:
            self.value = v
            self.queue_draw()
            if emit:
                self.emit("value-changed")

    def do_measure(self, orientation, for_size):
        if orientation == self.orientation:
            return self.length, self.length, -1, -1
        return 24, 24, -1, -1

    def _geom(self):
        w, h = self.get_width(), self.get_height()
        pad = 10
        if self.orientation == Gtk.Orientation.HORIZONTAL:
            return pad, w - pad, h / 2
        return pad, h - pad, w / 2

    def _pos_to_frac(self, x, y):
        a, b, _c = self._geom()
        if self.orientation == Gtk.Orientation.HORIZONTAL:
            return (x - a) / max(1, b - a)
        return 1 - (y - a) / max(1, b - a)

    def _begin(self, g, x, y):
        self.grab_focus()
        self.dragging = True
        self._start = (x, y)
        self.set_value(self.from_frac(self._pos_to_frac(x, y)), True)

    def _update(self, g, dx, dy):
        x, y = self._start[0] + dx, self._start[1] + dy
        self.set_value(self.from_frac(self._pos_to_frac(x, y)), True)

    def _end(self, *_a):
        self.dragging = False
        self.queue_draw()
        self.emit("released")

    def _scroll(self, _c, dx, dy):
        step = (self.hi - self.lo) / 50 if not self.mapping else None
        if step:
            self.set_value(self.value - dy * step, True)
        else:
            self.set_value(self.from_frac(self.frac() - dy * 0.03), True)
        self.emit("released")
        return True

    def _key(self, _c, keyval, _code, _state):
        d = {Gdk.KEY_Right: 1, Gdk.KEY_Up: 1, Gdk.KEY_Left: -1, Gdk.KEY_Down: -1}.get(keyval)
        if d is None:
            return False
        self.set_value(self.from_frac(self.frac() + d * 0.02), True)
        self.emit("released")
        return True

    def do_snapshot(self, snap):
        th = theme.get()
        w, h = self.get_width(), self.get_height()
        cr = snap.append_cairo(Graphene.Rect().init(0, 0, w, h))
        a, b, c = self._geom()
        f = max(0, min(1, self.frac()))
        horiz = self.orientation == Gtk.Orientation.HORIZONTAL
        tw = 4
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_width(tw)
        p = a + f * (b - a) if horiz else b - f * (b - a)
        cr.set_source_rgba(*th.rgb("track"))
        if horiz:
            cr.move_to(p, c)
            cr.line_to(b, c)
        else:
            cr.move_to(c, a)
            cr.line_to(c, p)
        cr.stroke()
        cr.set_source_rgba(*th.rgb("accent"))
        if horiz:
            cr.move_to(a, c)
            cr.line_to(p, c)
        else:
            cr.move_to(c, p)
            cr.line_to(c, b)
        cr.stroke()
        tx, ty = (p, c) if horiz else (c, p)
        cr.arc(tx, ty, 10, 0, 2 * math.pi)
        cr.set_source_rgba(*th.rgb("thumb"))
        cr.fill_preserve()
        cr.set_line_width(1)
        cr.set_source_rgba(*th.rgb("thumb-line"))
        cr.stroke()
        r = 7 if (self.hover or self.dragging) else 6
        if self.dragging:
            r = 5
        cr.arc(tx, ty, r, 0, 2 * math.pi)
        cr.set_source_rgba(*th.rgb("accent"))
        cr.fill()


# =========================================================================== swatches

class Swatch(Gtk.Widget):
    """Round colour sample used in the palette and as primary / secondary colour."""
    __gtype_name__ = "FenestraPaintSwatch"

    def __init__(self, rgba=None, size=20, ring=False):
        super().__init__()
        self.rgba = rgba
        self.size = size
        self.ring = ring
        self.selected = False
        self.add_css_class("swatch")
        theme.get().connect(self.queue_draw)

    def set_rgba(self, rgba):
        self.rgba = rgba
        self.queue_draw()

    def set_selected(self, s):
        self.selected = s
        self.queue_draw()

    def do_measure(self, orientation, for_size):
        n = self.size + (8 if self.ring else 0)
        return n, n, -1, -1

    def do_snapshot(self, snap):
        th = theme.get()
        w, h = self.get_width(), self.get_height()
        cr = snap.append_cairo(Graphene.Rect().init(0, 0, w, h))
        cx, cy = w / 2, h / 2
        r = self.size / 2
        if self.rgba is None:
            cr.arc(cx, cy, r - 0.5, 0, 2 * math.pi)
            cr.set_source_rgba(*th.rgb("empty-swatch"))
            cr.set_line_width(1)
            cr.stroke()
            return
        if self.rgba[3] < 1:
            cr.save()
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.clip()
            for i in range(0, int(self.size) + 4, 4):
                for j in range(0, int(self.size) + 4, 4):
                    cr.set_source_rgb(*((1, 1, 1) if (i + j) // 4 % 2 else (0.8, 0.8, 0.8)))
                    cr.rectangle(cx - r + i, cy - r + j, 4, 4)
                    cr.fill()
            cr.restore()
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgba(*self.rgba)
        cr.fill()
        cr.arc(cx, cy, r - 0.5, 0, 2 * math.pi)
        cr.set_line_width(1)
        cr.set_source_rgba(*th.rgb("swatch-line"))
        cr.stroke()
        if self.selected and self.ring:
            cr.arc(cx, cy, r + 3, 0, 2 * math.pi)
            cr.set_line_width(1.6)
            cr.set_source_rgba(*th.rgb("accent"))
            cr.stroke()


class ColorWheel(Gtk.Widget):
    """'Edit colours' glyph: hue wheel with a plus badge (own drawing)."""
    __gtype_name__ = "FenestraPaintColorWheel"

    def do_measure(self, orientation, for_size):
        return 32, 32, -1, -1

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        cr = snap.append_cairo(Graphene.Rect().init(0, 0, w, h))
        cx, cy, r = w / 2 - 1, h / 2 + 1, 12
        import colorsys
        n = 72
        for i in range(n):
            a0 = 2 * math.pi * i / n - math.pi / 2
            a1 = 2 * math.pi * (i + 1.5) / n - math.pi / 2
            rr, gg, bb = colorsys.hsv_to_rgb(i / n, 1, 1)
            pat = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
            pat.add_color_stop_rgb(0, 1, 1, 1)
            pat.add_color_stop_rgb(1, rr, gg, bb)
            cr.move_to(cx, cy)
            cr.arc(cx, cy, r, a0, a1)
            cr.close_path()
            cr.set_source(pat)
            cr.fill()
        th = theme.get()
        bx, by = cx + 9, cy - 9
        cr.arc(bx, by, 5.5, 0, 2 * math.pi)
        cr.set_source_rgba(*th.rgb("bar"))
        cr.fill_preserve()
        cr.set_source_rgba(*th.rgb("fg"))
        cr.set_line_width(1)
        cr.stroke()
        cr.move_to(bx - 3, by)
        cr.line_to(bx + 3, by)
        cr.move_to(bx, by - 3)
        cr.line_to(bx, by + 3)
        cr.stroke()


class Glyph(Gtk.Widget):
    """Widget drawn by a python callable(cr, w, h, theme) - shape icons, selection icon..."""
    __gtype_name__ = "FenestraPaintGlyph"

    def __init__(self, fn, w=16, h=16):
        super().__init__()
        self.fn = fn
        self.w, self.h = w, h
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        theme.get().connect(self.queue_draw)

    def do_measure(self, orientation, for_size):
        n = self.w if orientation == Gtk.Orientation.HORIZONTAL else self.h
        return n, n, -1, -1

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        cr = snap.append_cairo(Graphene.Rect().init(0, 0, w, h))
        th = theme.get()
        col = self.get_color()
        cr.set_source_rgba(col.red, col.green, col.blue, col.alpha)
        self.fn(cr, w, h, th)


def surface_picture(surf):
    """Gtk.Picture of a cairo surface (brush previews)."""
    from . import raster
    pic = Gtk.Picture.new_for_paintable(raster.texture_from_surface(surf))
    pic.set_can_shrink(False)
    return pic


def spin_entry(value, lo, hi, width=6, digits=0):
    sp = Gtk.SpinButton.new_with_range(lo, hi, 1)
    sp.set_digits(digits)
    sp.set_value(value)
    sp.set_width_chars(width)
    sp.add_css_class("fluent-spin")
    return sp


def radio_group(options, active, cb):
    """Vertical Fluent radio buttons; options = [(key, text)]."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    first = None
    btns = {}
    for key, text in options:
        r = Gtk.CheckButton(label=text)
        r.add_css_class("fluent-radio")
        if first is None:
            first = r
        else:
            r.set_group(first)
        r.set_active(key == active)
        r.connect("toggled", lambda b, k=key: cb(k) if b.get_active() else None)
        box.append(r)
        btns[key] = r
    box.btns = btns
    return box


def checkbox(text, active, cb=None):
    c = Gtk.CheckButton(label=text)
    c.add_css_class("fluent-check")
    c.set_active(active)
    if cb:
        c.connect("toggled", lambda b: cb(b.get_active()))
    return c


_ = _  # re-export for modules that import from widgets

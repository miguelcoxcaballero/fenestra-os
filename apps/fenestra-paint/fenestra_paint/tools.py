"""Tools: selection (rectangle / free-form), pencil, brushes, eraser, fill, colour picker,
magnifier, text and shapes.

Coordinates passed to tools are image coordinates (floats).  Tools paint into their own
surfaces and show them through ``Document.preview`` until they commit with an undoable
``Document.modify_layer`` (or a patch entry built from a copy of the layer)."""
from __future__ import annotations

import math

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Pango, PangoCairo  # noqa: E402

from . import brushes, raster, shapes, theme  # noqa: E402
from .document import PatchEntry  # noqa: E402
from .i18n import _  # noqa: E402

HANDLES = ["nw", "n", "ne", "w", "e", "sw", "s", "se"]
CURSORS = {"n": "n-resize", "s": "s-resize", "e": "e-resize", "w": "w-resize", "ne": "ne-resize",
           "nw": "nw-resize", "se": "se-resize", "sw": "sw-resize"}


def norm_box(b):
    x0, y0, x1, y1 = b
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def handle_points(cv, box):
    x0, y0, x1, y1 = norm_box(box)
    a = cv.to_widget(x0, y0)
    b = cv.to_widget(x1, y1)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    return {"nw": (a[0], a[1]), "n": (mx, a[1]), "ne": (b[0], a[1]), "w": (a[0], my), "e": (b[0], my),
            "sw": (a[0], b[1]), "s": (mx, b[1]), "se": (b[0], b[1])}


def hit_handle(cv, box, wx, wy, r=6):
    for name, (hx, hy) in handle_points(cv, box).items():
        if abs(wx - hx) <= r and abs(wy - hy) <= r:
            return name
    return None


def apply_handle(box, name, dx, dy, keep_ratio=False):
    x0, y0, x1, y1 = box
    if "w" in name:
        x0 += dx
    if "e" in name:
        x1 += dx
    if "n" in name:
        y0 += dy
    if "s" in name:
        y1 += dy
    if keep_ratio and len(name) == 2:
        bw, bh = box[2] - box[0], box[3] - box[1]
        if bw and bh:
            nw, nh = x1 - x0, y1 - y0
            s = max(abs(nw / bw), abs(nh / bh))
            nw, nh = math.copysign(abs(bw) * s, nw or 1), math.copysign(abs(bh) * s, nh or 1)
            if "w" in name:
                x0 = x1 - nw
            else:
                x1 = x0 + nw
            if "n" in name:
                y0 = y1 - nh
            else:
                y1 = y0 + nh
    return (x0, y0, x1, y1)


def draw_handle(cr, x, y, th, round_=False):
    s = 7
    if round_:
        cr.arc(x, y, 4, 0, 2 * math.pi)
    else:
        cr.rectangle(int(x - s / 2) + 0.5, int(y - s / 2) + 0.5, s - 1, s - 1)
    cr.set_source_rgba(*th.rgb("handle"))
    cr.fill_preserve()
    cr.set_source_rgba(*th.rgb("handle-line"))
    cr.set_line_width(1)
    cr.stroke()


def ants(cr, path_fn):
    """Marching-ants outline: white line under a black dashed one."""
    cr.set_line_width(1)
    path_fn()
    cr.set_source_rgb(1, 1, 1)
    cr.stroke()
    path_fn()
    cr.set_dash([4, 4])
    cr.set_source_rgb(0.1, 0.1, 0.1)
    cr.stroke()
    cr.set_dash([])


def widget_bounds(cv, pts):
    ws = [cv.to_widget(x, y) for x, y in pts]
    xs, ys = [p[0] for p in ws], [p[1] for p in ws]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def shift(state):
    return bool(state & Gdk.ModifierType.SHIFT_MASK)


def ctrl(state):
    return bool(state & Gdk.ModifierType.CONTROL_MASK)


class Tool:
    name = ""
    cursor = "crosshair"
    uses_size = False
    uses_opacity = False

    def __init__(self, win):
        self.win = win

    @property
    def doc(self):
        return self.win.doc

    def activate(self):
        pass

    def deactivate(self):
        self.commit()

    @property
    def pending(self):
        return False

    def press(self, x, y, button, state, n):
        pass

    def drag(self, x, y, state):
        pass

    def release(self, x, y, button):
        pass

    def key(self, keyval, state):
        return False

    def draw_overlay(self, cr, cv):
        pass

    def overlay_rect(self, cv):
        """Widget-space rectangle the overlay draws in, or None (nothing to draw)."""
        return None

    def cursor_at(self, x, y, cv):
        return self.cursor

    def commit(self):
        pass

    def cancel(self):
        self.commit()

    def refresh(self):
        """Colours / size / style changed while the tool has something pending."""

    def color_for(self, button):
        return self.win.primary if button != 3 else self.win.secondary

    def layer_ok(self):
        if not self.doc.layer.visible:
            self.win.notify(_("The selected layer is hidden. Show it to draw on it."))
            return False
        return True


# =========================================================================== strokes

class StrokeTool(Tool):
    uses_size = True
    uses_opacity = True

    def __init__(self, win, kind):
        super().__init__(win)
        self.kind = kind
        self.name = kind
        self.stroke = None
        self.timer = 0
        self.last = None

    @property
    def size_key(self):
        return "pencil" if self.kind == "pencil" else "eraser" if self.kind == "eraser" else "brush"

    @property
    def stroke_kind(self):
        return self.win.brush if self.kind == "brush" else self.kind

    def cursor_at(self, x, y, cv):
        return "crosshair" if self.kind != "eraser" else "cell"

    def press(self, x, y, button, state, n):
        if self.stroke is not None or not self.layer_ok():
            return
        doc = self.doc
        kind = self.stroke_kind
        self.stroke = brushes.Stroke(kind, self.color_for(button), self.win.size_for(self.size_key),
                                     doc.width, doc.height, erase=self.kind == "eraser",
                                     seed=int(x * 7 + y * 13) & 0xffff)
        opacity = self.win.opacity
        st = self.stroke
        doc.begin_cache()
        doc.preview = [lambda cr: st.composite(cr, opacity)]
        self.last = (x, y)
        self._add(x, y)
        if kind == "airbrush":
            self.timer = GLib.timeout_add(35, self._spray)

    def _spray(self):
        if self.stroke is None or self.last is None:
            self.timer = 0
            return False
        self._add(*self.last)
        return True

    def _add(self, x, y):
        r = self.stroke.add(x, y)
        if r is not None:
            self.doc.damage(r)

    def drag(self, x, y, state):
        if self.stroke is None:
            return
        self.last = (x, y)
        self._add(x, y)

    def release(self, x, y, button):
        self.commit()

    @property
    def pending(self):
        return self.stroke is not None

    def commit(self):
        st = self.stroke
        if st is None:
            return
        self.stroke = None
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        doc = self.doc
        doc.preview = []
        doc.end_cache()
        opacity = self.win.opacity
        if st.bbox is not None:
            label = {"pencil": _("Pencil"), "eraser": _("Eraser")}.get(self.kind, _("Brush"))
            doc.modify_layer(st.bbox, lambda cr: st.composite(cr, opacity), label)


# =========================================================================== fill / picker / magnifier

class FillTool(Tool):
    name = "fill"
    cursor = "crosshair"
    uses_opacity = True
    TOLERANCE = 24

    def press(self, x, y, button, state, n):
        doc = self.doc
        if not self.layer_ok():
            return
        mask, bbox = raster.flood_mask(doc.layer.surface, x, y, self.TOLERANCE)
        if mask is None:
            return
        ms = raster.mask_surface_from_bytes(mask, doc.width, doc.height)
        r, g, b, a = self.color_for(button)
        op = self.win.opacity

        def fn(cr):
            cr.set_source_rgba(r, g, b, a * op)
            cr.mask_surface(ms, 0, 0)
        doc.modify_layer(bbox, fn, _("Fill"))


class PickerTool(Tool):
    name = "picker"
    cursor = "crosshair"

    def press(self, x, y, button, state, n):
        px = raster.get_pixel(self.doc.composite, int(x), int(y))
        if px is None:
            return
        if px[3] == 0:
            px = (1.0, 1.0, 1.0, 1.0) if self.doc.bg_visible else (1.0, 1.0, 1.0, 1.0)
        rgba = (px[0], px[1], px[2], 1.0)
        if button == 3:
            self.win.set_secondary(rgba)
        else:
            self.win.set_primary(rgba)

    def release(self, x, y, button):
        GLib.idle_add(lambda: (self.win.restore_previous_tool(), False)[1])


class MagnifierTool(Tool):
    name = "magnifier"
    cursor = "zoom-in"

    def press(self, x, y, button, state, n):
        cv = self.win.canvas
        cv.zoom_step(-1 if button == 3 else 1, cv.to_widget(x, y))


# =========================================================================== selection

class Selection:
    def __init__(self, box, kind="rect", poly=None, mask=None, outlines=None):
        self.box = box                  # (x0, y0, x1, y1) image coords (floats while floating)
        self.kind = kind                # rect | free | mask
        self.poly = poly                # free-form points
        self.mask = mask                # A8 surface of the box size (free / inverted)
        self.outlines = outlines or []  # extra outlines for display (inverted selection)
        self.floating = None            # lifted pixels (unscaled)
        self.orig = None                # copy of the layer before lifting / pasting
        self.layer_id = None
        self.src = None                 # rect the pixels were lifted from

    @property
    def rect(self):
        x0, y0, x1, y1 = norm_box(self.box)
        return (int(round(x0)), int(round(y0)), max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0))))


class SelectTool(Tool):
    name = "select"

    def __init__(self, win):
        super().__init__(win)
        self.mode = "rect"          # rect | free
        self.sel: Selection | None = None
        self.op = None
        self.start = None
        self.poly = []
        self.drag_box = None

    # ------------------------------------------------------------------ state
    @property
    def pending(self):
        return self.sel is not None and self.sel.floating is not None

    @property
    def has_selection(self):
        return self.sel is not None

    def cursor_at(self, x, y, cv):
        if self.sel is not None:
            wx, wy = cv.to_widget(x, y)
            h = hit_handle(cv, self.sel.box, wx, wy)
            if h:
                return CURSORS[h]
            if self._inside(x, y):
                return "move"
        return "crosshair"

    def _inside(self, x, y):
        x0, y0, x1, y1 = norm_box(self.sel.box)
        return x0 <= x <= x1 and y0 <= y <= y1

    # ------------------------------------------------------------------ input
    def press(self, x, y, button, state, n):
        cv = self.win.canvas
        wx, wy = cv.to_widget(x, y)
        if self.sel is not None:
            h = hit_handle(cv, self.sel.box, wx, wy)
            if h is not None:
                if not self.lift():
                    return
                self.op = ("resize", h, self.sel.box, (x, y))
                return
            if self._inside(x, y):
                if not self.lift():
                    return
                if ctrl(state):  # Ctrl+drag stamps a copy
                    self._stamp()
                self.op = ("move", self.sel.box, (x, y))
                return
            self.commit()
        self.start = (x, y)
        if self.mode == "free":
            self.poly = [self._clamp(x, y)]
            self.op = ("free",)
        else:
            self.op = ("rect",)
            self.drag_box = None

    def _clamp(self, x, y):
        return (max(0, min(self.doc.width, x)), max(0, min(self.doc.height, y)))

    def drag(self, x, y, state):
        if self.op is None:
            return
        kind = self.op[0]
        if kind == "rect":
            x0, y0 = self._clamp(*self.start)
            x1, y1 = self._clamp(x, y)
            if shift(state):
                d = max(abs(x1 - x0), abs(y1 - y0))
                x1 = x0 + math.copysign(d, x1 - x0)
                y1 = y0 + math.copysign(d, y1 - y0)
            self.drag_box = (round(x0), round(y0), round(x1), round(y1))
            self.win.update_status(selection=self.drag_box)
        elif kind == "free":
            self.poly.append(self._clamp(x, y))
        elif kind == "move":
            _k, box, (sx, sy) = self.op
            dx, dy = round(x - sx), round(y - sy)
            self._set_box((box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy))
        elif kind == "resize":
            _k, h, box, (sx, sy) = self.op
            nb = apply_handle(box, h, round(x - sx), round(y - sy), shift(state))
            self._set_box(nb)

    def release(self, x, y, button):
        if self.op is None:
            return
        kind = self.op[0]
        self.op = None
        if kind == "rect":
            b = self.drag_box
            self.drag_box = None
            if b is None or abs(b[2] - b[0]) < 1 or abs(b[3] - b[1]) < 1:
                self.sel = None
            else:
                self.sel = Selection(norm_box(b))
        elif kind == "free":
            pts = self.poly
            self.poly = []
            if len(pts) < 3:
                self.sel = None
            else:
                self.sel = self._free_selection(pts)
        self.win.on_selection_changed()

    def _free_selection(self, pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, y0 = int(math.floor(min(xs))), int(math.floor(min(ys)))
        x1, y1 = int(math.ceil(max(xs))), int(math.ceil(max(ys)))
        if x1 - x0 < 1 or y1 - y0 < 1:
            return None
        m = cairo.ImageSurface(cairo.FORMAT_A8, x1 - x0, y1 - y0)
        cr = cairo.Context(m)
        cr.translate(-x0, -y0)
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.close_path()
        cr.fill()
        m.flush()
        return Selection((x0, y0, x1, y1), "free", pts, m)

    def key(self, keyval, state):
        if self.sel is None:
            return False
        step = 10 if shift(state) else 1
        d = {Gdk.KEY_Left: (-step, 0), Gdk.KEY_Right: (step, 0), Gdk.KEY_Up: (0, -step),
             Gdk.KEY_Down: (0, step)}.get(keyval)
        if d is not None:
            if self.lift():
                b = self.sel.box
                self._set_box((b[0] + d[0], b[1] + d[1], b[2] + d[0], b[3] + d[1]))
            return True
        if keyval == Gdk.KEY_Escape:
            self.commit()
            return True
        if keyval == Gdk.KEY_Return:
            self.commit()
            return True
        return False

    # ------------------------------------------------------------------ floating
    def _paint_float(self, cr):
        s = self.sel
        if s is None or s.floating is None:
            return
        x0, y0, x1, y1 = norm_box(s.box)
        fw, fh = s.floating.get_width(), s.floating.get_height()
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        cr.translate(x0, y0)
        if (bw, bh) != (fw, fh):
            cr.scale(bw / fw, bh / fh)
        cr.set_source_surface(s.floating, 0, 0)
        if (bw, bh) != (fw, fh):
            cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.paint()

    def _float_rect(self):
        x0, y0, x1, y1 = norm_box(self.sel.box)
        return (math.floor(x0) - 1, math.floor(y0) - 1, math.ceil(x1 - x0) + 2, math.ceil(y1 - y0) + 2)

    def _set_box(self, box):
        old = self._float_rect()
        self.sel.box = box
        self.doc.damage(raster.union(old, self._float_rect()))
        self.win.update_status(selection=box)

    def lift(self):
        """Turn a marked selection into floating pixels (cut from the layer)."""
        s = self.sel
        if s is None:
            return False
        if s.floating is not None:
            return True
        doc = self.doc
        if not self.layer_ok():
            return False
        layer = doc.layer
        r = raster.clip_rect(s.rect, doc.width, doc.height)
        if r is None:
            return False
        s.orig = raster.copy_surface(layer.surface)
        s.layer_id = layer.id
        content = raster.copy_surface(layer.surface, *r)
        if s.mask is not None:
            cr = cairo.Context(content)
            cr.set_operator(cairo.OPERATOR_DEST_IN)
            cr.mask_surface(s.mask, s.rect[0] - r[0], s.rect[1] - r[1])
            content.flush()
        if self.win.transparent_selection:
            content = raster.key_out(content, self.win.secondary)
        # cut the pixels out of the layer (recorded in the history at commit)
        cr = cairo.Context(layer.surface)
        if s.mask is not None:
            cr.set_operator(cairo.OPERATOR_DEST_OUT)
            cr.mask_surface(s.mask, s.rect[0], s.rect[1])
        else:
            cr.rectangle(*r)
            cr.set_operator(cairo.OPERATOR_CLEAR)
            cr.fill()
        layer.surface.flush()
        s.floating = content
        s.src = r
        s.box = (r[0], r[1], r[0] + r[2], r[1] + r[3])
        doc.begin_cache()
        doc.preview = [self._paint_float]
        doc.damage(r)
        return True

    def _stamp(self):
        """Leave a copy of the floating pixels at the current place (Ctrl+drag)."""
        s = self.sel
        layer = self.doc.layer
        cr = cairo.Context(layer.surface)
        self._paint_float(cr)
        layer.surface.flush()

    def float_surface(self, surf, x, y):
        """Paste: surf becomes a floating selection at (x, y)."""
        self.commit()
        doc = self.doc
        s = Selection((x, y, x + surf.get_width(), y + surf.get_height()))
        s.floating = surf
        s.orig = raster.copy_surface(doc.layer.surface)
        s.layer_id = doc.layer.id
        s.src = None
        self.sel = s
        doc.begin_cache()
        doc.preview = [self._paint_float]
        doc.damage(self._float_rect())
        self.win.on_selection_changed()

    def commit(self):
        s = self.sel
        if s is None:
            return
        self.sel = None
        doc = self.doc
        if s.floating is not None:
            doc.preview = []
            doc.end_cache()
            layer = doc.layer_by_id(s.layer_id) or doc.layer
            dst = None
            x0, y0, x1, y1 = norm_box(s.box)
            dst = raster.clip_rect((math.floor(x0), math.floor(y0), math.ceil(x1 - x0) + 1, math.ceil(y1 - y0) + 1),
                                   doc.width, doc.height)
            cr = cairo.Context(layer.surface)
            self.sel = s
            self._paint_float(cr)
            self.sel = None
            layer.surface.flush()
            self._record(layer, s, raster.union(s.src, dst), _("Move selection"))
        else:
            self.win.canvas.queue_draw()
        self.win.on_selection_changed()

    def _record(self, layer, s, region, label):
        doc = self.doc
        if region is not None and s.orig is not None:
            region = raster.clip_rect(region, doc.width, doc.height)
            if region is not None:
                before = raster.pack(s.orig, region)
                after = raster.pack(layer.surface, region)
                if before != after:
                    doc.history.push(PatchEntry(label, layer.id, region, before, after))
                doc.damage(region)

    def cancel(self):
        s = self.sel
        if s is None:
            return
        self.sel = None
        doc = self.doc
        if s.floating is not None:
            doc.preview = []
            doc.end_cache()
            layer = doc.layer_by_id(s.layer_id) or doc.layer
            if s.src is not None and s.orig is not None:
                raster.write_rect(layer.surface, s.src, raster.read_rect(s.orig, s.src))
            doc.damage()
        self.win.on_selection_changed()
        self.win.canvas.queue_draw()

    def delete(self):
        s = self.sel
        if s is None:
            return
        doc = self.doc
        if s.floating is not None:
            self.sel = None
            doc.preview = []
            doc.end_cache()
            layer = doc.layer_by_id(s.layer_id) or doc.layer
            self._record(layer, s, s.src, _("Delete"))
            doc.damage()
        else:
            self.sel = None
            r = s.rect

            def fn(cr):
                if s.mask is not None:
                    cr.set_operator(cairo.OPERATOR_DEST_OUT)
                    cr.mask_surface(s.mask, r[0], r[1])
                else:
                    cr.set_operator(cairo.OPERATOR_CLEAR)
                    cr.paint()
            doc.modify_layer(r, fn, _("Delete"))
        self.win.on_selection_changed()

    def content(self):
        """Pixels of the selection (for copy)."""
        s = self.sel
        if s is None:
            return None
        if s.floating is not None:
            x0, y0, x1, y1 = norm_box(s.box)
            bw, bh = int(round(x1 - x0)), int(round(y1 - y0))
            if (bw, bh) != (s.floating.get_width(), s.floating.get_height()):
                return raster.scaled(s.floating, bw, bh)
            return raster.copy_surface(s.floating)
        r = raster.clip_rect(s.rect, self.doc.width, self.doc.height)
        if r is None:
            return None
        content = raster.copy_surface(self.doc.layer.surface, *r)
        if s.mask is not None:
            cr = cairo.Context(content)
            cr.set_operator(cairo.OPERATOR_DEST_IN)
            cr.mask_surface(s.mask, s.rect[0] - r[0], s.rect[1] - r[1])
            content.flush()
        return content

    def transform_floating(self, fn):
        """Apply fn(surface) -> surface to the selection, keeping its centre."""
        if not self.lift():
            return
        s = self.sel
        cur = self.content()
        out = fn(cur)
        x0, y0, x1, y1 = norm_box(s.box)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = out.get_width(), out.get_height()
        old = self._float_rect()
        s.floating = out
        nx, ny = round(cx - w / 2), round(cy - h / 2)
        s.box = (nx, ny, nx + w, ny + h)
        self.doc.damage(raster.union(old, self._float_rect()))
        self.win.on_selection_changed()

    def select_all(self):
        self.commit()
        self.sel = Selection((0, 0, self.doc.width, self.doc.height))
        self.win.on_selection_changed()

    def invert(self):
        s = self.sel
        if s is None or s.floating is not None:
            if s is not None:
                self.commit()
            return
        doc = self.doc
        m = cairo.ImageSurface(cairo.FORMAT_A8, doc.width, doc.height)
        cr = cairo.Context(m)
        cr.set_source_rgba(0, 0, 0, 1)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_DEST_OUT)
        r = s.rect
        if s.mask is not None:
            cr.mask_surface(s.mask, r[0], r[1])
        else:
            cr.rectangle(*r)
            cr.fill()
        m.flush()
        outline = s.poly if s.kind == "free" else [(r[0], r[1]), (r[0] + r[2], r[1]), (r[0] + r[2], r[1] + r[3]),
                                                   (r[0], r[1] + r[3])]
        self.sel = Selection((0, 0, doc.width, doc.height), "mask", None, m, [outline])
        self.win.on_selection_changed()

    # ------------------------------------------------------------------ overlay
    def overlay_rect(self, cv):
        if self.op is not None and self.op[0] == "rect" and self.drag_box is not None:
            b = self.drag_box
            return widget_bounds(cv, [(b[0], b[1]), (b[2], b[3])])
        if self.op is not None and self.op[0] == "free" and len(self.poly) > 1:
            return widget_bounds(cv, self.poly)
        s = self.sel
        if s is None:
            return None
        pts = [(s.box[0], s.box[1]), (s.box[2], s.box[3])]
        for ol in s.outlines:
            pts += ol
        return widget_bounds(cv, pts)

    def draw_overlay(self, cr, cv):
        th = theme.get()
        if self.op is not None and self.op[0] == "rect" and self.drag_box is not None:
            x0, y0, x1, y1 = norm_box(self.drag_box)
            a, b = cv.to_widget(x0, y0), cv.to_widget(x1, y1)
            ants(cr, lambda: cr.rectangle(int(a[0]) + 0.5, int(a[1]) + 0.5, int(b[0] - a[0]), int(b[1] - a[1])))
            return
        if self.op is not None and self.op[0] == "free" and len(self.poly) > 1:
            def p():
                cr.move_to(*cv.to_widget(*self.poly[0]))
                for pt in self.poly[1:]:
                    cr.line_to(*cv.to_widget(*pt))
            ants(cr, p)
            return
        s = self.sel
        if s is None:
            return
        if s.kind == "free" and s.floating is None and s.poly:
            def fp():
                cr.move_to(*cv.to_widget(*s.poly[0]))
                for pt in s.poly[1:]:
                    cr.line_to(*cv.to_widget(*pt))
                cr.close_path()
            ants(cr, fp)
        for ol in s.outlines:
            def op_(ol=ol):
                cr.move_to(*cv.to_widget(*ol[0]))
                for pt in ol[1:]:
                    cr.line_to(*cv.to_widget(*pt))
                cr.close_path()
            ants(cr, op_)
        x0, y0, x1, y1 = norm_box(s.box)
        a, b = cv.to_widget(x0, y0), cv.to_widget(x1, y1)
        ants(cr, lambda: cr.rectangle(int(a[0]) + 0.5, int(a[1]) + 0.5, int(b[0] - a[0]), int(b[1] - a[1])))
        for hx, hy in handle_points(cv, s.box).values():
            draw_handle(cr, hx, hy, th)


# =========================================================================== shapes

def render_shape(kind, box, pts, outline, fill, line_rgba, fill_rgba, size):
    """Render a shape into its own surface; returns (surface, ox, oy) or None."""
    probe = cairo.Context(cairo.ImageSurface(cairo.FORMAT_A8, 1, 1))
    shapes.path(probe, kind, *box, pts=pts)
    ex = probe.path_extents()
    m = size / 2 + 4
    ox, oy = int(math.floor(ex[0] - m)), int(math.floor(ex[1] - m))
    w, h = int(math.ceil(ex[2] + m)) - ox, int(math.ceil(ex[3] + m)) - oy
    if w <= 0 or h <= 0 or w > 20000 or h > 20000:
        return None
    surf = raster.new_surface(w, h)
    cr = cairo.Context(surf)
    cr.translate(-ox, -oy)
    is_open = kind in ("line", "curve")
    if fill != "none" and not is_open:
        _fill(cr, kind, box, pts, fill, fill_rgba, size)
    if outline != "none" or is_open:
        style = "solid" if (outline == "none" and is_open) else outline
        _outline(cr, kind, box, pts, style, line_rgba, size, ox, oy, w, h)
    surf.flush()
    return surf, ox, oy


def _fill(cr, kind, box, pts, style, rgba, size):
    r, g, b, a = rgba
    cr.save()
    shapes.path(cr, kind, *box, pts=pts)
    if style in ("solid", "marker"):
        cr.set_source_rgba(r, g, b, a * (0.55 if style == "marker" else 1))
        cr.fill()
    elif style == "crayon":
        cr.clip()
        cr.set_source_rgba(r, g, b, a)
        cr.mask(brushes.grain_pattern("crayon"))
    elif style == "watercolor":
        cr.clip_preserve()
        cr.set_source_rgba(r, g, b, a * 0.40)
        cr.fill_preserve()
        cr.set_line_width(max(4, size * 2))
        cr.set_source_rgba(r, g, b, a * 0.30)
        cr.stroke()
        cr.set_source_rgba(r, g, b, a * 0.12)
        cr.mask(brushes.grain_pattern("watercolor"))
    elif style == "natural_pencil":
        ex = cr.fill_extents()
        cr.clip()
        cr.push_group()
        cr.set_source_rgba(r, g, b, a)
        cr.set_line_width(1.2)
        gap = 4
        x0, y0, x1, y1 = ex
        d = (x1 - x0) + (y1 - y0)
        t = -d
        while t < d:
            cr.move_to(x0 + t, y0)
            cr.line_to(x0 + t + (y1 - y0), y1)
            t += gap
        cr.stroke()
        cr.pop_group_to_source()
        cr.mask(brushes.grain_pattern("natural_pencil"))
    elif style == "oil":
        ex = cr.fill_extents()
        cr.clip()
        cr.set_source_rgba(r, g, b, a * 0.85)
        cr.paint()
        import random
        rnd = random.Random(int(ex[0] * 3 + ex[1]))
        x0, y0, x1, y1 = ex
        y = y0
        while y < y1:
            sh = rnd.uniform(-0.18, 0.15)
            f = (lambda v: v * (1 + sh)) if sh < 0 else (lambda v: v + (1 - v) * sh)
            cr.set_source_rgba(f(r), f(g), f(b), a * rnd.uniform(0.4, 0.9))
            cr.set_line_width(rnd.uniform(1.5, 4))
            cr.move_to(x0, y)
            cr.curve_to(x0 + (x1 - x0) / 3, y + rnd.uniform(-3, 3), x0 + 2 * (x1 - x0) / 3,
                        y + rnd.uniform(-3, 3), x1, y)
            cr.stroke()
            y += rnd.uniform(2, 5)
    cr.restore()


def _outline(cr, kind, box, pts, style, rgba, size, ox, oy, w, h):
    cr.save()
    if style == "solid":
        shapes.path(cr, kind, *box, pts=pts)
        cr.set_source_rgba(*rgba)
        cr.set_line_width(size)
        if kind in ("line", "curve"):
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND if kind in ("oval", "heart", "callout_cloud", "curve",
                                                           "rounded_rectangle", "callout_oval")
                         else cairo.LINE_JOIN_MITER)
        cr.stroke()
        cr.restore()
        return
    cr.identity_matrix()
    probe = cairo.Context(cairo.ImageSurface(cairo.FORMAT_A8, 1, 1))
    probe.set_tolerance(0.3)
    shapes.path(probe, kind, *box, pts=pts)
    kind_map = {"crayon": "crayon", "marker": "marker", "oil": "oil", "natural_pencil": "natural_pencil",
                "watercolor": "watercolor"}
    bk = kind_map.get(style, "brush")
    for sub in brushes.flatten_path(probe):
        local = [(x - ox, y - oy) for x, y in sub]
        if bk in brushes.INCREMENTAL:
            local = brushes.densify(local, max(1.0, size / 4))
        st = brushes.render_stroke(bk, local, rgba, size, w, h, seed=7)
        st.composite(cr, 1.0)
    cr.restore()


class ShapeTool(Tool):
    name = "shape"
    uses_size = True
    uses_opacity = True

    def __init__(self, win):
        super().__init__(win)
        self.s = None            # editing state dict
        self.op = None
        self.cache = None        # (surface, ox, oy)
        self.rect = None         # damaged rect of the current preview

    @property
    def kind(self):
        return self.win.shape

    @property
    def pending(self):
        return self.s is not None

    # ------------------------------------------------------------------ geometry
    def _box_of_pts(self, pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def _render(self):
        s = self.s
        old = self.rect
        if s is None:
            self.cache = None
            self.rect = None
        else:
            line, fill = (self.win.primary, self.win.secondary) if s["button"] != 3 \
                else (self.win.secondary, self.win.primary)
            outline = self.win.outline_style
            fstyle = self.win.fill_style
            res = render_shape(s["kind"], s["box"], s.get("pts"), outline, fstyle, line, fill,
                               self.win.size_for("shape"))
            self.cache = res
            self.rect = (res[1], res[2], res[0].get_width(), res[0].get_height()) if res else None
        self.doc.damage(raster.union(old, self.rect) or (0, 0, 1, 1))
        self.win.canvas.queue_draw()

    def _paint(self, cr):
        if self.cache is None:
            return
        surf, ox, oy = self.cache
        cr.set_source_surface(surf, ox, oy)
        cr.paint_with_alpha(self.win.opacity)

    def refresh(self):
        if self.s is not None:
            self._render()

    def _begin(self, kind, box, button, pts=None):
        self.s = {"kind": kind, "box": box, "button": button, "pts": pts, "stage": 0}
        self.doc.begin_cache()
        self.doc.preview = [self._paint]

    # ------------------------------------------------------------------ input
    def cursor_at(self, x, y, cv):
        s = self.s
        if s is not None and not self.op:
            wx, wy = cv.to_widget(x, y)
            if s["kind"] in ("line", "curve"):
                if self._hit_point(cv, wx, wy) is not None:
                    return "pointer"
            elif hit_handle(cv, s["box"], wx, wy):
                return CURSORS[hit_handle(cv, s["box"], wx, wy)]
            if self._inside(x, y):
                return "move"
        return "crosshair"

    def _inside(self, x, y):
        x0, y0, x1, y1 = norm_box(self.s["box"])
        m = max(3, self.win.size_for("shape") / 2)
        return x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m

    def _hit_point(self, cv, wx, wy):
        pts = self.s.get("pts") or []
        for i, p in enumerate(pts):
            px, py = cv.to_widget(*p)
            if abs(px - wx) <= 6 and abs(py - wy) <= 6:
                return i
        return None

    def press(self, x, y, button, state, n):
        if not self.layer_ok():
            return
        cv = self.win.canvas
        wx, wy = cv.to_widget(x, y)
        s = self.s
        if s is not None:
            k = s["kind"]
            if k == "polygon" and s.get("building"):
                p0 = cv.to_widget(*s["pts"][0])
                if n >= 2 or (abs(p0[0] - wx) <= 6 and abs(p0[1] - wy) <= 6 and len(s["pts"]) > 2):
                    if n >= 2 and len(s["pts"]) > 3:
                        s["pts"].pop()
                    s["building"] = False
                    s["box"] = self._box_of_pts(s["pts"])
                    self._render()
                    return
                s["pts"].append((x, y))
                self.op = ("poly-point",)
                self._render()
                return
            if k in ("line", "curve"):
                i = self._hit_point(cv, wx, wy)
                if i is not None:
                    self.op = ("point", i)
                    return
                if k == "curve" and s["stage"] < 2:
                    a, b = s["pts"][0], s["pts"][-1]
                    if s["stage"] == 0:
                        s["pts"] = [a, (x, y), (x, y), b]
                    else:
                        s["pts"][2] = (x, y)
                    s["stage"] += 1
                    self.op = ("bend", 1 if s["stage"] == 1 else 2)
                    self._render()
                    return
                if self._near_line(x, y):
                    self.op = ("move-pts", list(s["pts"]), (x, y))
                    return
            else:
                h = hit_handle(cv, s["box"], wx, wy)
                if h is not None:
                    self.op = ("resize", h, s["box"], (x, y), list(s["pts"]) if s.get("pts") else None)
                    return
                if self._inside(x, y):
                    self.op = ("move", s["box"], (x, y), list(s["pts"]) if s.get("pts") else None)
                    return
            self.commit()
        kind = self.kind
        if kind == "polygon":
            self._begin(kind, (x, y, x, y), button, [(x, y), (x, y)])
            self.s["building"] = True
            self.op = ("poly-point",)
        elif kind in ("line", "curve"):
            self._begin(kind, (x, y, x, y), button, [(x, y), (x, y)])
            self.op = ("create-line",)
        else:
            self._begin(kind, (x, y, x, y), button)
            self.op = ("create", (x, y))
        self._render()

    def _near_line(self, x, y):
        pts = self.s["pts"]
        a, b = pts[0], pts[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / L))
        px, py = a[0] + t * dx, a[1] + t * dy
        tol = max(4, self.win.size_for("shape")) / max(0.25, self.win.canvas.zoom) * max(1, self.win.canvas.zoom)
        return math.hypot(x - px, y - py) <= tol or self._inside(x, y)

    @staticmethod
    def _constrain_line(a, x, y):
        dx, dy = x - a[0], y - a[1]
        ang = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
        d = math.hypot(dx, dy)
        return (a[0] + d * math.cos(ang), a[1] + d * math.sin(ang))

    def drag(self, x, y, state):
        s, op = self.s, self.op
        if s is None or op is None:
            return
        k = op[0]
        if k == "create":
            sx, sy = op[1]
            if shift(state):
                d = max(abs(x - sx), abs(y - sy))
                x, y = sx + math.copysign(d, x - sx), sy + math.copysign(d, y - sy)
            s["box"] = (sx, sy, x, y)
        elif k == "create-line":
            a = s["pts"][0]
            p = self._constrain_line(a, x, y) if shift(state) else (x, y)
            s["pts"] = [a, p]
            s["box"] = self._box_of_pts(s["pts"])
        elif k == "poly-point":
            p = self._constrain_line(s["pts"][-2], x, y) if shift(state) and len(s["pts"]) > 1 else (x, y)
            s["pts"][-1] = p
            s["box"] = self._box_of_pts(s["pts"])
        elif k == "bend":
            i = op[1]
            if s["stage"] == 1:
                s["pts"][1] = s["pts"][2] = (x, y)
            else:
                s["pts"][i] = (x, y)
            s["box"] = self._box_of_pts(s["pts"])
        elif k == "point":
            s["pts"][op[1]] = (x, y)
            s["box"] = self._box_of_pts(s["pts"])
        elif k == "move-pts":
            base, (sx, sy) = op[1], op[2]
            s["pts"] = [(px + x - sx, py + y - sy) for px, py in base]
            s["box"] = self._box_of_pts(s["pts"])
        elif k == "move":
            box, (sx, sy), pts = op[1], op[2], op[3]
            dx, dy = x - sx, y - sy
            s["box"] = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
            if pts:
                s["pts"] = [(px + dx, py + dy) for px, py in pts]
        elif k == "resize":
            h, box, (sx, sy), pts = op[1], op[2], op[3], op[4]
            nb = apply_handle(box, h, x - sx, y - sy, shift(state))
            s["box"] = nb
            if pts:
                bw, bh = (box[2] - box[0]) or 1, (box[3] - box[1]) or 1
                s["pts"] = [(nb[0] + (px - box[0]) / bw * (nb[2] - nb[0]),
                             nb[1] + (py - box[1]) / bh * (nb[3] - nb[1])) for px, py in pts]
        self._render()
        self.win.update_status(selection=s["box"])

    def release(self, x, y, button):
        s, op = self.s, self.op
        self.op = None
        if s is None or op is None:
            return
        if op[0] == "create":
            x0, y0, x1, y1 = s["box"]
            if abs(x1 - x0) < 2 and abs(y1 - y0) < 2:
                self.cancel()
                return
            s["box"] = norm_box(s["box"])
        elif op[0] == "create-line":
            a, b = s["pts"]
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 2:
                self.cancel()
                return
        self._render()

    def key(self, keyval, state):
        if self.s is None:
            return False
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_Escape):
            if self.s.get("building"):
                self.s["building"] = False
                self.s["box"] = self._box_of_pts(self.s["pts"])
            self.commit()
            return True
        if keyval == Gdk.KEY_Delete:
            self.cancel()
            return True
        return False

    def commit(self):
        s = self.s
        if s is None:
            return
        if s.get("building"):
            s["building"] = False
        self.op = None
        cache = self.cache
        self.s = None
        self.cache = None
        doc = self.doc
        doc.preview = []
        doc.end_cache()
        old, self.rect = self.rect, None
        if cache is not None:
            surf, ox, oy = cache
            op = self.win.opacity

            def fn(cr):
                cr.set_source_surface(surf, ox, oy)
                cr.paint_with_alpha(op)
            doc.modify_layer((ox, oy, surf.get_width(), surf.get_height()), fn, _("Shape"))
        elif old:
            doc.damage(old)
        self.win.canvas.queue_draw()

    def cancel(self):
        self.s = None
        self.op = None
        self.cache = None
        self.doc.preview = []
        self.doc.end_cache()
        old, self.rect = self.rect, None
        if old:
            self.doc.damage(old)
        self.win.canvas.queue_draw()

    def overlay_rect(self, cv):
        s = self.s
        if s is None:
            return None
        pts = list(s.get("pts") or []) + [(s["box"][0], s["box"][1]), (s["box"][2], s["box"][3])]
        return widget_bounds(cv, pts)

    def draw_overlay(self, cr, cv):
        s = self.s
        if s is None:
            return
        th = theme.get()
        if s["kind"] in ("line", "curve") or s.get("building"):
            for p in s.get("pts") or []:
                draw_handle(cr, *cv.to_widget(*p), th, round_=True)
            return
        x0, y0, x1, y1 = norm_box(s["box"])
        a, b = cv.to_widget(x0, y0), cv.to_widget(x1, y1)
        cr.set_line_width(1)
        cr.set_dash([3, 3])
        cr.set_source_rgba(*th.rgb("accent"))
        cr.rectangle(int(a[0]) + 0.5, int(a[1]) + 0.5, int(b[0] - a[0]), int(b[1] - a[1]))
        cr.stroke()
        cr.set_dash([])
        for hx, hy in handle_points(cv, s["box"]).values():
            draw_handle(cr, hx, hy, th)


# =========================================================================== text

class TextTool(Tool):
    name = "text"
    cursor = "text"
    uses_opacity = True

    def __init__(self, win):
        super().__init__(win)
        self.box = None
        self.text = ""
        self.cur = 0
        self.op = None
        self.cache = None
        self.rect = None
        self.layout = None
        self.blink = True
        self._blink_id = 0

    @property
    def pending(self):
        return self.box is not None

    def props(self):
        return self.win.text_props

    def _px(self):
        return self.props()["size"] * 96 / 72

    def _layout(self, cr):
        p = self.props()
        lay = PangoCairo.create_layout(cr)
        fd = Pango.FontDescription()
        fd.set_family(p["family"])
        fd.set_absolute_size(self._px() * Pango.SCALE)
        fd.set_weight(Pango.Weight.BOLD if p["bold"] else Pango.Weight.NORMAL)
        fd.set_style(Pango.Style.ITALIC if p["italic"] else Pango.Style.NORMAL)
        lay.set_font_description(fd)
        x0, y0, x1, y1 = norm_box(self.box)
        lay.set_width(int(max(1, x1 - x0 - 4) * Pango.SCALE))
        lay.set_wrap(Pango.WrapMode.WORD_CHAR)
        lay.set_alignment({"left": Pango.Alignment.LEFT, "center": Pango.Alignment.CENTER,
                           "right": Pango.Alignment.RIGHT}[p["align"]])
        attrs = Pango.AttrList()
        if p["underline"]:
            attrs.insert(Pango.attr_underline_new(Pango.Underline.SINGLE))
        if p["strike"]:
            attrs.insert(Pango.attr_strikethrough_new(True))
        lay.set_attributes(attrs)
        lay.set_text(self.text, -1)
        return lay

    def _render(self):
        old = self.rect
        if self.box is None:
            self.cache = self.rect = None
        else:
            probe = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
            lay = self._layout(probe)
            _ink, logical = lay.get_pixel_extents()
            x0, y0, x1, y1 = norm_box(self.box)
            need = logical.height + 4
            if y1 - y0 < need:  # grow downwards like Paint
                y1 = y0 + need
                self.box = (x0, y0, x1, y1)
            w, h = int(math.ceil(x1 - x0)), int(math.ceil(y1 - y0))
            surf = raster.new_surface(w, h)
            cr = cairo.Context(surf)
            p = self.props()
            if p["background"]:
                cr.set_source_rgba(*self.win.secondary)
                cr.paint()
            cr.translate(2, 2)
            lay = self._layout(cr)
            cr.set_source_rgba(*self.win.primary)
            PangoCairo.show_layout(cr, lay)
            surf.flush()
            self.layout = lay
            self.cache = (surf, int(round(x0)), int(round(y0)))
            self.rect = (int(round(x0)), int(round(y0)), w, h)
        self.doc.damage(raster.union(old, self.rect) or (0, 0, 1, 1))
        self.win.canvas.queue_draw()

    def _paint(self, cr):
        if self.cache is None:
            return
        surf, ox, oy = self.cache
        cr.set_source_surface(surf, ox, oy)
        cr.paint_with_alpha(self.win.opacity)

    def refresh(self):
        if self.box is not None:
            self._render()

    def cursor_at(self, x, y, cv):
        if self.box is not None:
            wx, wy = cv.to_widget(x, y)
            h = hit_handle(cv, self.box, wx, wy)
            if h:
                return CURSORS[h]
            x0, y0, x1, y1 = norm_box(self.box)
            if x0 <= x <= x1 and y0 <= y <= y1:
                return "text"
        return "text"

    def press(self, x, y, button, state, n):
        if not self.layer_ok():
            return
        cv = self.win.canvas
        wx, wy = cv.to_widget(x, y)
        if self.box is not None:
            h = hit_handle(cv, self.box, wx, wy)
            if h:
                self.op = ("resize", h, self.box, (x, y))
                return
            x0, y0, x1, y1 = norm_box(self.box)
            # border band moves the box, inside places the caret
            band = 6 / cv.zoom
            if x0 - band <= x <= x1 + band and y0 - band <= y <= y1 + band:
                if x0 + band < x < x1 - band and y0 + band < y < y1 - band and self.layout is not None:
                    inside, idx, trail = self.layout.xy_to_index(int((x - x0 - 2) * Pango.SCALE),
                                                                 int((y - y0 - 2) * Pango.SCALE))
                    self.cur = self._char_index(idx + trail)
                    self._render()
                else:
                    self.op = ("move", self.box, (x, y))
                return
            self.commit()
        self.op = ("create", (x, y))
        self.box = (x, y, x + 1, y + 1)
        self.text = ""
        self.cur = 0
        self.doc.begin_cache()
        self.doc.preview = [self._paint]
        self.win.show_text_bar(True)

    def _char_index(self, byte_idx):
        b = self.text.encode()[:byte_idx]
        return len(b.decode(errors="ignore"))

    def _byte_index(self, char_idx):
        return len(self.text[:char_idx].encode())

    def drag(self, x, y, state):
        op = self.op
        if op is None or self.box is None:
            return
        if op[0] == "create":
            sx, sy = op[1]
            self.box = (sx, sy, x, y)
        elif op[0] == "move":
            box, (sx, sy) = op[1], op[2]
            self.box = (box[0] + x - sx, box[1] + y - sy, box[2] + x - sx, box[3] + y - sy)
        elif op[0] == "resize":
            self.box = apply_handle(op[2], op[1], x - op[3][0], y - op[3][1])
        self._render()

    def release(self, x, y, button):
        op = self.op
        self.op = None
        if op is None or self.box is None:
            return
        if op[0] == "create":
            x0, y0, x1, y1 = norm_box(self.box)
            if x1 - x0 < 20 or y1 - y0 < 8:
                # a click: default-sized box
                px = self._px()
                x0, y0 = op[1]
                self.box = (x0, y0, x0 + max(200, px * 8), y0 + px * 1.6)
            else:
                self.box = (x0, y0, x1, y1)
        self.box = norm_box(self.box)
        self._render()
        self._start_blink()

    def _start_blink(self):
        if self._blink_id:
            return

        def tick():
            if self.box is None:
                self._blink_id = 0
                return False
            self.blink = not self.blink
            self.win.canvas.queue_draw()
            return True
        self._blink_id = GLib.timeout_add(530, tick)

    def insert(self, s):
        if self.box is None:
            return
        self.text = self.text[:self.cur] + s + self.text[self.cur:]
        self.cur += len(s)
        self.blink = True
        self._render()

    def key(self, keyval, state):
        if self.box is None:
            return False
        if ctrl(state):
            if keyval in (Gdk.KEY_b, Gdk.KEY_B):
                self.win.toggle_text_prop("bold")
                return True
            if keyval in (Gdk.KEY_i, Gdk.KEY_I):
                self.win.toggle_text_prop("italic")
                return True
            if keyval in (Gdk.KEY_u, Gdk.KEY_U):
                self.win.toggle_text_prop("underline")
                return True
            return False
        t, c = self.text, self.cur
        if keyval == Gdk.KEY_BackSpace:
            if c > 0:
                self.text, self.cur = t[:c - 1] + t[c:], c - 1
        elif keyval == Gdk.KEY_Delete:
            self.text = t[:c] + t[c + 1:]
        elif keyval == Gdk.KEY_Left:
            self.cur = max(0, c - 1)
        elif keyval == Gdk.KEY_Right:
            self.cur = min(len(t), c + 1)
        elif keyval == Gdk.KEY_Home:
            self.cur = t.rfind("\n", 0, c) + 1
        elif keyval == Gdk.KEY_End:
            e = t.find("\n", c)
            self.cur = len(t) if e < 0 else e
        elif keyval in (Gdk.KEY_Up, Gdk.KEY_Down) and self.layout is not None:
            line, xpos = self.layout.index_to_line_x(self._byte_index(c), False)
            nl = line + (-1 if keyval == Gdk.KEY_Up else 1)
            if 0 <= nl < self.layout.get_line_count():
                ln = self.layout.get_line_readonly(nl)
                inside, idx, trail = ln.x_to_index(xpos)
                self.cur = self._char_index(idx + trail)
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.insert("\n")
            return True
        elif keyval == Gdk.KEY_Escape:
            self.commit()
            return True
        elif keyval == Gdk.KEY_Tab:
            self.insert("    ")
            return True
        else:
            return False
        self.blink = True
        self._render()
        return True

    def commit(self):
        if self.box is None:
            return
        cache = self.cache
        text = self.text
        self.box = None
        self.cache = None
        self.layout = None
        self.op = None
        doc = self.doc
        doc.preview = []
        doc.end_cache()
        old, self.rect = self.rect, None
        self.win.show_text_bar(False)
        if cache is not None and text.strip():
            surf, ox, oy = cache
            op = self.win.opacity

            def fn(cr):
                cr.set_source_surface(surf, ox, oy)
                cr.paint_with_alpha(op)
            doc.modify_layer((ox, oy, surf.get_width(), surf.get_height()), fn, _("Text"))
        elif old:
            doc.damage(old)
        self.win.canvas.queue_draw()

    def cancel(self):
        self.text = ""
        self.commit()

    def overlay_rect(self, cv):
        if self.box is None:
            return None
        return widget_bounds(cv, [(self.box[0], self.box[1]), (self.box[2], self.box[3])])

    def draw_overlay(self, cr, cv):
        if self.box is None:
            return
        th = theme.get()
        x0, y0, x1, y1 = norm_box(self.box)
        a, b = cv.to_widget(x0, y0), cv.to_widget(x1, y1)
        cr.set_line_width(1)
        cr.set_dash([3, 3])
        cr.set_source_rgba(*th.rgb("handle-line"))
        cr.rectangle(int(a[0]) + 0.5, int(a[1]) + 0.5, int(b[0] - a[0]), int(b[1] - a[1]))
        cr.stroke()
        cr.set_dash([])
        if self.op is None:
            for hx, hy in handle_points(cv, self.box).values():
                draw_handle(cr, hx, hy, th)
        if self.blink and self.layout is not None and self.op is None:
            strong, _weak = self.layout.get_cursor_pos(self._byte_index(self.cur))
            cx = x0 + 2 + strong.x / Pango.SCALE
            cy = y0 + 2 + strong.y / Pango.SCALE
            ch = max(strong.height / Pango.SCALE, self._px())
            p0 = cv.to_widget(cx, cy)
            p1 = cv.to_widget(cx, cy + ch)
            cr.set_source_rgba(*self.win.primary[:3], 1)
            cr.set_line_width(max(1, cv.zoom))
            cr.move_to(int(p0[0]) + 0.5, p0[1])
            cr.line_to(int(p1[0]) + 0.5, p1[1])
            cr.stroke()


def make_tools(win):
    return {
        "select": SelectTool(win),
        "pencil": StrokeTool(win, "pencil"),
        "brush": StrokeTool(win, "brush"),
        "eraser": StrokeTool(win, "eraser"),
        "fill": FillTool(win),
        "picker": PickerTool(win),
        "magnifier": MagnifierTool(win),
        "text": TextTool(win),
        "shape": ShapeTool(win),
    }

"""The drawing surface widget.

The flattened image (Document.composite) is shown as a grid of 256x256 GPU textures;
only tiles touched by a damaged rectangle are re-uploaded, so a brush stroke on a
full-HD canvas uploads a few kilobytes per frame.  Scaling is done by the GPU (nearest
neighbour when zoomed in, linear when zoomed out).  Tool overlays (marching ants,
handles, text caret), gridlines and the canvas resize handles are drawn with cairo on
top, limited to the visible part of the widget."""
from __future__ import annotations

import math
import time

import cairo
from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk

from . import raster, theme

TILE = 256
PAD = 34           # margin around the canvas when it is larger than the view (reference)
HANDLE = 6         # canvas resize handle size (px)
ZOOM_MIN, ZOOM_MAX = 0.125, 8.0
ZOOM_PRESETS = [0.125, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]


def _rect(x, y, w, h):
    return Graphene.Rect().init(x, y, w, h)


class Canvas(Gtk.Widget):
    __gtype_name__ = "FenestraPaintCanvas"

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.doc = None
        self.zoom = 1.0
        self.hadj = self.vadj = None
        self.tiles = {}
        self.dirty = set()
        self.ox = self.oy = 0
        self._anchor = None
        self.resize_drag = None      # (handle, start w, h) while dragging a canvas handle
        self.resize_preview = None   # (x, y, w, h) new canvas rect in image coords
        self.pointer = None          # image coords under the pointer
        self.gridlines = False
        self._last_press = (0, 0, 0, 0)
        self._checker = None
        self.set_focusable(True)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.add_css_class("paint-canvas")

        drag = Gtk.GestureDrag(button=0)
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        self.add_controller(drag)
        self.drag = drag
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._motion)
        motion.connect("leave", self._leave)
        self.add_controller(motion)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._scroll)
        self.add_controller(scroll)
        self._drag_start = (0, 0)
        self._button = 1
        self._last_motion = None

    # ------------------------------------------------------------------ document
    def set_document(self, doc):
        self.doc = doc
        doc.connect(self._on_doc)
        self.tiles.clear()
        self.dirty.clear()
        self.queue_resize()

    def _on_doc(self, kind, rect):
        if kind == "damage":
            self.invalidate(rect)
        elif kind == "structure":
            self.tiles.clear()
            self.dirty.clear()
            self.queue_resize()
            self.queue_draw()

    def invalidate(self, rect=None):
        if rect is None:
            self.tiles.clear()
        else:
            x, y, w, h = rect
            for ty in range(int(y) // TILE, int(math.ceil((y + h) / TILE))):
                for tx in range(int(x) // TILE, int(math.ceil((x + w) / TILE))):
                    self.dirty.add((tx, ty))
        self.queue_draw()

    # ------------------------------------------------------------------ geometry
    def img_size(self):
        return (self.doc.width, self.doc.height) if self.doc else (1, 1)

    def do_measure(self, orientation, for_size):
        iw, ih = self.img_size()
        if orientation == Gtk.Orientation.HORIZONTAL:
            n = int(math.ceil(iw * self.zoom)) + 2 * PAD
        else:
            n = int(math.ceil(ih * self.zoom)) + 2 * PAD
        return n, n, -1, -1

    def do_size_allocate(self, w, h, baseline):
        iw, ih = self.img_size()
        self.ox = max(PAD, int((w - iw * self.zoom) / 2))
        self.oy = max(PAD, int((h - ih * self.zoom) / 2))
        if self._anchor is not None:
            GLib.idle_add(self._apply_anchor)

    def show_origin(self):
        """Scroll so the image's top-left corner is at the top-left of the view (new canvas)."""
        self._anchor = (0, 0, 0, 0)
        self.queue_resize()

    def _apply_anchor(self):
        if self._anchor is None:
            return False
        ix, iy, vx, vy = self._anchor
        self._anchor = None
        if self.hadj is not None:
            self.hadj.set_value(self.ox + ix * self.zoom - vx)
            self.vadj.set_value(self.oy + iy * self.zoom - vy)
        return False

    def to_img(self, wx, wy):
        return (wx - self.ox) / self.zoom, (wy - self.oy) / self.zoom

    def to_widget(self, ix, iy):
        return self.ox + ix * self.zoom, self.oy + iy * self.zoom

    def view_rect(self):
        """Visible part of the widget (widget coordinates)."""
        if self.hadj is None:
            return (0, 0, self.get_width(), self.get_height())
        return (self.hadj.get_value(), self.vadj.get_value(),
                self.hadj.get_page_size() or self.get_width(), self.vadj.get_page_size() or self.get_height())

    def view_center_img(self):
        x, y, w, h = self.view_rect()
        return self.to_img(x + w / 2, y + h / 2)

    def visible_img_origin(self):
        x, y, _w, _h = self.view_rect()
        ix, iy = self.to_img(x, y)
        return max(0, int(ix)), max(0, int(iy))

    # ------------------------------------------------------------------ zoom
    def set_zoom(self, z, anchor_widget=None):
        z = max(ZOOM_MIN, min(ZOOM_MAX, z))
        if abs(z - self.zoom) < 1e-6:
            return
        vx, vy, vw, vh = self.view_rect()
        if anchor_widget is None:
            ax, ay = vx + vw / 2, vy + vh / 2
        else:
            ax, ay = anchor_widget
        ix, iy = self.to_img(ax, ay)
        iw, ih = self.img_size()
        ix, iy = max(0, min(iw, ix)), max(0, min(ih, iy))
        self._anchor = (ix, iy, ax - vx, ay - vy)
        self.zoom = z
        self.queue_resize()
        self.queue_draw()
        self.win.on_zoom_changed()

    def zoom_step(self, direction, anchor=None):
        z = self.zoom
        if direction > 0:
            nz = next((p for p in ZOOM_PRESETS if p > z + 1e-6), ZOOM_MAX)
        else:
            nz = next((p for p in reversed(ZOOM_PRESETS) if p < z - 1e-6), ZOOM_MIN)
        self.set_zoom(nz, anchor)

    def fit_zoom(self):
        _x, _y, vw, vh = self.view_rect()
        if self.hadj is not None:
            vw, vh = self.hadj.get_page_size(), self.vadj.get_page_size()
        iw, ih = self.img_size()
        if vw <= 1 or vh <= 1:
            return 1.0
        return max(ZOOM_MIN, min(ZOOM_MAX, min((vw - 2 * PAD) / iw, (vh - 2 * PAD) / ih)))

    # ------------------------------------------------------------------ drawing
    def _tile_texture(self, tx, ty):
        key = (tx, ty)
        tex = self.tiles.get(key)
        if tex is None or key in self.dirty:
            iw, ih = self.img_size()
            x, y = tx * TILE, ty * TILE
            w, h = min(TILE, iw - x), min(TILE, ih - y)
            tex = raster.texture_from_surface(self.doc.composite, (x, y, w, h))
            self.tiles[key] = tex
            self.dirty.discard(key)
        return tex

    def do_snapshot(self, snap):
        if self.doc is None:
            return
        th = theme.get()
        iw, ih = self.img_size()
        z = self.zoom
        cw, ch = iw * z, ih * z
        ox, oy = self.ox, self.oy
        vx, vy, vw, vh = self.view_rect()
        # soft shadow under the canvas
        sh = th.c["canvas-shadow"]
        snap.append_color(sh, _rect(ox, oy + ch, cw, 1))
        snap.append_color(sh, _rect(ox + cw, oy, 1, ch + 1))
        # transparent background: checkerboard
        if not self.doc.bg_visible:
            if self._checker is None:
                self._checker = raster.texture_from_surface(raster.checker_surface(8))
            r = _rect(ox, oy, cw, ch)
            snap.push_repeat(r, None)
            snap.append_texture(self._checker, _rect(ox, oy, 16, 16))
            snap.pop()
        filt = Gsk.ScalingFilter.NEAREST if z >= 1 else Gsk.ScalingFilter.LINEAR
        # visible tile range
        x0 = max(0, int((vx - ox) / z) // TILE)
        y0 = max(0, int((vy - oy) / z) // TILE)
        x1 = min((iw - 1) // TILE, int((vx + vw - ox) / z) // TILE)
        y1 = min((ih - 1) // TILE, int((vy + vh - oy) / z) // TILE)
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                tex = self._tile_texture(tx, ty)
                px0 = round(ox + tx * TILE * z)
                py0 = round(oy + ty * TILE * z)
                px1 = round(ox + min(iw, (tx + 1) * TILE) * z)
                py1 = round(oy + min(ih, (ty + 1) * TILE) * z)
                snap.append_scaled_texture(tex, filt, _rect(px0, py0, px1 - px0, py1 - py0))
        # overlays: cairo only where something is drawn (never during plain strokes)
        if self.gridlines:
            cr = snap.append_cairo(_rect(vx, vy, vw, vh))
            self._draw_grid(cr, iw, ih, z, ox, oy)
        tool = self.win.tool
        r = tool.overlay_rect(self) if tool is not None else None
        if r is not None:
            x0, y0 = max(vx, r[0] - 12), max(vy, r[1] - 12)
            x1, y1 = min(vx + vw, r[0] + r[2] + 12), min(vy + vh, r[1] + r[3] + 12)
            if x1 > x0 and y1 > y0:
                cr = snap.append_cairo(_rect(x0, y0, x1 - x0, y1 - y0))
                tool.draw_overlay(cr, self)
        if self.resize_preview is not None:
            x, y, w, h = self.resize_preview
            wx, wy = self.to_widget(x, y)
            cr = snap.append_cairo(_rect(vx, vy, vw, vh))
            cr.set_line_width(1)
            cr.set_dash([4, 4])
            cr.set_source_rgba(*th.rgb("handle-line"))
            cr.rectangle(int(wx) + 0.5, int(wy) + 0.5, int(w * z), int(h * z))
            cr.stroke()
        if self.win.show_canvas_handles():
            fill, line = th.c["handle"], th.c["handle-line"]
            for hx, hy, _name in self.handle_positions():
                x, y = int(hx - HANDLE / 2), int(hy - HANDLE / 2)
                rr = Gsk.RoundedRect()
                rr.init_from_rect(_rect(x, y, HANDLE, HANDLE), 0)
                snap.append_color(fill, _rect(x, y, HANDLE, HANDLE))
                snap.append_border(rr, [1, 1, 1, 1], [line, line, line, line])

    def _draw_grid(self, cr, iw, ih, z, ox, oy):
        if z >= 4:
            step = 1
        else:
            step = next((s for s in (2, 5, 10, 20, 25, 50, 100, 200, 500) if s * z >= 10), 1000)
        vx, vy, vw, vh = self.view_rect()
        ix0 = max(0, int((vx - ox) / z / step) * step)
        iy0 = max(0, int((vy - oy) / z / step) * step)
        ix1 = min(iw, int((vx + vw - ox) / z) + 1)
        iy1 = min(ih, int((vy + vh - oy) / z) + 1)
        cr.set_line_width(1)
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.45)
        x = ix0
        while x <= ix1:
            px = int(ox + x * z) + 0.5
            cr.move_to(px, max(oy, vy))
            cr.line_to(px, min(oy + ih * z, vy + vh))
            x += step
        y = iy0
        while y <= iy1:
            py = int(oy + y * z) + 0.5
            cr.move_to(max(ox, vx), py)
            cr.line_to(min(ox + iw * z, vx + vw), py)
            y += step
        cr.stroke()

    def handle_positions(self):
        iw, ih = self.img_size()
        if self.resize_preview is not None:
            x, y, iw, ih = self.resize_preview
        else:
            x = y = 0
        x0, y0 = self.to_widget(x, y)
        x1, y1 = self.to_widget(x + iw, y + ih)
        x0, y0, x1, y1 = x0 - 3, y0 - 3, x1 + 3, y1 + 3
        mx, my = round((x0 + x1) / 2), round((y0 + y1) / 2)
        return [(x0, y0, "nw"), (mx, y0, "n"), (x1, y0, "ne"), (x0, my, "w"), (x1, my, "e"),
                (x0, y1, "sw"), (mx, y1, "s"), (x1, y1, "se")]

    def hit_canvas_handle(self, wx, wy):
        if not self.win.show_canvas_handles():
            return None
        for hx, hy, name in self.handle_positions():
            if abs(wx - hx) <= 5 and abs(wy - hy) <= 5:
                return name
        return None

    # ------------------------------------------------------------------ input
    def _press_count(self, wx, wy, button):
        now = time.monotonic()
        lt, lx, ly, n = self._last_press
        gs = Gtk.Settings.get_default()
        dt = (gs.props.gtk_double_click_time if gs else 400) / 1000
        if now - lt <= dt and abs(wx - lx) < 5 and abs(wy - ly) < 5:
            n += 1
        else:
            n = 1
        self._last_press = (now, wx, wy, n)
        return n

    def _drag_begin(self, g, wx, wy):
        self.grab_focus()
        self._button = g.get_current_button() or 1
        self._drag_start = (wx, wy)
        state = g.get_current_event_state()
        n = self._press_count(wx, wy, self._button)
        h = self.hit_canvas_handle(wx, wy) if self._button == 1 else None
        if h is not None:
            self.win.commit_tool()
            iw, ih = self.img_size()
            self.resize_drag = (h, iw, ih)
            self.resize_preview = (0, 0, iw, ih)
            return
        if self.win.tool is not None and self.doc is not None:
            ix, iy = self.to_img(wx, wy)
            self.win.tool.press(ix, iy, self._button, state, n)
            self.queue_draw()

    def _drag_update(self, g, dx, dy):
        sx, sy = self._drag_start
        wx, wy = sx + dx, sy + dy
        ix, iy = self.to_img(wx, wy)
        self.pointer = (ix, iy)
        if self.resize_drag is not None:
            h, iw, ih = self.resize_drag
            ddx, ddy = dx / self.zoom, dy / self.zoom
            x0, y0, x1, y1 = 0, 0, iw, ih
            if "w" in h:
                x0 = min(iw - 1, round(ddx))
            if "e" in h:
                x1 = max(1, round(iw + ddx))
            if "n" in h:
                y0 = min(ih - 1, round(ddy))
            if "s" in h:
                y1 = max(1, round(ih + ddy))
            self.resize_preview = (x0, y0, x1 - x0, y1 - y0)
            self.win.update_status(resize=(x1 - x0, y1 - y0))
            self.queue_draw()
            return
        if self.win.tool is not None:
            state = g.get_current_event_state()
            self.win.tool.drag(ix, iy, state)
            self.win.update_status()
            self.queue_draw()

    def _drag_end(self, g, dx, dy):
        sx, sy = self._drag_start
        ix, iy = self.to_img(sx + dx, sy + dy)
        if self.resize_drag is not None:
            x, y, w, h = self.resize_preview
            iw, ih = self.img_size()
            self.resize_drag = None
            self.resize_preview = None
            if (x, y, w, h) != (0, 0, iw, ih):
                self.doc.resize_canvas(w, h, -x, -y)
            self.win.update_status()
            self.queue_draw()
            return
        if self.win.tool is not None:
            self.win.tool.release(ix, iy, self._button)
            self.queue_draw()

    def _motion(self, _c, wx, wy):
        self._last_motion = (wx, wy)
        ix, iy = self.to_img(wx, wy)
        self.pointer = (ix, iy)
        h = self.hit_canvas_handle(wx, wy)
        if h is not None and self.resize_drag is None:
            self.set_cursor_from_name({"n": "n-resize", "s": "s-resize", "e": "e-resize", "w": "w-resize",
                                       "ne": "ne-resize", "nw": "nw-resize", "se": "se-resize",
                                       "sw": "sw-resize"}[h])
        elif self.win.tool is not None:
            self.set_cursor_from_name(self.win.tool.cursor_at(ix, iy, self))
        self.win.update_status()

    def _leave(self, *_a):
        self.pointer = None
        self.win.update_status()

    def _scroll(self, c, dx, dy):
        state = c.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            pos = self._last_motion
            if dy < 0:
                self.set_zoom(self.zoom * 1.1, pos)
            elif dy > 0:
                self.set_zoom(self.zoom / 1.1, pos)
            return True
        return False


class Ruler(Gtk.Widget):
    """Pixel ruler along the top or left edge of the workspace (View > Rulers)."""
    __gtype_name__ = "FenestraPaintRuler"

    def __init__(self, canvas, orientation):
        super().__init__()
        self.canvas = canvas
        self.orientation = orientation
        self.add_css_class("ruler")

    def do_measure(self, orientation, for_size):
        if orientation == self.orientation:
            return 0, 0, -1, -1
        return 20, 20, -1, -1

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        th = theme.get()
        cr = snap.append_cairo(_rect(0, 0, w, h))
        cr.set_source_rgba(*th.rgb("ruler"))
        cr.paint()
        cv = self.canvas
        z = cv.zoom
        horiz = self.orientation == Gtk.Orientation.HORIZONTAL
        origin = (cv.ox - cv.view_rect()[0]) if horiz else (cv.oy - cv.view_rect()[1])
        length = w if horiz else h
        # tick spacing so labels are >= 50 px apart
        step = next((s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000)
                     if s * z >= 50), 10000)
        minor = step / 5 if step >= 5 else step
        cr.set_source_rgba(*th.rgb("ruler-fg"))
        cr.set_line_width(1)
        cr.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9)
        v = math.floor(-origin / z / minor) * minor
        end = (length - origin) / z
        while v <= end:
            p = int(origin + v * z) + 0.5
            major = abs(v / step - round(v / step)) < 1e-6
            t = 10 if major else 4
            if horiz:
                cr.move_to(p, h)
                cr.line_to(p, h - t)
            else:
                cr.move_to(w, p)
                cr.line_to(w - t, p)
            cr.stroke()
            if major:
                txt = str(int(round(v)))
                if horiz:
                    cr.move_to(p + 3, 10)
                    cr.show_text(txt)
                else:
                    cr.save()
                    cr.move_to(10, p + 3)
                    cr.rotate(math.pi / 2)
                    cr.show_text(txt)
                    cr.restore()
            v += minor
        # pointer marker
        if cv.pointer is not None:
            pv = cv.pointer[0] if horiz else cv.pointer[1]
            p = int(origin + pv * z) + 0.5
            cr.set_source_rgba(*th.rgb("accent"))
            if horiz:
                cr.move_to(p, 0)
                cr.line_to(p, h)
            else:
                cr.move_to(0, p)
                cr.line_to(w, p)
            cr.stroke()
        cr.set_source_rgba(*th.rgb("bar-line"))
        if horiz:
            cr.move_to(0, h - 0.5)
            cr.line_to(w, h - 0.5)
        else:
            cr.move_to(w - 0.5, 0)
            cr.line_to(w - 0.5, h)
        cr.stroke()

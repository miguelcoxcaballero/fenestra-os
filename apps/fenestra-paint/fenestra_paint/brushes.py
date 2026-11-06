"""Stroke engines for the pencil, the nine brushes and the eraser.

A stroke draws *coverage* into its own layer-sized surface in the stroke colour.  How it is
laid on the layer (alpha, paper grain, erase) is decided when compositing, so the live
preview and the committed result are identical and overlapping segments of one stroke
never darken each other (marker / watercolour stay even, like Paint).

Path-based kinds re-stroke the whole smoothed polyline inside the damaged rectangle on
every motion event (cheap: cairo only rasterises inside the clip).  Dab-based kinds
(airbrush, oil, calligraphy) draw incrementally."""
from __future__ import annotations

import math
import random

import cairo

from . import raster
from .i18n import N_

BRUSHES = [  # (id, label)
    ("brush", N_("Brush")),
    ("calligraphy_brush", N_("Calligraphy brush")),
    ("calligraphy_pen", N_("Calligraphy pen")),
    ("airbrush", N_("Airbrush")),
    ("oil", N_("Oil brush")),
    ("crayon", N_("Crayon")),
    ("marker", N_("Marker")),
    ("natural_pencil", N_("Natural pencil")),
    ("watercolor", N_("Watercolor brush")),
]
BRUSH_IDS = [b[0] for b in BRUSHES]

INCREMENTAL = {"airbrush", "oil", "calligraphy_brush", "calligraphy_pen"}
ALPHA = {"marker": 0.55, "natural_pencil": 0.9, "watercolor": 1.0}
GRAIN = {"crayon": dict(density=0.62, soft=False, seed=11), "natural_pencil": dict(density=0.5, soft=True, seed=5),
         "watercolor": dict(density=0.5, soft=True, seed=3)}
NIB_ANGLE = math.radians(45)


def grain_pattern(kind):
    g = GRAIN.get(kind)
    if not g:
        return None
    p = cairo.SurfacePattern(raster.noise_surface(128, g["seed"], g["density"], g["soft"]))
    p.set_extend(cairo.EXTEND_REPEAT)
    return p


def smooth_path(cr, pts):
    """Quadratic smoothing through segment midpoints."""
    if not pts:
        return
    x0, y0 = pts[0]
    if len(pts) == 1:
        cr.move_to(x0, y0)
        cr.line_to(x0 + 0.01, y0)
        return
    cr.move_to(x0, y0)
    if len(pts) == 2:
        cr.line_to(*pts[1])
        return
    px, py = x0, y0
    for i in range(1, len(pts) - 1):
        cx, cy = pts[i]
        mx, my = (cx + pts[i + 1][0]) / 2, (cy + pts[i + 1][1]) / 2
        # quadratic (px,py)-(cx,cy)-(mx,my) as cubic
        cr.curve_to(px + 2 / 3 * (cx - px), py + 2 / 3 * (cy - py),
                    mx + 2 / 3 * (cx - mx), my + 2 / 3 * (cy - my), mx, my)
        px, py = mx, my
    cr.line_to(*pts[-1])


class Stroke:
    def __init__(self, kind, color, size, w, h, erase=False, seed=1):
        self.kind = kind
        self.color = color              # (r, g, b, a) un-premultiplied
        self.size = max(1, float(size))
        self.erase = erase or kind == "eraser"
        self.surface = raster.new_surface(w, h)
        self.w, self.h = w, h
        self.pts = []
        self.bbox = None
        self.rnd = random.Random(seed)
        self.length = 0.0
        self.last_t = None
        self.dir = None

    # ------------------------------------------------------------------ geometry
    @property
    def reach(self):
        return self.size / 2 + 3

    def add(self, x, y, t=None):
        """Add a point; returns the damaged rectangle (image coordinates)."""
        if self.kind == "pencil":
            x, y = math.floor(x) + 0.5, math.floor(y) + 0.5
        if self.pts and abs(self.pts[-1][0] - x) < 0.25 and abs(self.pts[-1][1] - y) < 0.25 \
                and self.kind != "airbrush":
            return None
        prev = self.pts[-1] if self.pts else (x, y)
        self.pts.append((x, y))
        seg = math.hypot(x - prev[0], y - prev[1])
        self.length += seg
        r = self.reach
        x0, y0 = min(prev[0], x) - r, min(prev[1], y) - r
        rect = (x0, y0, abs(x - prev[0]) + 2 * r, abs(y - prev[1]) + 2 * r)
        if self.kind not in INCREMENTAL and len(self.pts) >= 3:
            # the smoothed curve between the previous midpoints moves too
            p2 = self.pts[-3]
            rect = raster.union(rect, (min(p2[0], x) - r, min(p2[1], y) - r,
                                       abs(x - p2[0]) + 2 * r, abs(y - p2[1]) + 2 * r))
        rect = raster.clip_rect(rect, self.w, self.h)
        if rect is None:
            return None
        cr = cairo.Context(self.surface)
        cr.rectangle(*rect)
        cr.clip()
        self._draw(cr, prev, (x, y), seg)
        self.surface.flush()
        self.bbox = raster.union(self.bbox, rect)
        return rect

    def _src(self, cr, alpha=1.0, shade=0.0):
        r, g, b, _a = self.color
        if shade:
            f = 1 + shade
            r, g, b = (min(1, max(0, v * f if shade < 0 else v + (1 - v) * shade)) for v in (r, g, b))
        cr.set_source_rgba(r, g, b, alpha)

    def _draw(self, cr, p0, p1, seg):
        k = self.kind
        if k in INCREMENTAL:
            getattr(self, "_draw_" + k)(cr, p0, p1, seg)
            return
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        if k == "pencil":
            cr.set_antialias(cairo.ANTIALIAS_NONE)
            cr.set_line_width(self.size)
            cr.move_to(*self.pts[0])
            if len(self.pts) == 1:
                cr.rectangle(self.pts[0][0] - self.size / 2, self.pts[0][1] - self.size / 2, self.size, self.size)
                self._src(cr)
                cr.fill()
                return
            for p in self.pts[1:]:
                cr.line_to(*p)
            self._src(cr)
            cr.stroke()
            return
        smooth_path(cr, self.pts)
        path = cr.copy_path()
        if k == "natural_pencil":
            cr.set_line_width(max(1.0, self.size * 0.55))
            self._src(cr)
            cr.stroke()
        elif k == "marker":
            cr.set_line_cap(cairo.LINE_CAP_SQUARE)
            cr.set_line_join(cairo.LINE_JOIN_BEVEL)
            cr.set_line_width(self.size)
            self._src(cr)
            cr.stroke()
        elif k == "watercolor":
            cr.set_line_width(self.size)
            self._src(cr, 0.42)
            cr.stroke()
            # darker rim: the outline ring of the stroke
            cr.push_group()
            cr.append_path(path)
            cr.set_line_width(self.size)
            self._src(cr, 1.0)
            cr.stroke()
            cr.append_path(path)
            cr.set_operator(cairo.OPERATOR_DEST_OUT)
            cr.set_line_width(max(1.0, self.size - max(2.0, self.size * 0.18)))
            cr.set_source_rgba(0, 0, 0, 1)
            cr.stroke()
            cr.pop_group_to_source()
            cr.paint_with_alpha(0.28)
            # wetter centre
            cr.append_path(path)
            cr.set_line_width(max(1.0, self.size * 0.45))
            self._src(cr, 0.12)
            cr.stroke()
        else:  # brush, crayon, eraser
            cr.set_line_width(self.size)
            self._src(cr)
            cr.stroke()

    # ------------------------------------------------------------------ dab kinds
    def _draw_calligraphy_pen(self, cr, p0, p1, seg, half=None):
        half = self.size / 2 if half is None else half
        dx, dy = math.cos(NIB_ANGLE) * half, -math.sin(NIB_ANGLE) * half
        self._src(cr)
        cr.move_to(p0[0] + dx, p0[1] + dy)
        cr.line_to(p1[0] + dx, p1[1] + dy)
        cr.line_to(p1[0] - dx, p1[1] - dy)
        cr.line_to(p0[0] - dx, p0[1] - dy)
        cr.close_path()
        cr.fill()
        # nib footprint (keeps strokes parallel to the nib visible)
        cr.set_line_width(max(1.0, self.size * 0.12))
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(p1[0] + dx, p1[1] + dy)
        cr.line_to(p1[0] - dx, p1[1] - dy)
        cr.stroke()

    def _draw_calligraphy_brush(self, cr, p0, p1, seg):
        # softer, tapers with speed
        speed = seg
        f = max(0.35, min(1.0, 1.15 - speed / (self.size * 3 + 8)))
        self._width = getattr(self, "_width", f) * 0.7 + f * 0.3
        self._draw_calligraphy_pen(cr, p0, p1, seg, self.size / 2 * self._width)

    def _draw_airbrush(self, cr, p0, p1, seg):
        r = self.size / 2
        n = int(max(4, r * r * 0.12))
        steps = max(1, int(seg / max(1.0, r / 2)))
        self._src(cr)
        dot = max(1.0, self.size / 40)
        for s in range(steps):
            t = (s + 1) / steps
            cx, cy = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
            for _i in range(n // steps + 1):
                a = self.rnd.random() * 2 * math.pi
                d = r * math.sqrt(self.rnd.random())
                cr.rectangle(int(cx + math.cos(a) * d), int(cy + math.sin(a) * d), dot, dot)
        cr.fill()

    def _draw_oil(self, cr, p0, p1, seg):
        if not hasattr(self, "_bristles"):
            k = max(4, int(self.size / 2.2))
            self._bristles = []
            for i in range(k):
                off = (i / (k - 1) - 0.5) * self.size * 0.95 if k > 1 else 0
                off += self.rnd.uniform(-0.3, 0.3) * self.size / k
                self._bristles.append((off, self.rnd.uniform(0.7, 1.4), self.rnd.uniform(-0.18, 0.14),
                                       self.rnd.uniform(0.75, 1.0)))
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        d = math.hypot(dx, dy)
        if d > 0.01:
            nd = (dx / d, dy / d)
            self.dir = nd if self.dir is None else (self.dir[0] * 0.6 + nd[0] * 0.4, self.dir[1] * 0.6 + nd[1] * 0.4)
        ux, uy = self.dir or (1.0, 0.0)
        ln = math.hypot(ux, uy) or 1
        nx, ny = -uy / ln, ux / ln
        load = max(0.4, 1.0 - self.length / (self.size * 60 + 400))
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        bw = self.size / len(self._bristles)
        # base body so the stroke stays opaque-ish between bristles
        cr.set_line_width(self.size * 0.82)
        self._src(cr, 0.55 * load)
        cr.move_to(*p0)
        cr.line_to(*p1)
        cr.stroke()
        for off, wmul, shade, a in self._bristles:
            cr.set_line_width(max(1.0, bw * wmul * 1.25))
            self._src(cr, a * load, shade)
            cr.move_to(p0[0] + nx * off, p0[1] + ny * off)
            cr.line_to(p1[0] + nx * off, p1[1] + ny * off)
            cr.stroke()

    # ------------------------------------------------------------------ compositing
    def composite(self, cr, opacity):
        """Lay the stroke on the layer (used for preview and commit)."""
        alpha = opacity * ALPHA.get(self.kind, 1.0)
        if self.erase:
            cr.set_operator(cairo.OPERATOR_DEST_OUT)
        grain = grain_pattern(self.kind)
        if grain is None:
            cr.set_source_surface(self.surface, 0, 0)
            cr.paint_with_alpha(alpha)
            return
        cr.push_group()
        cr.set_source_surface(self.surface, 0, 0)
        cr.mask(grain)
        cr.pop_group_to_source()
        cr.paint_with_alpha(alpha)


def render_stroke(kind, pts, color, size, w, h, seed=1):
    """One-shot stroke along pts; returns the Stroke (surface + bbox)."""
    st = Stroke(kind, color, size, w, h, seed=seed)
    for x, y in pts:
        st.add(x, y)
    return st


def flatten_path(cr):
    """Points of the current path (flattened), one list per sub-path."""
    out, cur = [], []
    for t, p in cr.copy_path_flat():
        if t == cairo.PATH_MOVE_TO:
            if cur:
                out.append(cur)
            cur = [p]
        elif t == cairo.PATH_LINE_TO:
            cur.append(p)
        elif t == cairo.PATH_CLOSE_PATH and cur:
            cur.append(cur[0])
    if cur:
        out.append(cur)
    return out


def densify(pts, step=2.0):
    """Insert points so consecutive ones are at most step apart (for dab brushes)."""
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / step))
        for i in range(1, n + 1):
            out.append((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
    return out


def preview_surface(kind, color, w=72, h=26, size=None):
    """Small sample stroke used in the Brushes menu."""
    s = raster.new_surface(w, h)
    pts = []
    for i in range(41):
        t = i / 40
        x = 4 + t * (w - 8)
        y = h / 2 - math.sin(t * math.pi * 2) * (h / 2 - 7)
        pts.append((x, y))
    sz = size or {"airbrush": 9, "calligraphy_pen": 7, "calligraphy_brush": 7, "natural_pencil": 5}.get(kind, 6)
    st = render_stroke(kind, densify(pts, 1.5) if kind in INCREMENTAL else pts, color, sz, w, h)
    cr = cairo.Context(s)
    st.composite(cr, 1.0)
    s.flush()
    return s

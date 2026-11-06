"""Shape geometry (the 23 shapes of Paint's Shapes gallery) as cairo paths.

Every shape is drawn in a box (x0, y0, x1, y1); line and curve use explicit points and
polygon uses its vertex list.  The same code draws the toolbar icons."""
from __future__ import annotations

import math

from .i18n import N_

SHAPES = [  # (id, tooltip) in gallery order, 7 per row
    ("line", N_("Line")), ("curve", N_("Curve")), ("oval", N_("Oval")),
    ("rectangle", N_("Rectangle")), ("rounded_rectangle", N_("Rounded rectangle")),
    ("polygon", N_("Polygon")), ("triangle", N_("Triangle")),
    ("right_triangle", N_("Right triangle")), ("diamond", N_("Diamond")),
    ("pentagon", N_("Pentagon")), ("hexagon", N_("Hexagon")),
    ("right_arrow", N_("Right arrow")), ("left_arrow", N_("Left arrow")), ("up_arrow", N_("Up arrow")),
    ("down_arrow", N_("Down arrow")), ("star4", N_("Four-point star")), ("star5", N_("Five-point star")),
    ("star6", N_("Six-point star")), ("callout_rect", N_("Rounded rectangular callout")),
    ("callout_oval", N_("Oval callout")), ("callout_cloud", N_("Cloud callout")),
    ("heart", N_("Heart")), ("lightning", N_("Lightning")),
]
SHAPE_IDS = [s[0] for s in SHAPES]

OUTLINES = [("none", N_("No outline")), ("solid", N_("Solid color")), ("crayon", N_("Crayon")),
            ("marker", N_("Marker")), ("oil", N_("Oil")), ("natural_pencil", N_("Natural pencil")),
            ("watercolor", N_("Watercolor"))]
FILLS = [("none", N_("No fill")), ("solid", N_("Solid color")), ("crayon", N_("Crayon")),
         ("marker", N_("Marker")), ("oil", N_("Oil")), ("natural_pencil", N_("Natural pencil")),
         ("watercolor", N_("Watercolor"))]


def _poly(cr, pts):
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.close_path()


def _norm(pts, x0, y0, w, h):
    """Points given in 0..1 unit coordinates."""
    return [(x0 + px * w, y0 + py * h) for px, py in pts]


def _star(n, inner):
    out = []
    for i in range(n * 2):
        a = -math.pi / 2 + i * math.pi / n
        r = 0.5 if i % 2 == 0 else 0.5 * inner
        out.append((0.5 + r * math.cos(a), 0.5 + r * math.sin(a)))
    return out


def _regular(n, rot=-math.pi / 2):
    return [(0.5 + 0.5 * math.cos(rot + i * 2 * math.pi / n), 0.5 + 0.5 * math.sin(rot + i * 2 * math.pi / n))
            for i in range(n)]


def _fit(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    mx, my, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    return [((x - mx) / w, (y - my) / h) for x, y in pts]


PENTAGON = _fit(_regular(5))
HEXAGON = _fit(_regular(6, 0))
STAR4 = _star(4, 0.38)
STAR5 = _fit(_star(5, 0.40))
STAR6 = _star(6, 0.55)
ARROW_R = [(0, 0.25), (0.6, 0.25), (0.6, 0), (1, 0.5), (0.6, 1), (0.6, 0.75), (0, 0.75)]
LIGHTNING = [(0.38, 0), (0.62, 0.30), (0.53, 0.35), (0.80, 0.58), (0.72, 0.62), (1, 1),
             (0.40, 0.70), (0.50, 0.66), (0.18, 0.44), (0.29, 0.40), (0, 0.13)]


def path(cr, kind, x0, y0, x1, y1, pts=None):
    """Append the path of the shape to cr."""
    if kind in ("line", "curve"):
        p = pts or [(x0, y0), (x1, y1)]
        cr.move_to(*p[0])
        if kind == "line" or len(p) == 2:
            cr.line_to(*p[-1])
        elif len(p) == 3:
            (ax, ay), (cx, cy), (bx, by) = p[0], p[1], p[2]
            # p[1] is the bend handle: quadratic through it
            qx, qy = 2 * cx - (ax + bx) / 2, 2 * cy - (ay + by) / 2
            cr.curve_to(ax + 2 / 3 * (qx - ax), ay + 2 / 3 * (qy - ay),
                        bx + 2 / 3 * (qx - bx), by + 2 / 3 * (qy - by), bx, by)
        else:
            cr.curve_to(p[1][0], p[1][1], p[2][0], p[2][1], p[3][0], p[3][1])
        return
    if kind == "polygon":
        if pts and len(pts) >= 2:
            cr.move_to(*pts[0])
            for p in pts[1:]:
                cr.line_to(*p)
            cr.close_path()
        return
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    w, h = max(x1 - x0, 0.01), max(y1 - y0, 0.01)
    if kind == "oval":
        cr.save()
        cr.translate(x0 + w / 2, y0 + h / 2)
        cr.scale(w / 2, h / 2)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.close_path()
    elif kind == "rectangle":
        cr.rectangle(x0, y0, w, h)
    elif kind == "rounded_rectangle":
        _rounded(cr, x0, y0, w, h, min(w, h) * 0.16)
    elif kind == "triangle":
        _poly(cr, _norm([(0.5, 0), (1, 1), (0, 1)], x0, y0, w, h))
    elif kind == "right_triangle":
        _poly(cr, _norm([(0, 0), (1, 1), (0, 1)], x0, y0, w, h))
    elif kind == "diamond":
        _poly(cr, _norm([(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)], x0, y0, w, h))
    elif kind == "pentagon":
        _poly(cr, _norm(PENTAGON, x0, y0, w, h))
    elif kind == "hexagon":
        _poly(cr, _norm(HEXAGON, x0, y0, w, h))
    elif kind == "right_arrow":
        _poly(cr, _norm(ARROW_R, x0, y0, w, h))
    elif kind == "left_arrow":
        _poly(cr, _norm([(1 - x, y) for x, y in ARROW_R], x0, y0, w, h))
    elif kind == "up_arrow":
        _poly(cr, _norm([(y, 1 - x) for x, y in ARROW_R], x0, y0, w, h))
    elif kind == "down_arrow":
        _poly(cr, _norm([(y, x) for x, y in ARROW_R], x0, y0, w, h))
    elif kind == "star4":
        _poly(cr, _norm(STAR4, x0, y0, w, h))
    elif kind == "star5":
        _poly(cr, _norm(STAR5, x0, y0, w, h))
    elif kind == "star6":
        _poly(cr, _norm(STAR6, x0, y0, w, h))
    elif kind == "callout_rect":
        bh = h * 0.72
        r = min(w, bh) * 0.18
        cr.new_sub_path()
        cr.arc(x0 + w - r, y0 + r, r, -math.pi / 2, 0)
        cr.arc(x0 + w - r, y0 + bh - r, r, 0, math.pi / 2)
        cr.line_to(x0 + w * 0.42, y0 + bh)
        cr.line_to(x0 + w * 0.17, y0 + h)
        cr.line_to(x0 + w * 0.22, y0 + bh)
        cr.arc(x0 + r, y0 + bh - r, r, math.pi / 2, math.pi)
        cr.arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
    elif kind == "callout_oval":
        bh = h * 0.80
        cx, cy, rx, ry = x0 + w / 2, y0 + bh / 2, w / 2, bh / 2
        a0, a1 = math.radians(112), math.radians(132)
        cr.save()
        cr.translate(cx, cy)
        cr.scale(rx, ry)
        cr.arc(0, 0, 1, a1, a0 + 2 * math.pi)
        cr.restore()
        cr.line_to(x0 + w * 0.16, y0 + h)
        cr.close_path()
    elif kind == "callout_cloud":
        _cloud(cr, x0, y0, w, h * 0.80)
        for (px, py, pr) in ((0.20, 0.86, 0.055), (0.11, 0.96, 0.035)):
            cr.new_sub_path()
            cr.save()
            cr.translate(x0 + px * w, y0 + py * h)
            cr.scale(pr * w, pr * h * 1.2)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.close_path()
    elif kind == "heart":
        cr.move_to(x0 + w * 0.5, y0 + h)
        cr.curve_to(x0 + w * 0.12, y0 + h * 0.70, x0, y0 + h * 0.48, x0, y0 + h * 0.28)
        cr.curve_to(x0, y0 + h * 0.08, x0 + w * 0.16, y0, x0 + w * 0.28, y0)
        cr.curve_to(x0 + w * 0.40, y0, x0 + w * 0.48, y0 + h * 0.08, x0 + w * 0.5, y0 + h * 0.18)
        cr.curve_to(x0 + w * 0.52, y0 + h * 0.08, x0 + w * 0.60, y0, x0 + w * 0.72, y0)
        cr.curve_to(x0 + w * 0.84, y0, x0 + w, y0 + h * 0.08, x0 + w, y0 + h * 0.28)
        cr.curve_to(x0 + w, y0 + h * 0.48, x0 + w * 0.88, y0 + h * 0.70, x0 + w * 0.5, y0 + h)
        cr.close_path()
    elif kind == "lightning":
        _poly(cr, _norm(LIGHTNING, x0, y0, w, h))


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _cloud(cr, x0, y0, w, h):
    # bumps around an ellipse
    n = 9
    cx, cy, rx, ry = x0 + w / 2, y0 + h / 2, w / 2 * 0.80, h / 2 * 0.74
    pts = [(cx + rx * math.cos(2 * math.pi * i / n - math.pi / 2), cy + ry * math.sin(2 * math.pi * i / n - math.pi / 2))
           for i in range(n)]
    cr.move_to(*pts[0])
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = mx - cx, my - cy
        d = math.hypot(dx / rx, dy / ry) or 1
        bulge = 0.55
        kx, ky = cx + dx / d * (1 + bulge), cy + dy / d * (1 + bulge)
        cr.curve_to(a[0] + (kx - cx) * 0.25 + (a[0] - cx) * 0.25 * 0,
                    a[1] + (ky - cy) * 0.25,
                    b[0] + (kx - cx) * 0.25, b[1] + (ky - cy) * 0.25, b[0], b[1])
    cr.close_path()


def draw_icon(cr, kind, size=16, line=1.0):
    """Toolbar glyph of a shape in a size x size box (stroke only)."""
    m = 1.5
    x0, y0, x1, y1 = m, m + 1, size - m, size - m - 1
    if kind in ("triangle", "right_triangle", "diamond", "pentagon", "hexagon", "star4", "star5",
                "star6", "up_arrow", "down_arrow", "heart", "lightning"):
        y0, y1 = m, size - m
    if kind == "oval":
        x0, x1 = m + 1, size - m - 1
        y0, y1 = m + 1, size - m - 1
    cr.set_line_width(line)
    cr.set_line_join(1)  # round
    if kind == "line":
        path(cr, "line", 0, 0, 0, 0, [(x0 + 1, y0), (x1 - 1, y1)])
    elif kind == "curve":
        cr.move_to(x0, y1 - 1)
        cr.curve_to(x0 + 4, y0 - 6, x0 + 6, y1 + 4, x1 - 4, y0 + 2)
        cr.curve_to(x1 - 3, y0, x1, y0 + 2, x1, y0 + 4)
    elif kind == "polygon":
        path(cr, "polygon", 0, 0, 0, 0, [(x0 + 4, y0), (x1, y0), (x1 - 3, y1), (x0, y1), (x0 + 2, y0 + 6)])
    else:
        path(cr, kind, x0, y0, x1, y1)
    cr.stroke()

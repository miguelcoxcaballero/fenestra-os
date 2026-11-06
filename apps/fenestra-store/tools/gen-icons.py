#!/usr/bin/env python3
"""Generate Fenestra Store's symbolic UI icons (data/icons/ui/st-*-symbolic.svg).

All icons are original, drawn here from simple geometry on a 16x16 grid. They use filled
shapes only (outlines are even-odd rings), because GTK recolours symbolic icons by fill.
Every helper returns a list of paths; `+` joins shapes (union), cut(a, b) punches b out of a.
    python3 tools/gen-icons.py
"""
import math
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "icons", "ui")


def _rr(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    return (f"M{x + r:.2f} {y:.2f}H{x + w - r:.2f}A{r:.2f} {r:.2f} 0 0 1 {x + w:.2f} {y + r:.2f}"
            f"V{y + h - r:.2f}A{r:.2f} {r:.2f} 0 0 1 {x + w - r:.2f} {y + h:.2f}H{x + r:.2f}"
            f"A{r:.2f} {r:.2f} 0 0 1 {x:.2f} {y + h - r:.2f}V{y + r:.2f}A{r:.2f} {r:.2f} 0 0 1 {x + r:.2f} {y:.2f}Z")


def rr(x, y, w, h, r):
    return [_rr(x, y, w, h, r)]


def ring_rr(x, y, w, h, r, t=1.3):
    return [_rr(x, y, w, h, r) + _rr(x + t, y + t, w - 2 * t, h - 2 * t, max(0.2, r - t))]


def _circle(cx, cy, r):
    return (f"M{cx - r:.2f} {cy:.2f}A{r:.2f} {r:.2f} 0 1 0 {cx + r:.2f} {cy:.2f}"
            f"A{r:.2f} {r:.2f} 0 1 0 {cx - r:.2f} {cy:.2f}Z")


def circle(cx, cy, r):
    return [_circle(cx, cy, r)]


def ring(cx, cy, r, t=1.3):
    return [_circle(cx, cy, r) + _circle(cx, cy, r - t)]


def poly(*pts):
    return ["M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z"]


def cut(a, b):
    return ["".join(a) + "".join(b)]


def arc_band(cx, cy, r_out, r_in, a0, a1):
    """Thick arc from angle a0 to a1 (degrees, clockwise from 3 o'clock)."""
    def p(r, a):
        return cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
    large = 1 if (a1 - a0) % 360 > 180 else 0
    x0, y0 = p(r_out, a0)
    x1, y1 = p(r_out, a1)
    x2, y2 = p(r_in, a1)
    x3, y3 = p(r_in, a0)
    return [f"M{x0:.2f} {y0:.2f}A{r_out} {r_out} 0 {large} 1 {x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}"
            f"A{r_in} {r_in} 0 {large} 0 {x3:.2f} {y3:.2f}Z"]


def bar(x0, y0, x1, y1, t=1.3):
    """A straight stroke from (x0,y0) to (x1,y1) as a filled quad."""
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1
    ox, oy = -dy / n * t / 2, dx / n * t / 2
    return poly((x0 + ox, y0 + oy), (x1 + ox, y1 + oy), (x1 - ox, y1 - oy), (x0 - ox, y0 - oy))


ICONS = {
    "home": cut(poly((8, 1), (15.5, 7.6), (14.6, 8.6), (13.5, 7.7), (13.5, 15), (2.5, 15), (2.5, 7.7), (1.4, 8.6),
                 (0.5, 7.6)), poly((4, 6.6), (4, 13.6), (6.6, 13.6), (6.6, 9.6), (9.4, 9.6), (9.4, 13.6),
                                      (12, 13.6), (12, 6.6), (8, 3.1))),
    "apps": ring_rr(1, 1, 6, 6, 1.6) + ring_rr(9, 9, 6, 6, 1.6) + ring_rr(1, 9, 6, 6, 1.6) + ring(12, 4, 3.1),
    "games": ring_rr(0.5, 3.5, 15, 9, 3.6) + rr(3.2, 7.4, 4, 1.2, 0.4) + rr(4.6, 6, 1.2, 4, 0.4)
    + circle(10.8, 7.1, 0.9) + circle(12.4, 8.9, 0.9),
    "library": ring_rr(1, 2, 3.6, 12, 0.8) + ring_rr(5.4, 2, 3.6, 12, 0.8)
    + poly((10.2, 3.3), (11.6, 2.9), (15.2, 13.6), (13.8, 14.1)) + poly((9.6, 4.5), (10.4, 4.3), (11.9, 8.8), (11.1, 9.1)),
    "sources": rr(1, 3.4, 14, 1.2, 0.6) + rr(1, 7.4, 14, 1.2, 0.6) + rr(1, 11.4, 14, 1.2, 0.6)
    + circle(5, 4, 2.2) + circle(11, 8, 2.2) + circle(6.5, 12, 2.2),
    "search": ring(6.5, 6.5, 5.2, 1.4) + bar(10.2, 10.2, 14.8, 14.8, 1.8),
    "back": poly((1.5, 8), (7.2, 2.3), (8.2, 3.3), (4.2, 7.3), (14.5, 7.3), (14.5, 8.7), (4.2, 8.7), (8.2, 12.7),
                 (7.2, 13.7)),
    "chevron-left": poly((10.4, 1.8), (11.4, 2.8), (6.2, 8), (11.4, 13.2), (10.4, 14.2), (4.2, 8)),
    "chevron-right": poly((5.6, 1.8), (11.8, 8), (5.6, 14.2), (4.6, 13.2), (9.8, 8), (4.6, 2.8)),
    "check": poly((1.6, 8.4), (2.6, 7.4), (6, 10.8), (13.4, 3.4), (14.4, 4.4), (6, 12.8)),
    "update": arc_band(8, 8, 6.5, 5.2, 200, 340) + poly((14.5, 3.6), (14.9, 8.6), (10.2, 7.2))
    + arc_band(8, 8, 6.5, 5.2, 20, 160) + poly((1.5, 12.4), (1.1, 7.4), (5.8, 8.8)),
    "download": poly((7.3, 1), (8.7, 1), (8.7, 8.4), (11.4, 5.7), (12.4, 6.7), (8, 11.1), (3.6, 6.7), (4.6, 5.7),
                     (7.3, 8.4)) + rr(1.5, 13.2, 13, 1.4, 0.7),
    "open": poly((2, 3.2), (7, 3.2), (7, 4.5), (3.3, 4.5), (3.3, 12.7), (11.5, 12.7), (11.5, 9), (12.8, 9),
                 (12.8, 14), (2, 14)) + poly((9, 1.5), (14.5, 1.5), (14.5, 7), (13.2, 7), (13.2, 3.7), (8.1, 8.8),
                                             (7.2, 7.9), (12.3, 2.8), (9, 2.8)),
    "trash": rr(1.5, 3, 13, 1.3, 0.5) + rr(5.5, 1, 5, 1.3, 0.5)
    + cut(poly((2.8, 5), (13.2, 5), (12.2, 15), (3.8, 15)), poly((4.3, 6.3), (5, 13.7), (11, 13.7), (11.7, 6.3))),
    "info": ring(8, 8, 7) + rr(7.3, 7, 1.4, 5, 0.6) + circle(8, 4.8, 0.95),
    "warning": cut(poly((8, 1), (15.5, 14.5), (0.5, 14.5)), poly((8, 3.8), (2.8, 13.2), (13.2, 13.2)))
    + rr(7.35, 6, 1.3, 4.2, 0.6) + circle(8, 11.6, 0.8),
    "close": bar(3, 3, 13, 13, 1.4) + bar(13, 3, 3, 13, 1.4),
    # categories
    "cat-productivity": ring_rr(1, 1.5, 5, 5, 1) + ring_rr(1, 9.5, 5, 5, 1) + rr(8, 3.4, 7, 1.3, 0.6)
    + rr(8, 11.4, 7, 1.3, 0.6) + poly((2.2, 12), (2.9, 11.3), (3.4, 11.8), (5.2, 10), (5.9, 10.7), (3.4, 13.2)),
    "cat-creativity": poly((14.2, 1), (15, 1.8), (8.4, 9.6), (6.4, 7.6)) + poly((5.6, 8.4), (7.6, 10.4), (7, 12.6),
                                                                              (4.2, 14.4), (1, 15), (2.2, 12.6), (3.4, 9.6)),
    "cat-multimedia": circle(4.6, 12.2, 2.6) + rr(6, 2, 1.3, 10.2, 0.4) + poly((6, 1.2), (13.5, 3.2), (13.5, 6.4), (6, 4.4)),
    "cat-communication": ring_rr(1, 1.5, 14, 10, 3) + poly((3.6, 11.2), (6.6, 11.2), (3.6, 14.6)),
    "cat-utilities": ring_rr(1, 5, 14, 9.5, 1.5) + ring_rr(5, 2, 6, 4.2, 1) + rr(1.6, 8.6, 12.8, 1.2, 0)
    + rr(6.8, 7.8, 2.4, 2.8, 0.5),
    "cat-education": poly((8, 2), (15.5, 5.6), (8, 9.2), (0.5, 5.6)) + poly((3.4, 7.8), (4.7, 8.4), (4.7, 11),
                                                                              (8, 12.6), (11.3, 11), (11.3, 8.4),
                                                                              (12.6, 7.8), (12.6, 11.8), (8, 14),
                                                                              (3.4, 11.8))
    + rr(13.6, 5.6, 1.1, 5.6, 0.5),
    "cat-development": poly((5, 3.2), (5.9, 4.2), (2.2, 8), (5.9, 11.8), (5, 12.8), (0.3, 8))
    + poly((11, 3.2), (15.7, 8), (11, 12.8), (10.1, 11.8), (13.8, 8), (10.1, 4.2)) + bar(9.4, 2, 6.6, 14, 1.3),
    "cat-games": ring_rr(0.5, 3.5, 15, 9, 3.6) + rr(3.2, 7.4, 4, 1.2, 0.4) + rr(4.6, 6, 1.2, 4, 0.4)
    + circle(10.8, 7.1, 0.9) + circle(12.4, 8.9, 0.9),
    # permissions
    "perm-network": ring(8, 8, 7) + rr(1.5, 7.35, 13, 1.3, 0) + ring_rr(5.2, 1.2, 5.6, 13.6, 2.8, 1.2),
    "perm-folder": cut(poly((1, 2.5), (6, 2.5), (7.6, 4.2), (15, 4.2), (15, 13.5), (1, 13.5)),
                       poly((2.3, 6.6), (2.3, 12.2), (13.7, 12.2), (13.7, 6.6))),
    "perm-device": ring_rr(3.5, 3.5, 9, 9, 1.5) + rr(6.2, 6.2, 3.6, 3.6, 0.6) + rr(5.2, 0.8, 1.2, 2.4, 0.3)
    + rr(9.6, 0.8, 1.2, 2.4, 0.3) + rr(5.2, 12.8, 1.2, 2.4, 0.3) + rr(9.6, 12.8, 1.2, 2.4, 0.3)
    + rr(0.8, 5.2, 2.4, 1.2, 0.3) + rr(0.8, 9.6, 2.4, 1.2, 0.3) + rr(12.8, 5.2, 2.4, 1.2, 0.3) + rr(12.8, 9.6, 2.4, 1.2, 0.3),
    "perm-audio": poly((1, 5.5), (4, 5.5), (8, 2), (8, 14), (4, 10.5), (1, 10.5))
    + arc_band(8, 8, 4.4, 3.2, -45, 45) + arc_band(8, 8, 7, 5.8, -50, 50),
    "perm-window": ring_rr(1, 2, 14, 12, 1.6) + rr(2, 4.6, 12, 1.2, 0),
    "perm-shield": cut(poly((8, 0.8), (14.5, 3.2), (14.2, 8.4), (8, 15.2), (1.8, 8.4), (1.5, 3.2)),
                       poly((8, 2.3), (2.9, 4.2), (3.1, 8), (8, 13.4), (12.9, 8), (13.1, 4.2))),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, parts in ICONS.items():
        paths = "".join(f'<path fill="#2e3436" fill-rule="evenodd" d="{d}"/>' for d in parts)
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">{paths}</svg>\n'

        with open(os.path.join(OUT, f"st-{name}-symbolic.svg"), "w") as f:
            f.write(svg)
    print(f"wrote {len(ICONS)} icons to {OUT}")


if __name__ == "__main__":
    main()

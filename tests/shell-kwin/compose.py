#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Composes the surfaces saved by Fenestra Shell's test probe (org.fenestra.Shell.Test.Grab)
into one picture per screen, placed by their layer-shell layer, anchors and margins.
App windows are not in it: KWin's screenshot API needs OpenGL, which the container lacks.
    compose.py DIR OUT.png
"""
import json
import sys

from PIL import Image

TOP, BOTTOM, LEFT, RIGHT = 1, 2, 4, 8  # LayerShellQt::Window::Anchor


def place(start, size, span, anchored_a, anchored_b, margin_a, margin_b):
    if anchored_a and anchored_b:
        return start + margin_a + (span - margin_a - margin_b - size) // 2
    if anchored_a:
        return start + margin_a
    if anchored_b:
        return start + span - size - margin_b
    return start + (span - size) // 2


def zone_edge(a):
    """The edge an exclusive zone applies to: the only anchored edge, or of three anchored edges the
    one whose opposite is free (a bottom taskbar anchored bottom|left|right reserves the bottom only)."""
    if bin(a).count("1") == 1:
        return a
    if bin(a).count("1") == 3:
        for edge, opposite in ((TOP, BOTTOM), (BOTTOM, TOP), (LEFT, RIGHT), (RIGHT, LEFT)):
            if a & edge and not a & opposite:
                return edge
    return 0


def main(src, out, below_top=None):
    """below_top(canvas, x0, y0, dpr): draws between the BACKGROUND/BOTTOM layers and TOP/OVERLAY,
    where app windows are (snip-source.py)."""
    surfaces = json.load(open(f"{src}/surfaces.json"))
    if not surfaces:
        sys.exit("no surfaces")
    x0 = min(s["screen"][0] for s in surfaces)
    y0 = min(s["screen"][1] for s in surfaces)
    w = max(s["screen"][0] + s["screen"][2] for s in surfaces) - x0
    h = max(s["screen"][1] + s["screen"][3] for s in surfaces) - y0
    dpr = max(s["dpr"] for s in surfaces)
    canvas = Image.new("RGBA", (round(w * dpr), round(h * dpr)), (0, 0, 0, 255))
    # wlr-layer-shell: a surface with exclusive_zone 0 is placed inside the area left by the
    # exclusive zones of the surfaces anchored to the same edge (the taskbar's 48 px).
    def zone(screen, edge):
        return sum(o["exclusionZone"] for o in surfaces if o["screen"] == screen and o["exclusionZone"] > 0
                   and zone_edge(o["anchors"]) == edge)

    drew_windows = below_top is None
    for s in sorted(surfaces, key=lambda s: s["layer"]):
        if not drew_windows and s["layer"] >= 2:  # LayerShellQt::Window::LayerTop
            below_top(canvas, x0, y0, dpr)
            drew_windows = True
        img = Image.open(s["file"]).convert("RGBA")
        sx, sy, sw, sh = s["screen"]
        ml, mt, mr, mb = s["margins"]
        a = s["anchors"]
        if s["exclusionZone"] == 0:
            mt, mb = mt + zone(s["screen"], TOP), mb + zone(s["screen"], BOTTOM)
            ml, mr = ml + zone(s["screen"], LEFT), mr + zone(s["screen"], RIGHT)
        x = place(sx - x0, s["width"], sw, a & LEFT, a & RIGHT, ml, mr)
        y = place(sy - y0, s["height"], sh, a & TOP, a & BOTTOM, mt, mb)
        canvas.alpha_composite(img, (round(x * dpr), round(y * dpr)))
    if not drew_windows:
        below_top(canvas, x0, y0, dpr)
    canvas.convert("RGB").save(out)
    print(out, canvas.size)


if __name__ == "__main__":
    main(*sys.argv[1:3])

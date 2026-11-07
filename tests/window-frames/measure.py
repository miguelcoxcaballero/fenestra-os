#!/usr/bin/env python3
"""measure.py SHOT.png X Y W [SCALE] : a window whose frame's top-left is near logical (X, Y) and
whose width is about W logical px.  Prints, in physical px of the shot: the frame edges, the top
corner's opaque profile (radius), border colour, title-bar colour and height, and every caption
glyph (box, centre) and the plates of hovered buttons."""
import sys
import numpy as np
from PIL import Image

shot, X, Y, W = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
S = float(sys.argv[5]) if len(sys.argv) > 5 else 1.6
a = np.asarray(Image.open(shot).convert('RGB')).astype(int)
L = a.max(2)
x0, y0 = int(X * S), int(Y * S)
# the window's top edge row: first row (around y0) whose middle differs from the backdrop above
col = int((X + W / 2) * S)
bg = a[y0 - 12, col]
top = next(y for y in range(y0 - 10, y0 + 20) if np.abs(a[y, col] - bg).max() > 20)
row = top + int(40 * S)
left = next(x for x in range(x0 - 10, x0 + 30) if np.abs(a[row, x] - a[row, x0 - 12]).max() > 20)
right = next(x for x in range(int((X + W) * S) + 30, int((X + W) * S) - 40, -1) if np.abs(a[row, x] - a[row, int((X + W) * S) + 40]).max() > 20)
print(f'frame: left {left} right {right} (width {right - left + 1} = {(right - left + 1) / S:.1f} lp), top {top}')
print('top border rows', [tuple(a[top + i, col]) for i in range(4)])
print('left border cols', [tuple(a[row, left + i]) for i in range(4)])
title = tuple(a[top + 6, col])
h = next(i for i in range(3, 120) if np.abs(a[top + i, col] - np.array(title)).max() > 6)
print(f'title colour {title} height {h} px = {h / S:.1f} lp')
# corner: for the first 16 rows, the first column whose colour is no longer the backdrop
prof = []
for i in range(int(10 * S)):
    yy = top + i
    bgc = a[yy, left - 8]
    xx = next((x for x in range(left - 4, left + 30) if np.abs(a[yy, x] - bgc).max() > 25), None)
    prof.append(None if xx is None else xx - left)
print('top-left corner inset per row:', prof)
# glyphs: bright pixels in the right 160 lp of the title bar
reg = L[top + 2:top + h - 1, right - int(160 * S):right - 1]
base = np.median(reg)
m = np.abs(reg - base) > 60
cols = np.where(m.any(0))[0]
gs = []
if len(cols):
    s = p = cols[0]
    for c in cols[1:]:
        if c > p + 2: gs.append((s, p)); s = c
        p = c
    gs.append((s, p))
for g0, g1 in gs:
    r = np.where(m[:, g0:g1 + 1].any(1))[0]
    gx0, gx1 = g0 + right - int(160 * S), g1 + right - int(160 * S)
    print(f'glyph x {gx0}-{gx1} w {g1 - g0 + 1} y {r.min() + top + 2}-{r.max() + top + 2} h {r.max() - r.min() + 1}; '
          f'centre from right edge {(right + 1 - (gx0 + gx1 + 1) / 2) / S:.1f} lp, from top {((r.min() + r.max() + 1) / 2 + 2) / S:.1f} lp')

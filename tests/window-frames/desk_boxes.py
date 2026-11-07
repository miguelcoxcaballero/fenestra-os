#!/usr/bin/env python3
"""desk_boxes.py SHOT.png [BG=#1f1f1f] : vertical runs of non-background content in the first desktop
column (x < 160 px), each with its horizontal extent, plus label ink statistics: for each text run
the summed coverage (white-ness over the background) and the peak value, to compare glyph weight."""
import sys
import numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)[:, :160]
bg = np.array([int((sys.argv[2] if len(sys.argv) > 2 else '#1f1f1f')[i:i + 2], 16) for i in (1, 3, 5)])
d = np.abs(a - bg).max(2) > 24
runs, s = [], None
for y in range(min(700, a.shape[0])):
    if d[y].any() and s is None: s = y
    if not d[y].any() and s is not None: runs.append((s, y - 1)); s = None
for y0, y1 in runs:
    xs = np.where(d[y0:y1 + 1].any(0))[0]
    blk = a[y0:y1 + 1, xs.min():xs.max() + 1]
    lum = blk.mean(2)
    ink = np.clip(lum - bg.mean(), 0, None).sum() / 255
    print('rows %4d-%4d h %3d  cols %3d-%3d w %3d c %.1f  ink %.0f  peak %d  >200: %d' % (
        y0, y1, y1 - y0 + 1, xs.min(), xs.max(), xs.max() - xs.min() + 1, (xs.min() + xs.max()) / 2, ink, lum.max(), (lum > 200).sum()))

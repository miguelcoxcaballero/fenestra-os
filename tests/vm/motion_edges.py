#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""motion_edges.py DIR axis(y|x) x0 x1 y0 y1: per frame the moving edge (top for y, left for x) of what
differs from f000 inside the band, and whether the frame is a repeat of the previous one."""
import json, sys, numpy as np
from PIL import Image
d, axis = sys.argv[1], sys.argv[2]; x0, x1, y0, y1 = map(int, sys.argv[3:7])
t = json.load(open(f'{d}/times.json'))['times_ms']
f0 = np.asarray(Image.open(f'{d}/f000.png').convert('L')).astype(int)[y0:y1, x0:x1]
prev = None; out = []
for i, ti in enumerate(t):
    a = np.asarray(Image.open(f'{d}/f{i:03d}.png').convert('L')).astype(int)[y0:y1, x0:x1]
    diff = np.abs(a - f0) > 20
    rows = np.where(diff.mean(axis=1) > 0.5)[0] if axis == 'y' else None
    cols = np.where(diff.mean(axis=0) > 0.5)[0] if axis == 'x' else None
    e = (int(rows[0]) + y0 if len(rows) else None) if axis == 'y' else (int(cols[0]) + x0 if len(cols) else None)
    rep = prev is not None and np.array_equal(a, prev)
    prev = a
    out.append((i, ti, e, rep))
    if not rep: print(f'f{i:03d} {ti:7.1f} ms  edge {e}')
json.dump(out, open(f'{d}/edges.json', 'w'))

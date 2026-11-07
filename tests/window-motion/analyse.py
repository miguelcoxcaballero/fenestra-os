#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""analyse.py DIR [--roi x0,y0,x1,y1] [--ref first|last] [--base first|last] : window motion from frames.

DIR holds fNNN.png and times.json ({"times_ms": [...]}) - QMP screendumps of Windows 11
(tests/vm/motion_rec.py) or KWin ScreenShot2 frames of the bench (record.py).

A window that is scaled by s about a centre c and drawn at opacity a over a still background B
changes each pixel by D(x) = a * Dref(c + (x - c) / s) (linear blending), Dref being the change of
the settled window. So from D = |X - B| summed over the colour channels:
    s_x = sqrt(var_x(D) / var_x(Dref)),  s_y likewise,  c = centroid(D),
    a = sum(D) / (s_x * s_y * sum(Dref)).
No thresholds: exact for a pure scale + fade, and the shadow counts like the rest of the window.
--base: frame without the window (first for open/restore, last for close/minimize);
--ref: frame with the settled window (the other end). Prints one JSON line per frame."""
import json, os, sys
import numpy as np
from PIL import Image

def load(d, i, roi):
    im = np.asarray(Image.open(f'{d}/f{i:03d}.png').convert('RGB'), dtype=np.float32)
    if roi:
        x0, y0, x1, y1 = roi
        im = im[y0:y1, x0:x1]
    return im

def moments(D):
    tot = D.sum()
    if tot <= 0:
        return 0.0, None, None
    ys, xs = np.indices(D.shape)
    cx, cy = (D * xs).sum() / tot, (D * ys).sum() / tot
    vx, vy = (D * (xs - cx) ** 2).sum() / tot, (D * (ys - cy) ** 2).sum() / tot
    return tot, (cx, cy), (vx, vy)

def analyse(d, roi=None, base='first', ref='last', noise=3.0):
    times = json.load(open(f'{d}/times.json'))['times_ms']
    n = len(times)
    bi, ri = (0 if base == 'first' else n - 1), (n - 1 if ref == 'last' else 0)
    B, R = load(d, bi, roi), load(d, ri, roi)
    def diff(X):
        D = np.abs(X - B).sum(axis=2)
        D[D < noise] = 0          # compression / dithering noise
        return D
    tr, cr, vr = moments(diff(R))
    if vr is None:
        raise ValueError(f'{d}: the reference frame shows no window')
    rows = []
    for i in range(n):
        D = diff(load(d, i, roi))
        t, c, v = moments(D)
        if not c or t < tr * 0.002:
            rows.append({'i': i, 't': times[i], 'a': 0.0}); continue
        sx, sy = (v[0] / vr[0]) ** 0.5, (v[1] / vr[1]) ** 0.5
        rows.append({'i': i, 't': times[i], 'sx': round(sx, 4), 'sy': round(sy, 4),
                     'a': round(t / (sx * sy * tr), 4), 'cx': round(c[0] - cr[0], 1), 'cy': round(c[1] - cr[1], 1)})
    return rows, {'ref_centre': cr, 'ref_sd': (vr[0] ** .5, vr[1] ** .5)}

if __name__ == '__main__':
    a = sys.argv[1:]
    d = a[0]; opt = dict(zip(a[1::2], a[2::2]))
    roi = tuple(map(int, opt['--roi'].split(','))) if '--roi' in opt else None
    rows, info = analyse(d, roi, opt.get('--base', 'first'), opt.get('--ref', 'last'))
    print(json.dumps(info))
    for r in rows:
        print(json.dumps(r))

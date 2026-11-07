#!/usr/bin/env python3
# fitshadow.py SHOT.png [BG]: fit the desktop label shadow (black, Gaussian sigma, offset, strength)
# on white labels over a flat background (reference solid/*-100-01-taskbar.png, bg #1f1f1f).
import sys, numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float)
bg = float(sys.argv[2]) if len(sys.argv) > 2 else 31.0
boxes = [(54, 97, 4, 94), (178, 204, 0, 97)]
def conv1(m, k, axis):
    r = len(k) // 2
    p = np.pad(m, [(r, r) if i == axis else (0, 0) for i in range(2)])
    out = np.zeros_like(m)
    for i, w in enumerate(k):
        sl = [slice(None)] * 2; sl[axis] = slice(i, i + m.shape[axis]); out += w * p[tuple(sl)]
    return out
def gk(sigma, off):  # gaussian sampled at integer taps, centre shifted by off
    xs = np.arange(-8, 9)
    k = np.exp(-((xs - off) ** 2) / (2 * sigma ** 2)); return k / k.sum()
regs = [a[y0:y1, x0:x1] for (y0, y1, x0, x1) in boxes]
ms = [np.clip((r.max(2) - bg) / (255 - bg), 0, 1) for r in regs]
res = []
for sigma in np.arange(0.5, 2.6, 0.1):
    for dx in np.arange(-1.5, 1.01, 0.25):
        for dy in np.arange(-2, 0.51, 0.25):
            ks = [conv1(conv1(m, gk(sigma, dy), 0), gk(sigma, dx), 1) for m in ms]
            for A in np.arange(0.5, 4.01, 0.1):
                err = 0; n = 0
                for reg, m, k in zip(regs, ms, ks):
                    alpha = np.clip(A * k, 0, 1)
                    sel = (m == 0)
                    err += ((bg * (1 - alpha) - reg[..., 1])[sel] ** 2).sum(); n += sel.sum()
                res.append((err / n, sigma, dx, dy, A))
res.sort()
for r in res[:6]: print('rmse %.2f sigma %.1f dx %.2f dy %.2f A %.1f' % ((r[0]) ** .5, *r[1:]))

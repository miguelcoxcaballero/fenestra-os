#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# fitshadow-popup.py SHOT [left top right bottom] : fits the shadow around a popup panel on a flat
# wallpaper as two black Gaussian layers of the panel's rectangle (sigma, dy, opacity each),
# combined as 1 - (1 - a)(1 - b). Defaults: Start on user-win11 "Screenshot 2026-11-04 160039.png"
# (panel x 815..2065, y 411..1709 device px, wallpaper (72, 104, 96)). Prints device px.
import sys
from math import erf, sqrt
import numpy as np
from PIL import Image

im = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float)
L, T, R, B = map(int, sys.argv[2:6]) if len(sys.argv) > 5 else (815, 411, 2065, 1709)
bg = np.array([72, 104, 96.])
A = lambda v: 1 - (v / bg).mean()
Phi = np.vectorize(lambda z: 0.5 * (1 + erf(z / sqrt(2))))
cy, cx = (T + B) // 2, (L + R) // 2
data = [(0, L - x - 0.5, A(im[cy, x])) for x in range(L - 35, L)]
data += [(1, T - y - 0.5, A(im[y, cx])) for y in range(T - 21, T)]
data += [(2, y - B - 0.5, A(im[y, cx])) for y in range(B + 1, B + 19)]   # cut by the taskbar
K = np.array([d[0] for d in data]); D = np.array([d[1] for d in data]); V = np.array([d[2] for d in data])


def layer(s, dy, k):
    s = abs(s) + 0.3
    z = np.where(K == 0, D / s, np.where(K == 1, (D + dy) / s, (D - dy) / s))
    return k * (1 - Phi(z))


def model(p):
    return 1 - (1 - layer(*p[:3])) * (1 - layer(*p[3:]))


def nelder(f, x0, step, it=6000):
    pts = [np.array(x0, float)] + [np.array(x0, float) + np.eye(len(x0))[i] * step[i] for i in range(len(x0))]
    vals = [f(p) for p in pts]
    for _ in range(it):
        o = np.argsort(vals); pts = [pts[i] for i in o]; vals = [vals[i] for i in o]
        c = np.mean(pts[:-1], axis=0); r = c + (c - pts[-1]); fr = f(r)
        if fr < vals[0]:
            e = c + 2 * (c - pts[-1]); fe = f(e)
            pts[-1], vals[-1] = (e, fe) if fe < fr else (r, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = r, fr
        else:
            k = c + 0.5 * (pts[-1] - c); fk = f(k)
            if fk < vals[-1]:
                pts[-1], vals[-1] = k, fk
            else:
                pts = [pts[0] + 0.5 * (p - pts[0]) for p in pts]; vals = [f(p) for p in pts]
    i = int(np.argmin(vals)); return pts[i], vals[i]


f = lambda p: np.mean((model(p) - V) ** 2)
best = min((nelder(f, x0, [1, 1, .05, 2, 2, .05]) for x0 in ([5, 3, .3, 15, 15, .2], [3, 1, .2, 10, 10, .3], [8, 8, .3, 20, 20, .2])),
           key=lambda r: r[1])
p, v = best
print('layer 1: sigma %.2f dy %.2f opacity %.3f | layer 2: sigma %.2f dy %.2f opacity %.3f (device px) rms %.4f'
      % (abs(p[0]) + 0.3, p[1], p[2], abs(p[3]) + 0.3, p[4], p[5], np.sqrt(v)))

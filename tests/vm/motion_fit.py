#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""motion_fit.py travel final mode(open|close) DIR... : least-squares fit of the edge offsets (distinct frames)
for some Fluent curves and durations; offset(t) = travel*(1-B) opening, travel*B closing."""
import json, sys, itertools
travel, final, mode = float(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
def bez(x1, y1, x2, y2):
    def f(p):
        if p <= 0: return 0.0
        if p >= 1: return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(40):
            s = (lo + hi) / 2; x = 3*(1-s)**2*s*x1 + 3*(1-s)*s**2*x2 + s**3
            lo, hi = (s, hi) if x < p else (lo, s)
        s = (lo + hi) / 2; return 3*(1-s)**2*s*y1 + 3*(1-s)*s**2*y2 + s**3
    return f
runs = []
for d in sys.argv[4:]:
    e = json.load(open(d + '/edges.json'))
    seen, obs = None, []
    # opening: from the first non-None edge to final; closing: the frames after the last 'final' frame
    rows = [(t, edge) for i, t, edge, rep in e if not rep]
    if mode == 'open':
        k = next(i for i, (t, edge) in enumerate(rows) if edge is not None)
        seg = rows[k - 1:k + 8]
        obs = [(t, travel if edge is None else edge - final) for t, edge in seg]
        obs = [o for o in obs if True]
        cut = next((i for i, o in enumerate(obs) if o[1] == 0), len(obs)); obs = obs[:cut + 1]
    else:
        k = max(i for i, (t, edge) in enumerate(rows) if edge == final)
        seg = rows[k:k + 8]
        obs = []
        for t, edge in seg:
            obs.append((t, travel if edge is None else edge - final))
            if edge is None: break
    runs.append(obs)
    print(d.split('/')[-1], obs)
curves = {'decel(0,0,0,1)': (0, 0, 0, 1), 'decel-min(.33,0,.1,1)': (.33, 0, .1, 1), 'accel-mid(.7,0,1,.5)': (.7, 0, 1, .5),
          'accel(1,0,1,1)': (1, 0, 1, 1), 'easeIn(.42,0,1,1)': (.42, 0, 1, 1), 'accel(.9,.1,1,.2)': (.9, .1, 1, .2),
          'point(.1,.9,.2,1)': (.1, .9, .2, 1), 'accel-max(1,0,1,.5)?': (1, 0, 1, .5), 'cubicIn(.32,0,.67,0)': (.32, 0, .67, 0)}
res = []
for name, c in curves.items():
    f = bez(*c)
    for dur in range(80, 520, 10):
        tot, n = 0, 0
        for obs in runs:
            best = None
            for t0 in range(int(obs[0][0]) - 300, int(obs[-1][0]) + 1, 2):
                err = 0
                for t, off in obs:
                    p = (t - t0) / dur
                    m = travel * (1 - f(p)) if mode == 'open' else travel * f(p)
                    if off >= travel and m >= travel - 1: continue  # gone / not yet shown: any value past the end
                    if mode == 'close' and off >= travel: m = min(m, travel)
                    err += (m - off) ** 2
                best = err if best is None or err < best else best
            tot += best; n += len(obs)
        res.append(((tot / n) ** .5, name, dur))
res.sort()
for r in res[:12]: print('rms %.1f px  %s  %d ms' % r)
for name in curves:
    b = min(r for r in res if r[1] == name); print('  best for %-24s rms %.1f at %d ms' % (name, b[0], b[2]))

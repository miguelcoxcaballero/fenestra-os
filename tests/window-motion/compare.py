#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""compare.py BENCH_OUT [W H]: fits the frames recorded by record.py (analyse.py measurements)
against Windows 11's window transitions (design/motion.json "window") and prints, per recording,
the fitted start, the scale / size and opacity errors and the timing error.

Timing error: for each frame inside the motion, how far in time the Windows curve has to be moved
to give the measured value (the frame's time stamp itself is only known to ~±half a frame)."""
import json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyse

def bez(x1, y1, x2, y2):
    s = np.linspace(0, 1, 4001)
    xs = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
    ys = 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3
    return lambda p: np.interp(np.clip(p, 0, 1), xs, ys)
lin = lambda p: np.clip(p, 0, 1)

M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'design', 'motion.json')))['window']
def curve(name):
    c = M[name]; return c['duration'], bez(*c['curve'])

SCALE = 1.5
def fit(ts, meas, model, span, lo=-60, hi=200):
    best = None
    for t0 in np.arange(lo, hi, 0.5):
        e = sum((m - model(t - t0)) ** 2 for t, m in zip(ts, meas))
        if best is None or e < best[0]: best = (e, t0)
    return best[1]

def timing_error(ts, meas, model, t0, dur):
    errs = []
    grid = np.arange(-60, dur + 60, 0.25)
    vals = model(grid)
    for t, m in zip(ts, meas):
        rel = t - t0
        if rel <= 0 or rel >= dur: continue
        k = np.argmin(np.abs(vals - m)); errs.append(abs(grid[k] - rel))
    timing_error.share = float(np.mean(np.array(errs) <= 1000 / 60)) if errs else 1.0
    return max(errs) if errs else 0.0, (float(np.mean(errs)) if errs else 0.0)

def report(name, d):
    kind = name.rsplit('-', 1)[1]
    base, ref = ('last', 'first') if kind in ('close', 'minimize') else ('first', 'last')
    rows, info = analyse.analyse(d, None, base, ref)
    vis = [r for r in rows if 'sx' in r]
    ts = np.array([r['t'] for r in vis]); s = np.array([(r['sx'] + r['sy']) / 2 for r in vis]); a = np.array([r['a'] for r in vis])
    size = 2 * np.array(info['ref_sd']) * 1.732  # ~ window size (uniform texture: sd = w / sqrt(12))
    if kind == 'open':
        dur, B = curve('open'); od = M['open']['opacity_duration']
        ms = lambda t: np.where(t < 0, 0.8, 0.8 + 0.2 * B(t / dur)); ma = lambda t: lin(t / od)
    elif kind == 'close':
        dur, B = curve('close'); dl, od = M['close']['opacity_delay'], M['close']['opacity_duration']
        ms = lambda t: 1 - 0.05 * B(t / dur); ma = lambda t: 1 - lin((t - dl) / od)
    elif kind == 'minimize':
        dur, B = curve('minimize'); ms = lambda t: 1 - B(t / dur); ma = lambda t: np.ones_like(t)
    elif kind == 'restore':
        dur, B = curve('restore'); ms = lambda t: B(t / dur); ma = lambda t: np.ones_like(t)
    else:
        return report_morph(name, d, kind)
    # The motion starts at or before the first frame that shows it; fit the start on the scale.
    # (first frame showing the window or a change, minus up to 60 ms).
    moving = [t for t, v, o in zip(ts, s, a) if abs(v - 1) > 0.002 or abs(o - 1) > 0.01] or list(ts)
    first = min(moving)
    t0 = fit(ts, s, lambda t: ms(np.asarray(t)), dur, first - 60, first + 5)
    se = (s - ms(ts - t0)) * size.mean() * SCALE
    ae = a - ma(ts - t0)
    inside = (ts - t0 > 0) & (ts - t0 < dur)
    # Timing on the channel that changes most (close: the fade; the scale only moves 5 %).
    if kind == 'close':
        tmax, tmean = timing_error(ts, a, lambda t: ma(np.asarray(t)), t0, dur)
    else:
        tmax, tmean = timing_error(ts, s, lambda t: ms(np.asarray(t)), t0, dur)
    return {'recording': name, 'frames_in_motion': int(inside.sum()), 'start_ms': round(float(t0), 1),
            'size_rms_px': round(float(np.sqrt(np.mean(se[inside] ** 2))) if inside.any() else 0, 2),
            'size_max_px': round(float(np.max(np.abs(se[inside]))) if inside.any() else 0, 2),
            'opacity_rms': round(float(np.sqrt(np.mean(ae[inside] ** 2))) if inside.any() else 0, 3),
            'timing_max_ms': round(tmax, 1), 'timing_mean_ms': round(tmean, 1),
            'within_1_frame': round(timing_error.share, 2)}

def report_morph(name, d, kind):
    # Maximize / unmaximize: no still background under the window, so edges against the backdrop
    # (per row, from the screen's left columns in the frame where the window is small).
    times = json.load(open(f'{d}/times.json'))['times_ms']
    n = len(times)
    load = lambda i: np.asarray(Image.open(f'{d}/f{i:03d}.png').convert('RGB'), dtype=np.float32)
    small = load(0 if kind == 'maximize' else n - 1)
    # A snap to the left covers the left columns: the right ones stay backdrop.
    bg = np.median(small[:, -200:] if kind in ('snap', 'unsnap') else small[:, :200], axis=1)[:, None, :]
    def box(i):
        D = np.abs(load(i) - bg).sum(axis=2) > 40
        # The backdrop window's own rounded corners (fenestra-corners) are not the window under test.
        for ry in (slice(0, 16), slice(-16, None)):
            for rx in (slice(0, 16), slice(-16, None)):
                D[ry, rx] = False
        ys, xs = np.nonzero(D)
        return np.array([xs.min(), ys.min(), xs.max() + 1, ys.max() + 1], dtype=float) if len(xs) else None
    b0, b1 = box(0), box(n - 1)
    if b0 is None or b1 is None or np.abs(b1 - b0).max() <= 20:
        raise ValueError(f'{d}: the window did not change size')
    dur, B = curve('maximize')
    ts, ps = [], []
    for i in range(n):
        b = box(i)
        if b is None: continue
        span = b1 - b0; k = np.abs(span) > 20
        ts.append(times[i]); ps.append(float(np.mean((b[k] - b0[k]) / span[k])))
    ts, ps = np.array(ts), np.array(ps)
    moving = [t for t, p in zip(ts, ps) if p > 0.002] or list(ts)
    first = min(moving)
    model = lambda t: B(np.asarray(t) / dur)
    t0 = fit(ts, ps, model, dur, first - 60, first + 5)
    inside = (ts - t0 > 0) & (ts - t0 < dur)
    err = (ps - model(ts - t0)) * float(np.abs(b1 - b0).max()) * SCALE
    tmax, tmean = timing_error(ts, ps, model, t0, dur)
    return {'recording': name, 'frames_in_motion': int(inside.sum()), 'start_ms': round(float(t0), 1),
            'edge_rms_px': round(float(np.sqrt(np.mean(err[inside] ** 2))) if inside.any() else 0, 2),
            'edge_max_px': round(float(np.max(np.abs(err[inside]))) if inside.any() else 0, 2),
            'timing_max_ms': round(tmax, 1), 'timing_mean_ms': round(tmean, 1),
            'within_1_frame': round(timing_error.share, 2)}

if __name__ == '__main__':
    root = sys.argv[1]
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isfile(os.path.join(d, 'times.json')): continue
        try:
            r = report(name, d)
        except ValueError as e:
            print(json.dumps({'recording': name, 'error': str(e)})); continue
        if r: print(json.dumps(r))

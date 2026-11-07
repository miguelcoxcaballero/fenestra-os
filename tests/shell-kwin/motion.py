#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Records Fenestra Shell's popups opening and closing on the KWin bench and compares the motion
with the Windows 11 measurements (design/motion.json). Runs inside session.sh (MOTION=1).

    motion.py OUT [start quick center search ...]

For each popup: frame f000 before it opens, then the popup's surfaces (test probe GrabScopes, with
the taskbar for the exclusive zone) as fast as the probe answers, composed by compose.py into
fNNN.png with times.json ({"times_ms": [...]}, the format of tests/visual/motion.py, so its
`analyse` also runs on these folders). Each frame's time is the middle of its grab call.
The analysis scans the changed area above the taskbar against f000 (top edge, or left edge for
the right-hand panels), turns it into the offset from the settled position and fits it with the
Windows curve (only the start time free): rms in px, plus the duration measured on the frames.
"""
import json
import os
import sys
import time

from gi.repository import Gio, GLib
from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose  # noqa: E402

TASKBAR = 48
# name: (open expression, close expression, scope, axis, Windows curve, Windows open ms)
POPUPS = {
    'start': ('ShellState.toggleStart(null, -1)', 'ShellState.toggleStart(null, -1)', 'fenestra-start', 'y', (0, 0, 0, 1), 250),
    'search': ('ShellState.toggleSearch(null, -1)', 'ShellState.toggleSearch(null, -1)', 'fenestra-start', 'y', (0, 0, 0, 1), 250),
    'quick': ('ShellState.toggleQuickSettings(null, -1)', 'ShellState.toggleQuickSettings(null, -1)', 'fenestra-flyout', 'y', (0, 0, 0, 1), 250),
    'center': ('ShellState.toggleCalendar(null, -1)', 'ShellState.toggleCalendar(null, -1)', 'fenestra-flyout', 'x', (0.33, 0, 0.1, 1), 220),
}
CLOSE = ((0.7, 0, 1, 0.5), 167)

bus = Gio.bus_get_sync(Gio.BusType.SESSION)


def call(method, *args):
    sig = '(' + 's' * len(args) + ')'
    return bus.call_sync('org.fenestra.Shell', '/org/fenestra/Shell/Test', 'org.fenestra.Shell.Test', method,
                         GLib.Variant(sig, args), None, Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]


def bezier(x1, y1, x2, y2):
    def f(p):
        p = min(1.0, max(0.0, p))
        lo, hi = 0.0, 1.0
        for _ in range(40):
            s = (lo + hi) / 2
            x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3
            lo, hi = (s, hi) if x < p else (lo, s)
        s = (lo + hi) / 2
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s ** 2 * y2 + s ** 3
    return f


def record(d, scopes, expr, ms):
    os.makedirs(d, exist_ok=True)
    call('GrabScopes', f'{d}/raw000', scopes)
    t0 = time.monotonic()
    call('Eval', expr)
    times, n = [0.0], 1
    while (time.monotonic() - t0) * 1000 < ms:
        a = time.monotonic()
        call('GrabScopes', f'{d}/raw{n:03d}', scopes)
        times.append(round(((a + time.monotonic()) / 2 - t0) * 1000, 1))
        n += 1
    for i in range(n):
        compose.main(f'{d}/raw{i:03d}', f'{d}/f{i:03d}.png')
    json.dump({'times_ms': times, 'trigger': expr, 'roi': None}, open(f'{d}/times.json', 'w'))
    return times


def edges(d, times, axis):
    f0 = Image.open(f'{d}/f000.png').convert('RGB')
    roi = (0, 0, f0.width, f0.height - TASKBAR)
    base = f0.crop(roi)
    out = []
    for i in range(1, len(times)):
        fr = Image.open(f'{d}/f{i:03d}.png').convert('RGB').crop(roi)
        bb = ImageChops.difference(base, fr).convert('L').point(lambda v: 255 if v > 12 else 0).getbbox()
        out.append((times[i], None if not bb else (bb[1] if axis == 'y' else bb[0])))
    return out, f0.size


def fit(obs, travel, curve, ms, closing=False):
    """Best start time for offset(t) = travel * (1 - curve((t - t0) / ms)) (opening) or travel *
    curve(...) (closing); returns (rms px, t0)."""
    f = bezier(*curve)
    best = None
    for t0 in range(-50, 200):
        err = []
        for t, off in obs:
            p = (t - t0) / ms
            m = travel * f(p) if closing else travel * (1 - f(p))
            if t < t0:
                m = 0 if closing else travel
            err.append((min(m, travel) - off) ** 2)
        rms = (sum(err) / len(err)) ** 0.5
        if best is None or rms < best[0]:
            best = (round(rms, 1), t0)
    return best


def analyse(name, d_open, t_open, d_close, t_close):
    _, _, _, axis, curve, ms = POPUPS[name]
    eo, (w, h) = edges(d_open, t_open, axis)
    seen = [e for e in eo if e[1] is not None]
    if not seen:
        return {'error': 'popup never showed'}
    final = seen[-1][1]
    travel = (h - TASKBAR - final) if axis == 'y' else (w - final)
    # Hidden frames count as fully hidden (offset = travel).
    obs = [(t, travel if e is None else e - final) for t, e in eo]
    moving = [t for t, off in obs if 0 < off < travel]
    first = next((t for t, off in obs if off < travel), None)
    settled = next((t for t, off in obs if off == 0), None)
    ec, _ = edges(d_close, t_close, axis)
    # Closing frames: f000 of the close recording has the popup; compare against the open f000.
    f0 = Image.open(f'{d_open}/f000.png').convert('RGB').crop((0, 0, w, h - TASKBAR))
    cobs = []
    for i, t in enumerate(t_close[1:], 1):
        fr = Image.open(f'{d_close}/f{i:03d}.png').convert('RGB').crop((0, 0, w, h - TASKBAR))
        bb = ImageChops.difference(f0, fr).convert('L').point(lambda v: 255 if v > 12 else 0).getbbox()
        e = None if not bb else (bb[1] if axis == 'y' else bb[0])
        cobs.append((t, travel if e is None else e - final))
    gone = next((t for t, off in cobs if off >= travel), None)
    return {
        'axis': axis, 'final_edge': final, 'travel_px': travel,
        'frames_open': [(t, off) for t, off in obs], 'frames_close': cobs,
        'frame_interval_ms': round((t_open[-1] - t_open[1]) / max(1, len(t_open) - 2), 1),
        'first_visible_ms': first, 'settled_ms': settled, 'moving_frames': len(moving),
        'open_fit_windows': {'curve': curve, 'ms': ms, 'rms_px_t0': fit(obs, travel, curve, ms)},
        'close_gone_ms': gone,
        'close_fit_assumed': {'curve': CLOSE[0], 'ms': CLOSE[1], 'rms_px_t0': fit(cobs, travel, CLOSE[0], CLOSE[1], True)},
    }


def main(out, names):
    res = {}
    for name in names:
        expr_open, expr_close, scope, *_ = POPUPS[name]
        scopes = f'fenestra-taskbar,{scope}'
        d = f'{out}/{name}'
        t_open = record(f'{d}/open', scopes, expr_open, 700)
        time.sleep(0.6)
        t_close = record(f'{d}/close', scopes, expr_close, 500)
        time.sleep(0.6)
        res[name] = analyse(name, f'{d}/open', t_open, f'{d}/close', t_close)
        r = res[name]
        print('MOTION', name, json.dumps({k: v for k, v in r.items() if not k.startswith('frames')}), flush=True)
    json.dump(res, open(f'{out}/motion.json', 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:] or list(POPUPS))

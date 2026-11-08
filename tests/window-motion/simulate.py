#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""simulate.py : runs kwin/effects/fenestra-window-motion in a QJSEngine with a stand-in for KWin's
scripted-effect API and replays AnimationEffect's arithmetic (pieces multiply / add, waitAtSource,
kept targets, Left|Top anchors) frame by frame. Prints, per action, the largest gap between the
drawn rect / opacity and the Windows curve (design/motion.json values), in device px (SCALE, 1.5)
over continuous time: the pieces are whole milliseconds, so a curve that moves the window
~25 px per ms (minimize's last few ms) is off by up to that within one millisecond."""
import json, math, os, sys
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine

app = QCoreApplication.instance() or QCoreApplication([])

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', 'kwin', 'effects', 'fenestra-window-motion', 'contents', 'code', 'main.js')

STUB = r'''
var __anims = [], __id = 0, __log = [];
function __sig() { var s = { cbs: [], connect: function (f) { s.cbs.push(f); }, emit: function () { var a = arguments; s.cbs.forEach(function (f) { f.apply(null, a); }); } }; return s; }
var Effect = { Scale: 'Scale', Opacity: 'Opacity', Translation: 'Translation', Size: 'Size', CrossFadePrevious: 'CF',
  Left: 1, Top: 2, Right: 4, Bottom: 8, WindowAddedGrabRole: 1, WindowClosedGrabRole: 2, WindowForceBlurRole: 3, WindowForceBackgroundContrastRole: 4 };
var QEasingCurve = { Linear: 0 };
var KWin = { ScreenArea: 0 };
var effect = { animationEnded: __sig(), configChanged: __sig(), isGrabbed: function () { return false; }, readConfig: function (k, d) { return d; } };
var effects = { windowAdded: __sig(), windowClosed: __sig(), windowDataChanged: __sig(), windowActivated: __sig(), mouseChanged: __sig(), stackingOrder: [], hasActiveFullScreenEffect: false,
  virtualScreenGeometry: { x: 0, y: 0, width: 1920, height: 1200 } };
function __mk(opts, kept) {
  var ids = [];
  opts.animations.forEach(function (a) {
    var id = ++__id;
    __anims.push({ id: id, w: opts.window, type: a.type, from: a.from, to: a.to, delay: a.delay !== undefined ? a.delay : (opts.delay || 0),
                   duration: a.duration || opts.duration, kept: kept, anchor: a.targetAnchor || 0, start: __now });
    ids.push(id);
  });
  return ids.length === 1 ? ids[0] : ids;
}
var __now = 0;
function animate(o) { return __mk(o, false); }
function set(o) { return __mk(o, true); }
function cancel(ids) { if (!Array.isArray(ids)) ids = [ids]; __anims = __anims.filter(function (a) { return ids.indexOf(a.id) < 0; }); return true; }
function retarget() { return false; }
function redirect() { return false; }
function animationTime(x) { return x; }
'''

def run(action, W=1200.0, H=800.0, X=300.0, Y=200.0, icon=(900.0, 1150.0, 48.0, 48.0), old=None, fps=240):
    eng = QJSEngine()
    eng.installExtensions(QJSEngine.Extension.ConsoleExtension)
    r = eng.evaluate(STUB + open(SRC).read() + '\n;0')
    if r.isError():
        raise SystemExit('JS error: ' + r.toString() + ' line ' + str(r.property('lineNumber').toInt()))
    setup = f'''
    var w = {{ windowClass: 'app app', hasDecoration: true, managed: true, normalWindow: true, dialog: false, popupWindow: false,
      visible: true, minimized: false, skipsCloseAnimation: false, geometry: {{ x: {X}, y: {Y}, width: {W}, height: {H} }},
      iconGeometry: {{ x: {icon[0]}, y: {icon[1]}, width: {icon[2]}, height: {icon[3]} }},
      minimizedChanged: __sig(), windowMaximizedStateAboutToChange: __sig(), windowMaximizedStateChanged: __sig(),
      setData: function () {{}} }};
    effects.windowAdded.emit(w);  // open
    '''
    eng.evaluate(setup)
    if action != 'open':
        eng.evaluate('__anims = []; __log = [];')
        if action == 'close': eng.evaluate('effects.windowClosed.emit(w)')
        elif action == 'minimize': eng.evaluate('w.minimized = true; w.minimizedChanged.emit()')
        elif action == 'restore': eng.evaluate('w.minimized = false; w.minimizedChanged.emit()')
        elif action == 'maximize':
            ox, oy, ow, oh = old
            eng.evaluate(f'w.geometry = {{x:{ox},y:{oy},width:{ow},height:{oh}}}; w.windowMaximizedStateAboutToChange.emit(); '
                         f'w.geometry = {{x:0,y:0,width:1920,height:1152}}; w.windowMaximizedStateChanged.emit()')
    anims = eng.evaluate('JSON.stringify(__anims)').toString()
    anims = json.loads(anims)
    g = json.loads(eng.evaluate('JSON.stringify(w.geometry)').toString())
    # Replay AnimationEffect: per time t, product/sum of interpolated values.
    out = []
    end = max(a['delay'] + a['duration'] for a in anims)
    for k in range(int(end * fps / 1000) + 2):
        t = k * 1000 / fps
        sx = sy = op = 1.0; tx = ty = 0.0; compx = compy = 0.0
        for a in anims:
            st = a['delay']
            if t < st:
                p = 0.0  # waitAtSource (from is set)
            elif t >= st + a['duration']:
                if not a['kept']: continue
                p = 1.0
            else:
                p = (t - st) / a['duration']
            to = a['to']
            f = a.get('from')
            if f is None: f = 0.0 if a['type'] == 'Translation' else 1.0  # KWin's default source
            val = lambda i: (f[i] if isinstance(f, list) else (f if not isinstance(f, dict) else f['value%d' % (i + 1)])) 
            def comp(v, i):
                if isinstance(v, dict): return v['value%d' % (i + 1)]
                return v
            v0 = comp(f, 0) + p * (comp(to, 0) - comp(f, 0)); v1 = comp(f, 1) + p * (comp(to, 1) - comp(f, 1))
            if a['type'] == 'Scale':
                if not (a['anchor'] & 1): tx += 0.5 * (1 - v0) * g['width']
                if not (a['anchor'] & 2): ty += 0.5 * (1 - v1) * g['height']
                sx *= v0; sy *= v1
            elif a['type'] == 'Opacity': op *= v0
            elif a['type'] == 'Translation': tx += v0; ty += v1
        out.append((t, g['x'] + tx, g['y'] + ty, g['width'] * sx, g['height'] * sy, op))
    return out, len(anims)

def bez(x1, y1, x2, y2):
    def f(p):
        if p <= 0: return 0.0
        if p >= 1: return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(50):
            s = (lo + hi) / 2
            x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
            lo, hi = (s, hi) if x < p else (lo, s)
        s = (lo + hi) / 2
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3
    return f

def expected(action, t, W=1200.0, H=800.0, X=300.0, Y=200.0, icon=(900.0, 1150.0, 48.0, 48.0), old=None):
    lin = lambda t0, d: min(1, max(0, (t - t0) / d))
    if action == 'open':
        s = 0.8 + 0.2 * bez(0, 0, 0, 1)(t / 250); o = lin(0, 83)
        return (X + (1 - s) * W / 2, Y + (1 - s) * H / 2, W * s, H * s, o)
    if action == 'close':
        s = 1 - 0.05 * bez(1, 1, 0, 1)(t / 175); o = 1 - lin(25, 150)
        return (X + (1 - s) * W / 2, Y + (1 - s) * H / 2, W * s, H * s, o)
    cx, cy = icon[0] + icon[2] / 2, icon[1] + icon[3] / 2
    if action == 'minimize':
        v = bez(1, 0, 1, 1)(t / 167)
        return (X + v * (cx - X), Y + v * (cy - Y), W * (1 - v), H * (1 - v), 1)
    if action == 'restore':
        v = bez(0, 0, 0, 1)(t / 175)
        return (cx + v * (X - cx), cy + v * (Y - cy), W * v, H * v, 1)
    if action == 'maximize':
        v = bez(0.8, 0, 0, 1)(t / 300); ox, oy, ow, oh = old
        return (ox + v * (0 - ox), oy + v * (0 - oy), ow + v * (1920 - ow), oh + v * (1152 - oh), 1)

if __name__ == '__main__':
    scale = float(os.environ.get('SCALE', '1.5'))
    for action in ('open', 'close', 'minimize', 'restore', 'maximize'):
        kw = {'old': (300.0, 200.0, 1200.0, 800.0)} if action == 'maximize' else {}
        frames, n = run(action, **kw)
        err = max(max(abs(a - b) for a, b in zip(f[1:5], expected(action, f[0], **kw)[:4])) for f in frames)
        oerr = max(abs(f[5] - expected(action, f[0], **kw)[4]) for f in frames)
        print(f'{action:9s} pieces {n:3d}  max rect error {err * scale:.2f} device px  max opacity error {oerr:.4f}')

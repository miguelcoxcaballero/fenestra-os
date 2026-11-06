#!/usr/bin/env python3
"""Measure shell panels in reference screenshots and write design/reference/measurements.json.

    tests/visual/measure.py SHOTS_DIR [-o design/reference/measurements.json] [--panels tests/visual/panels.json]

SHOTS_DIR holds PNGs named <theme>-<pct>-<NN>-<name>.png (dark-100-06-start.png) and, next to
each one, an optional <same>.json sidecar written by the capture script:
    {"seed": [x, y], "bg": "#1f1f1f", "wallpaper": "solid", "hover": [x, y], "note": "..."}
Screenshots never enter the repo: only this script and the numbers it prints.

Geometry is measured only on the solid-background pass (wallpaper "solid"): the panel is the
connected region around the seed that differs from the empty desktop of the same pass
(capture 01, or the capture named by "base" in panels.json when windows are open). The VM
draws no panel shadows. Anything that depends on acrylic, mica, shadows or animation is
written with "reliable": false. Every value carries the screenshot it comes from and the
pixel it was read at. Token probes (taskbar icons and indicators, search box, Start grid,
menu rows, quick tiles, calendar day, Alt+Tab thumbnail, title bar, text size) read the
design/tokens.json keys that are not a whole panel.

The output file is shared: only this script's top-level keys (_comment, not_measured,
skipped, entries) are replaced; the dialog sections written by measure_dialogs.py are kept.
"""
import argparse
import json
import os
import re
import sys
from collections import deque

from PIL import Image, ImageChops, ImageDraw

NAME = re.compile(r'^(dark|light)-(\d{3})-(\d{2})-([a-z0-9-]+)\.png$')


def hexc(c):
    return '#%02x%02x%02x' % tuple(c[:3])


def parse_hex(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def close(a, b, tol):
    return max(abs(a[i] - b[i]) for i in range(3)) <= tol


class Shot:
    def __init__(self, path):
        self.path = path
        self.file = os.path.basename(path)
        m = NAME.match(self.file)
        if not m:
            raise ValueError(f'{self.file}: expected <theme>-<pct>-<NN>-<name>.png')
        self.theme, pct, self.num, self.name = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        self.scale = pct / 100
        self.im = Image.open(path).convert('RGB')
        self.px = self.im.load()
        self.W, self.H = self.im.size
        side = path[:-4] + '.json'
        self.meta = json.load(open(side)) if os.path.exists(side) else {}
        self.bg = parse_hex(self.meta.get('bg', '#1f1f1f'))
        self.solid = self.meta.get('wallpaper', 'solid') == 'solid'


class Out:
    def __init__(self):
        self.entries = []

    def add(self, shot, key, value, at, reliable=True, **extra):
        e = {'key': key, 'value': value, 'scale': shot.scale, 'theme': shot.theme,
             'source': shot.file, 'at': [int(at[0]), int(at[1])], 'reliable': bool(reliable and shot.solid)}
        e.update(extra)
        self.entries.append(e)


# --- taskbar -----------------------------------------------------------------------------

def taskbar_top(shot):
    """Top row of the taskbar: the strongest horizontal edge in the bottom 120 px.

    In dark theme the bar fill is within a few levels of #1f1f1f, so it is found by its
    top border line, not by its colour."""
    ds = {y: sum(abs(lum(shot.px[x, y]) - lum(shot.px[x, y - 1])) for x in range(0, shot.W, 8))
          for y in range(shot.H - 120, shot.H)}
    peak = max(ds.values())
    # the border line makes two edges (above and below it): the bar starts at the upper one,
    # and a faint 1 px border above the strongest edge still belongs to the bar
    t = min(y for y, d in ds.items() if d >= 0.5 * peak)
    n = len(range(0, shot.W, 8))
    while t - 1 in ds and ds[t] / n >= 2.5 and t - 2 >= shot.H - 120 and ds[t - 1] / n >= 2.5:
        t -= 1
    return t


_TB = {}


def bar_top(shot):
    """Taskbar top measured on capture 01 of the same theme and scale (no panel covers it there)."""
    d = os.path.dirname(shot.path)
    return (_TB.get((d, shot.theme, shot.scale))
            or next((v for (dd, _t, sc), v in _TB.items() if dd == d and sc == shot.scale), None)
            or taskbar_top(shot))


def measure_taskbar(shot, out, spec):
    top = taskbar_top(shot)
    _TB[(os.path.dirname(shot.path), shot.theme, shot.scale)] = top
    _BASE[(os.path.dirname(shot.path), shot.theme, shot.scale)] = shot.im
    out.add(shot, 'taskbar.height', shot.H - top, (4, top))
    fill = median_patch(shot, (4, top + 6), 2)
    out.add(shot, 'taskbar.background', hexc(fill), (4, top + 6), reliable=False, note='acrylic/mica: VM render')
    out.add(shot, 'taskbar.border', hexc(shot.px[4, top]), (4, top), reliable=False)
    # icon buttons: columns in the bar whose pixels depart from the bar fill, grouped into runs
    cy = top + (shot.H - top) // 2
    runs = runs_where(lambda x: not close(shot.px[x, cy], fill, 24), 0, shot.W)
    for i, (a, b) in enumerate(runs):
        out.add(shot, f'taskbar.content[{i}].x', a, (a, cy), width=b - a)
    return top


def runs_where(pred, a, b, gap=3):
    runs, start, last = [], None, None
    for x in range(a, b):
        if pred(x):
            if start is None:
                start = x
            elif x - last > gap:
                runs.append((start, last + 1))
                start = x
            last = x
    if start is not None:
        runs.append((start, last + 1))
    return runs


# --- panels ------------------------------------------------------------------------------

def median_patch(shot, at, r):
    vals = [shot.px[x, y] for x in range(max(0, at[0] - r), min(shot.W, at[0] + r + 1))
            for y in range(max(0, at[1] - r), min(shot.H, at[1] + r + 1))]
    return tuple(sorted(v[i] for v in vals)[len(vals) // 2] for i in range(3))


def panel_mask(shot, limit_y, base=None, tol=0):
    """255 where the pixel differs from the empty desktop of the same pass (capture 01), else 0.

    The VM draws no shadows, and some panels are darker than #1f1f1f (the dark toast fill is
    #1c1c1c) or have edges within 1-3 levels of it (the dark Search tiles), so any difference
    counts: the desktop is pixel-identical between captures of one pass (lossless QMP dumps).
    Without that capture, anything not exactly the solid background counts."""
    if base is None:
        base = _BASE.get((os.path.dirname(shot.path), shot.theme, shot.scale))
    diff = ImageChops.difference(shot.im.crop((0, 0, shot.W, limit_y)),
                                 base.crop((0, 0, shot.W, limit_y)) if base is not None
                                 else Image.new('RGB', (shot.W, limit_y), shot.bg))
    r, g, b = diff.split()
    d = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > tol else 0)
    m = Image.new('L', (shot.W, shot.H), 0)
    m.paste(d, (0, 0))
    return m


def panel_box(shot, seed, limit_y, base=None, tol=0):
    m = panel_mask(shot, limit_y, base, tol)
    if m.getpixel(tuple(seed)) == 0:
        raise ValueError(f'{shot.file}: seed {seed} is not on a panel pixel')
    ImageDraw.floodfill(m, tuple(seed), 128)
    sel = m.point(lambda v: 255 if v == 128 else 0)
    # fill holes: the flood stops at dark text in light theme, the bbox is unaffected
    return sel.getbbox(), sel


def corner_radius(sel, box):
    """Fit r so that the row insets of the top-left corner match a circle of radius r."""
    x0, y0 = box[0], box[1]
    sp = sel.load()
    insets = []
    for dy in range(0, 20):
        x = x0
        while x < x0 + 30 and sp[x, y0 + dy] == 0:
            x += 1
        insets.append(x - x0)
    best = None
    for r in range(0, 21):
        err = 0
        for dy, ins in enumerate(insets):
            yy = r - dy - 0.5
            exp = r - (r * r - yy * yy) ** 0.5 if 0 <= dy < r else 0
            err += (exp - ins) ** 2
        if best is None or err < best[0]:
            best = (err, r)
    return best[1], insets[:best[1] + 1]


def shadow_extent(shot, box):
    """Pixels to the left of the panel darker than the background (VM render: not reliable)."""
    cy = (box[1] + box[3]) // 2
    bl = lum(shot.bg)
    n, darkest = 0, bl
    x = box[0] - 1
    while x >= 0 and lum(shot.px[x, cy]) < bl - 0.5:
        darkest = min(darkest, lum(shot.px[x, cy]))
        n += 1
        x -= 1
    return n, round(bl - darkest, 1)


def elements(shot, box, fill, radius, tol=28, merge=6):
    """Connected groups of pixels that differ from the panel fill: icons, words, controls."""
    x0, y0, x1, y1 = box
    inset = max(2, radius // 2)
    w, h = x1 - x0, y1 - y0
    seen = bytearray(w * h)
    px = shot.px
    comps = []
    for y in range(inset, h - inset):
        for x in range(inset, w - inset):
            i = y * w + x
            if seen[i] or close(px[x0 + x, y0 + y], fill, tol):
                continue
            q = deque([(x, y)])
            seen[i] = 1
            bx0 = bx1 = x
            by0 = by1 = y
            colors = {}
            while q:
                cx, cy = q.popleft()
                c = px[x0 + cx, y0 + cy]
                colors[c] = colors.get(c, 0) + 1
                bx0, bx1, by0, by1 = min(bx0, cx), max(bx1, cx), min(by0, cy), max(by1, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if inset <= nx < w - inset and inset <= ny < h - inset:
                        j = ny * w + nx
                        if not seen[j] and not close(px[x0 + nx, y0 + ny], fill, tol):
                            seen[j] = 1
                            q.append((nx, ny))
            comps.append([bx0, by0, bx1 + 1, by1 + 1, colors])
    # merge glyphs into words/rows and icon parts into icons
    changed = True
    while changed:
        changed = False
        comps.sort(key=lambda c: (c[1], c[0]))
        res = []
        for c in comps:
            for r in res:
                if c[0] <= r[2] + merge and r[0] <= c[2] + merge and c[1] <= r[3] + 1 and r[1] <= c[3] + 1:
                    r[0], r[1], r[2], r[3] = min(r[0], c[0]), min(r[1], c[1]), max(r[2], c[2]), max(r[3], c[3])
                    for k, v in c[4].items():
                        r[4][k] = r[4].get(k, 0) + v
                    changed = True
                    break
            else:
                res.append(c)
        comps = res
    outl = []
    for c in comps:
        if (c[2] - c[0]) * (c[3] - c[1]) < 4:
            continue
        # dominant colour = the one furthest from the fill among the frequent ones (text, glyph)
        freq = sorted(c[4].items(), key=lambda kv: -kv[1])[:6]
        ink = max(freq, key=lambda kv: max(abs(kv[0][i] - fill[i]) for i in range(3)))[0]
        outl.append({'box': [x0 + c[0], y0 + c[1], c[2] - c[0], c[3] - c[1]], 'color': hexc(ink)})
    return outl


def controls(shot, box, fill, radius, lo=3, hi=28, min_area=300):
    """Flat areas whose colour is close to, but not the panel fill: search boxes, buttons,
    footers, toggles' tracks. Returns their boxes and median colour."""
    x0, y0, x1, y1 = box
    inset = max(2, radius // 2)
    w, h = x1 - x0, y1 - y0
    m = Image.new('L', (w, h), 0)
    mp = m.load()
    px = shot.px
    for y in range(inset, h - inset):
        for x in range(inset, w - inset):
            c = px[x0 + x, y0 + y]
            d = max(abs(c[i] - fill[i]) for i in range(3))
            if lo < d <= hi:
                mp[x, y] = 255
    res = []
    for y in range(inset, h - inset, 2):
        for x in range(inset, w - inset, 2):
            if mp[x, y] == 255:
                ImageDraw.floodfill(m, (x, y), 100)
                part = m.point(lambda v: 255 if v == 100 else 0)
                bb = part.getbbox()
                ImageDraw.floodfill(m, (x, y), 50)
                area = sum(part.histogram()[255:])
                if bb and area >= min_area and (bb[2] - bb[0]) >= 12 and (bb[3] - bb[1]) >= 8:
                    cx, cy = bb[0] + 3, (bb[1] + bb[3]) // 2
                    res.append({'box': [x0 + bb[0], y0 + bb[1], bb[2] - bb[0], bb[3] - bb[1]],
                                'color': hexc(px[x0 + cx, y0 + cy])})
    return res


_BASE = {}
_BOX = {}


def auto_seed(shot, base, limit_y):
    """A pixel of the panel's fill: the most frequent colour among pixels that differ from the
    empty desktop (capture 01 of the same pass), nearest their centre (the dark toast is darker
    than the background, so lighter is not required)."""
    bp, px = base.load(), shot.px
    cols, pts = {}, []
    for y in range(0, limit_y, 3):
        for x in range(0, shot.W, 3):
            c = px[x, y]
            if max(abs(c[i] - bp[x, y][i]) for i in range(3)) > 2:
                cols[c] = cols.get(c, 0) + 1
                pts.append((x, y, c))
    if not cols:
        raise ValueError(f'{shot.file}: nothing differs from the empty desktop')
    fill = max(cols, key=cols.get)
    sel = [(x, y) for x, y, c in pts if c == fill]
    cx = sum(x for x, _ in sel) / len(sel)
    cy = sum(y for _, y in sel) / len(sel)
    x, y = min(sel, key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
    return [x, y]


def flat_region(shot, seed, tol=4, reach=(200, 120)):
    """Area of the seed's colour (within tol) connected to the seed: shapes inside it (glyphs,
    the pointer) leave holes but do not change the box."""
    sel = Image.new('L', (shot.W, shot.H), 0)
    ref = shot.px[seed[0], seed[1]]
    sp = sel.load()
    for y in range(max(0, seed[1] - reach[1]), min(shot.H, seed[1] + reach[1])):
        for x in range(max(0, seed[0] - reach[0]), min(shot.W, seed[0] + reach[0])):
            if close(shot.px[x, y], ref, tol):
                sp[x, y] = 255
    ImageDraw.floodfill(sel, tuple(seed), 128)
    sel = sel.point(lambda v: 255 if v == 128 else 0)
    return sel.getbbox(), sel


def spec_for(shot, spec):
    """panels.json entry with its overrides for this capture: "variants" by capture name
    (15-notifications-2 -> another key), then "passes" by pass (dark-100, light-150...)."""
    pname = f'{shot.theme}-{int(round(shot.scale * 100))}'
    spec = dict(spec, **spec.get('variants', {}).get(shot.name, {}))
    return dict(spec, **spec.get('passes', {}).get(pname, {}))


def measure_panel(shot, out, spec, tb_top):
    spec = spec_for(shot, spec)
    # seed: a pixel inside the panel; the sidecar wins, else panels.json (100 % coords, y from the bottom)
    base = _BASE.get((os.path.dirname(shot.path), shot.theme, shot.scale))
    pname = f'{shot.theme}-{int(round(shot.scale * 100))}'
    ref_name = spec.get('base')
    if isinstance(ref_name, dict):
        ref_name = ref_name.get(pname)
    if spec.get('backdrop'):
        # modal dialog on a dimmed screen (UAC): the dialog is what differs from the backdrop colour
        bx, by = spec['backdrop']
        base = Image.new('RGB', (shot.W, shot.H), shot.px[int(bx * shot.scale), int(by * shot.scale)])
    elif ref_name:
        # panels.json "base": the same windows without the panel (another capture of this pass),
        # so the mask holds only the panel and not the windows behind it
        rp = os.path.join(os.path.dirname(shot.path), f'{pname}-{ref_name}.png')
        if os.path.exists(rp):
            base = Image.open(rp).convert('RGB')
    pass_seed = spec.get('seeds', {}).get(pname)
    if pass_seed:
        # panels.json "seeds": {"dark-100": [x, y]} = absolute pixel for that pass, checked by eye;
        # it wins over the sidecar and the automatic seed (other windows open, panel off-centre)
        seed = list(pass_seed)
    elif 'seed' in shot.meta:
        seed = shot.meta['seed']
    elif base is not None and spec.get('mode', 'panel') == 'panel':
        seed = auto_seed(shot, base, tb_top if spec.get('above_taskbar', True) else shot.H)
    else:
        sx, sy = spec['seed']
        seed = [shot.W // 2 if sx == 'center' else int(sx * shot.scale), shot.H - int(sy * shot.scale)]
    mode = spec.get('mode', 'panel')
    if mode == 'fullscreen':
        box = (0, 0, shot.W, shot.H)
        sel = Image.new('L', (shot.W, shot.H), 255)
    elif mode == 'region':
        # a flat-coloured area around the seed (hover highlight, caption button), any background
        r = spec.get('reach', [200, 120])
        box, sel = flat_region(shot, seed, tol=spec.get('tol', 4), reach=(int(r[0] * shot.scale), int(r[1] * shot.scale)))
    elif mode == 'hoverdiff':
        # the hover highlight = what differs from the same state without hover, around the seed
        ref = Image.open(os.path.join(os.path.dirname(shot.path),
                                      f"{shot.theme}-{int(round(shot.scale * 100))}-{spec['ref']}.png")).convert('RGB')
        rp = ref.load()
        sel = Image.new('L', (shot.W, shot.H), 0)
        sp = sel.load()
        r = int(80 * shot.scale)
        for y in range(max(0, seed[1] - r), min(shot.H, seed[1] + r)):
            for x in range(max(0, seed[0] - r), min(shot.W, seed[0] + r)):
                if max(abs(shot.px[x, y][i] - rp[x, y][i]) for i in range(3)) > 3:
                    sp[x, y] = 255
        # the highlight is the most frequent colour among the differences; keep the flat area of
        # that colour around the seed, so the mouse pointer drawn on top stays out of the box
        cols = {}
        for y in range(max(0, seed[1] - r), min(shot.H, seed[1] + r)):
            for x in range(max(0, seed[0] - r), min(shot.W, seed[0] + r)):
                if sp[x, y]:
                    cols[shot.px[x, y]] = cols.get(shot.px[x, y], 0) + 1
        if not cols:
            raise ValueError(f'{shot.file}: hover changed nothing')
        hl = max(cols, key=cols.get)
        pts = [(x, y) for y in range(max(0, seed[1] - r), min(shot.H, seed[1] + r))
               for x in range(max(0, seed[0] - r), min(shot.W, seed[0] + r)) if sp[x, y] and shot.px[x, y] == hl]
        start = min(pts, key=lambda q: (q[0] - seed[0]) ** 2 + (q[1] - seed[1]) ** 2)
        box, sel = flat_region(shot, start, tol=4)
        seed = list(start)
    elif 'mask' in shot.meta:
        # exact panel shape supplied with the capture (Fenestra bench: from the surface's alpha)
        sel = Image.open(os.path.join(os.path.dirname(shot.path), shot.meta['mask'])).convert('L')
        box = sel.getbbox()
        if not box:
            raise ValueError(f'{shot.file}: empty mask')
        seed = [box[0] + (box[2] - box[0]) // 2, box[1] + 8]
    else:
        # mask_tol: ignore differences up to this many levels (window shadows that change with focus)
        box, sel = panel_box(shot, seed, tb_top if spec.get('above_taskbar', True) else shot.H, base, spec.get('mask_tol', 0))
    x0, y0, x1, y1 = box
    p = spec['key']
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    fs = {'fullscreen': True} if mode == 'fullscreen' else {}   # the screen itself: not cross-checked
    out.add(shot, f'{p}.x', x0, (x0, cy), **fs)
    out.add(shot, f'{p}.y', y0, (cx, y0), **fs)
    out.add(shot, f'{p}.width', x1 - x0, (x0, cy), **fs)
    out.add(shot, f'{p}.height', y1 - y0, (cx, y0), **fs)
    out.add(shot, f'{p}.gap.taskbar', tb_top - y1, (cx, y1))
    out.add(shot, f'{p}.edge.left', x0, (x0, cy))
    out.add(shot, f'{p}.edge.right', shot.W - x1, (x1, cy))
    r, insets = corner_radius(sel, box)
    out.add(shot, f'{p}.radius', r, (x0, y0), insets=insets)
    fill = median_patch(shot, tuple(seed), 2)
    out.add(shot, f'{p}.background', hexc(fill), seed, reliable=False, note='acrylic over solid bg')
    out.add(shot, f'{p}.border', hexc(shot.px[cx, y0]), (cx, y0), reliable=False)
    n, depth = shadow_extent(shot, box)
    out.add(shot, f'{p}.shadow.extent', n, (x0 - 1, cy), reliable=False, depth=depth)
    for i, e in enumerate(elements(shot, box, fill, r)):
        b = e['box']
        out.add(shot, f'{p}.element[{i}]', {'x': b[0] - x0, 'y': b[1] - y0, 'w': b[2], 'h': b[3], 'color': e['color']},
                (b[0], b[1]))
    _BOX[shot.file] = (box, seed)
    if mode != 'fullscreen':
        for i, c in enumerate(controls(shot, box, fill, r)):
            b = c['box']
            out.add(shot, f'{p}.control[{i}]', {'x': b[0] - x0, 'y': b[1] - y0, 'w': b[2], 'h': b[3], 'color': c['color']},
                    (b[0], b[1]))
    for name, pt in spec.get('probes', {}).items():
        pt = [int(pt[0] * shot.scale) + x0, int(pt[1] * shot.scale) + y0]
        out.add(shot, f'{p}.{name}', hexc(shot.px[pt[0], pt[1]]), pt)
    for name, pt in shot.meta.get('probes', {}).items():
        out.add(shot, f'{p}.{name}', hexc(shot.px[pt[0], pt[1]]), pt)
    # the same numbers under design/tokens.json names (panels.json "tokens": {suffix: token})
    for suffix, token in spec.get('tokens', {}).items():
        src = next((e for e in reversed(out.entries) if e['key'] == f'{p}.{suffix}' and e['source'] == shot.file), None)
        if src and token != src['key']:
            out.entries.append(dict(src, key=token, measured_as=src['key']))
    return box


def measure_wallpaper(shot, out, spec):
    """Non-solid background: only the acrylic colour, sampled inside the box measured on the
    solid pass of the same capture (geometry is never read off a photo)."""
    spec = spec_for(shot, spec)
    if shot.file not in _BOX or not spec.get('key'):
        return False
    box, seed = _BOX[shot.file]
    p = spec['key']
    cx, cy = (box[0] + box[2]) // 2, box[1] + 8
    for name, pt in (('background.acrylic', seed), ('background.acrylic.top', (cx, cy))):
        out.add(shot, f'{p}.{name}', hexc(median_patch(shot, tuple(pt), 2)), pt, reliable=False,
                note='acrylic over fenestra-bloom-dark.jpg, VM render (no GPU)')
    return True


def motion_entries(d, panels_motion):
    """motion.py analyses -> motion.* keys (all reliable=false)."""
    ents = []
    for name, keys in panels_motion.items():
        f = os.path.join(d, name, 'analysis.json')
        if not os.path.exists(f):
            continue
        a = json.load(open(f))
        if 'duration_ms' not in a:
            continue
        settled = next((r for r in a['frames'] if r['t_ms'] == a['settled_ms']), None)
        src = f"motion/{name}/f{settled['frame']:03d}.png" if settled else f'motion/{name}'
        at = a['final_box'][:2]
        for k, field in keys.items():
            ents.append({'key': k, 'value': abs(a[field]), 'scale': 1.0, 'theme': 'dark', 'source': src, 'at': at,
                         'reliable': False, 'note': f"QMP screendump every ~{a['frame_interval_ms']} ms, no GPU; {name}"})
    return ents


# --- token probes --------------------------------------------------------------------------
# Values of design/tokens.json that are not a whole panel: read off one part of a capture
# (taskbar icons, search box, running indicators, Start grid, menu rows, quick tiles, calendar
# day, Alt+Tab thumbnail, title bar, text size). Each probe runs on every pass of its capture
# and the 4 passes are cross-checked like the panel boxes.

def diff_base(shot, x, y):
    base = _BASE.get((os.path.dirname(shot.path), shot.theme, shot.scale))
    if base is None:
        return max(abs(shot.px[x, y][i] - shot.bg[i]) for i in range(3))
    b = base.getpixel((x, y))
    return max(abs(shot.px[x, y][i] - b[i]) for i in range(3))


def entries_of(out, shot, prefix):
    return [e for e in out.entries if e['source'] == shot.file and e['key'].startswith(prefix)]


def probe_taskbar(shot, out):
    """Capture 01: icon size of the pinned apps and the taskbar search box."""
    s, top = shot.scale, _TB[(os.path.dirname(shot.path), shot.theme, shot.scale)]
    fill = median_patch(shot, (4, top + 6), 2)
    px = shot.px
    rows = range(top + 3, shot.H - 3)
    runs = runs_where(lambda x: any(not close(px[x, y], fill, 24) for y in rows), int(shot.W * 0.3), int(shot.W * 0.75))
    icons, boxrun = [], None
    for a, b in runs:
        ys = [y for y in rows if any(not close(px[x, y], fill, 24) for x in range(a, b))]
        if b - a > 100 * s:
            boxrun = (a, b)
        elif b - a <= 30 * s:
            icons.append((max(b - a, ys[-1] - ys[0] + 1), a, ys[0]))
    if icons:
        v, x, y = max(icons)
        out.add(shot, 'taskbar.icon', v, (x, y), note='lado mayor de los iconos anclados (Explorador, Bloc de notas, Paint)')
    if boxrun:
        cy = top + (shot.H - top) // 2
        seed = (int(boxrun[0] + 0.8 * (boxrun[1] - boxrun[0])), cy)
        box, _ = flat_region(shot, seed, tol=3, reach=(int(250 * s), int(30 * s)))
        x0, y0, x1, y1 = box
        # the 1 px border around the fill is part of the box
        while x0 > 0 and not close(px[x0 - 1, cy], fill, 2):
            x0 -= 1
        while x1 < shot.W and not close(px[x1, cy], fill, 2):
            x1 += 1
        mx = seed[0]
        while y0 > top and not close(px[mx, y0 - 1], fill, 2):
            y0 -= 1
        while y1 < shot.H and not close(px[mx, y1], fill, 2):
            y1 += 1
        out.add(shot, 'search.box.width', x1 - x0, (x0, cy), color=hexc(px[seed[0], seed[1]]))
        out.add(shot, 'search.box.height', y1 - y0, (mx, y0))


_BARS = {}


def probe_bars(shot, out):
    """Every capture with the taskbar: running indicators (thin bars under the icons) and the
    button plate (attention / hover background). Collected per pass, written by bars_entries."""
    s = shot.scale
    top = bar_top(shot)
    band = range(shot.H - int(12 * s), shot.H - 1)
    cols = [x for x in range(int(shot.W * 0.3), int(shot.W * 0.75)) if any(diff_base(shot, x, y) > 40 for y in band)]
    runs = runs_where(lambda x: x in cols_set, int(shot.W * 0.3), int(shot.W * 0.75), gap=1) if (cols_set := set(cols)) else []
    key = (shot.theme, s)
    for a, b in runs:
        ys = [y for y in band if any(diff_base(shot, x, y) > 40 for x in range(a, b))]
        if not ys:
            continue
        if ys[-1] - ys[0] + 1 <= 5 * s and ys[0] > band[0]:
            # thin bar: its colour is the most frequent strong difference (the pointer may cover
            # part of it); a pixel belongs to the bar when it is closer to that colour than to the
            # bar background (half coverage at the antialiased ends)
            cnt = {}
            for x in range(a, b):
                for y in ys:
                    if diff_base(shot, x, y) > 40:
                        cnt[shot.px[x, y]] = cnt.get(shot.px[x, y], 0) + 1
            c = max(cnt, key=cnt.get)
            bg = median_patch(shot, (a - int(4 * s), ys[0] + 1), 1)

            def on(x, y):
                q = shot.px[x, y]
                return sum((q[i] - c[i]) ** 2 for i in range(3)) < sum((q[i] - bg[i]) ** 2 for i in range(3))
            row = max(ys, key=lambda y: sum(1 for x in range(a, b) if shot.px[x, y] == c))
            col = max(range(a, b), key=lambda x: sum(1 for y in ys if shot.px[x, y] == c))
            w = sum(1 for x in range(a - 2, b + 2) if on(x, row))
            h = sum(1 for y in range(ys[0] - 2, ys[-1] + 3) if on(col, y))
            sat = max(c) - min(c)
            kind = 'unfocused' if sat <= 60 else ('focused' if c[2] > c[0] else 'attention')
            _BARS.setdefault(key, {}).setdefault(kind, []).append((w, h, shot, (a, ys[0]), hexc(c)))
        elif 30 * s <= b - a <= 70 * s and len(ys := [y for y in range(top + 1, shot.H)
                                                      if any(diff_base(shot, x, y) > 40 for x in range(a, b))]) >= 30 * s:
            # button plate (attention or hover background): flat colour along its left margin,
            # clearly unlike the bar (other icons shifting under a different layout do not count)
            fill = median_patch(shot, (4, top + int(6 * s)), 2)
            xx = a + int(6 * s)
            cnt = {}
            for y in ys:
                cnt[shot.px[xx, y]] = cnt.get(shot.px[xx, y], 0) + 1
            c = max(cnt, key=cnt.get)
            if max(abs(c[i] - fill[i]) for i in range(3)) <= 20:
                continue

            def onp(x, y):
                q = shot.px[x, y]
                return sum((q[i] - c[i]) ** 2 for i in range(3)) < sum((q[i] - fill[i]) ** 2 for i in range(3))
            midy = (ys[0] + ys[-1]) // 2
            w = sum(1 for x in range(a - 3, b + 3) if onp(x, midy) or (a <= x < b and not close(shot.px[x, midy], fill, 30)))
            h = sum(1 for y in range(top + 1, shot.H) if onp(xx, y))
            _BARS.setdefault(key, {}).setdefault('plate', []).append((w, h, shot, (a, ys[0]), hexc(c)))


def bars_entries(out):
    def mode(v):
        return max(set(v), key=v.count)
    for (theme, s), kinds in _BARS.items():
        for kind, items in kinds.items():
            w = mode([i[0] for i in items])
            h = mode([i[1] for i in items])
            src = next(i for i in items if i[0] == w and i[1] == h) if any(i[0] == w and i[1] == h for i in items) else next(i for i in items if i[0] == w)
            n = sum(1 for i in items if i[0] == w)
            note = f'moda de {n} de {len(items)} capturas de la pasada'
            if kind == 'plate':
                out.add(src[2], 'taskbar.button', w, src[3], color=src[4], note=note + '; fondo del botón (atención / hover), no la separación entre iconos')
                out.add(src[2], 'taskbar.button.height', h, src[3], note=note)
            else:
                out.add(src[2], f'taskbar.indicator.{kind}', w, src[3], color=src[4], note=note)
                out.add(src[2], f'taskbar.indicator.height.{kind}', h, src[3], note=note)
                if kind == 'unfocused':
                    out.add(src[2], 'taskbar.indicator.height', h, src[3], note=note)


def ink_components(shot, rect, fill):
    """Connected components of 'ink' (at least half-way from the fill to the strongest pixel) in rect."""
    x0, y0, w, h = rect
    peak = max(max(abs(shot.px[x, y][i] - fill[i]) for i in range(3)) for x in range(x0, x0 + w) for y in range(y0, y0 + h))
    m = Image.new('L', (w, h), 0)
    mp = m.load()
    for y in range(h):
        for x in range(w):
            if max(abs(shot.px[x0 + x, y0 + y][i] - fill[i]) for i in range(3)) >= peak / 2:
                mp[x, y] = 255
    comps = []
    for y in range(h):
        for x in range(w):
            if mp[x, y] == 255:
                ImageDraw.floodfill(m, (x, y), 100)
                bb = m.point(lambda v: 255 if v == 100 else 0).getbbox()
                ImageDraw.floodfill(m, (x, y), 50)
                comps.append((bb[0] + x0, bb[1] + y0, bb[2] - bb[0], bb[3] - bb[1]))
    return sorted(comps)


CAP_HEIGHT = 0.70   # Segoe UI / Segoe UI Variable: capHeight 1434 / unitsPerEm 2048


def font_size(shot, out, key, word, fill, what):
    """Text size from the height of the first capital of a word (flat-topped: B, M, ...)."""
    comps = ink_components(shot, (word['X'], word['Y'], word['w'], word['h']), fill)
    if not comps:
        return
    c = comps[0]
    px_size = c[3] / CAP_HEIGHT
    out.add(shot, key, round(px_size), (c[0], c[1]), cap_height=c[3], estimate=round(px_size, 2),
            note=f'{what}: altura de la mayúscula / {CAP_HEIGHT} (capHeight de Segoe UI); el peso no se mide')


def elements_of(out, shot, p, box):
    return [dict(e['value'], X=e['value']['x'] + box[0], Y=e['value']['y'] + box[1])
            for e in entries_of(out, shot, f'{p}.element[')]


def rows_of(items, tol):
    rows = []
    for it in sorted(items, key=lambda e: e['Y'] + e['h'] / 2):
        cy = it['Y'] + it['h'] / 2
        if rows and abs(rows[-1][0] - cy) <= tol:
            rows[-1][1].append(it)
        else:
            rows.append([cy, [it]])
    return rows


def median(v):
    v = sorted(v)
    return v[len(v) // 2]


def probe_start(shot, out):
    """Capture 06: pinned grid (columns, pitch), footer height, caption text size (tile label)."""
    (x0, y0, x1, y1), seed = _BOX[shot.file]
    s = shot.scale
    els = elements_of(out, shot, 'start', (x0, y0))
    icons = [e for e in els if 26 * s <= e['w'] <= 38 * s and 26 * s <= e['h'] <= 38 * s and e['Y'] < y0 + (y1 - y0) / 2]
    rows = [r for r in rows_of(icons, 6 * s) if len(r[1]) >= 3]
    if rows:
        cols = max(len(r[1]) for r in rows)
        r0 = sorted(rows[0][1], key=lambda e: e['X'])
        pitch_x = median([(b['X'] + b['w'] / 2) - (a['X'] + a['w'] / 2) for a, b in zip(r0, r0[1:])])
        out.add(shot, 'start.pinned.columns', cols, (r0[0]['X'], r0[0]['Y']), note='iconos por fila en Anclado')
        out.add(shot, 'start.pinned.pitch.x', round(pitch_x), (r0[0]['X'], r0[0]['Y']), note='distancia entre centros de iconos')
        out.add(shot, 'start.pinned.tile.width', round(pitch_x), (r0[0]['X'], r0[0]['Y']), reliable=False,
                note='sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso horizontal de la rejilla')
        if len(rows) >= 2:
            pitch_y = rows[1][0] - rows[0][0]
            out.add(shot, 'start.pinned.pitch.y', round(pitch_y), (r0[0]['X'], r0[0]['Y']), note='distancia entre filas de iconos')
            out.add(shot, 'start.pinned.tile.height', round(pitch_y), (r0[0]['X'], r0[0]['Y']), reliable=False,
                    note='sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso vertical de la rejilla')
        # tile label under the first icon: caption text size
        ic = r0[0]
        lab = [e for e in els if e['Y'] > ic['Y'] + ic['h'] and e['Y'] < ic['Y'] + ic['h'] + 20 * s
               and e['X'] < ic['X'] + ic['w'] and e['X'] + e['w'] > ic['X']]
        if lab:
            font_size(shot, out, 'font.caption', min(lab, key=lambda e: e['Y']), median_patch(shot, tuple(seed), 2),
                      'etiqueta de icono anclado de Inicio')
    footer_height(shot, out, 'start.footer.height')


def probe_quick(shot, out):
    """Capture 12: toggle tiles = the flat buttons of the grid (mode of the control boxes)."""
    s = shot.scale
    ctl = [e for e in entries_of(out, shot, 'quick.control[')]
    sizes = [(e['value']['w'], e['value']['h']) for e in ctl
             if 70 * s <= e['value']['w'] <= 130 * s and 36 * s <= e['value']['h'] <= 60 * s]
    if not sizes:
        return
    w, h = max(set(sizes), key=sizes.count)
    e = next(e for e in ctl if (e['value']['w'], e['value']['h']) == (w, h))
    note = f'moda de {sizes.count((w, h))} botones de {len(sizes)}'
    out.add(shot, 'quick.tile.width', w, e['at'], color=e['value']['color'], note=note)
    out.add(shot, 'quick.tile.height', h, e['at'], note=note)
    footer_height(shot, out, 'quick.footer.height')


def footer_height(shot, out, key):
    """Strip of another colour along the bottom edge of the panel (Start, Quick Settings)."""
    (x0, y0, x1, y1), _ = _BOX[shot.file]
    fx = x0 + int(20 * shot.scale)
    c = shot.px[fx, y1 - 3]
    y = y1 - 3
    while y > y0 and close(shot.px[fx, y - 1], c, 2):
        y -= 1
    out.add(shot, key, (y1 - 1) - y, (fx, y), color=hexc(c), note='sin el borde exterior de 1 px')


def accent_blob(shot, box):
    """Largest connected area of strongly coloured pixels inside box (today, selected card)."""
    x0, y0, x1, y1 = box
    m = Image.new('L', (x1 - x0, y1 - y0), 0)
    mp = m.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            c = shot.px[x, y]
            if max(c) - min(c) > 80 and c[2] > c[0]:
                mp[x - x0, y - y0] = 255
    best = None
    for y in range(0, y1 - y0, 2):
        for x in range(0, x1 - x0, 2):
            if mp[x, y] == 255:
                ImageDraw.floodfill(m, (x, y), 100)
                part = m.point(lambda v: 255 if v == 100 else 0)
                bb, area = part.getbbox(), part.histogram()[255]
                ImageDraw.floodfill(m, (x, y), 50)
                if best is None or area > best[1]:
                    best = (bb, area)
    if not best:
        return None
    bb = best[0]
    return (bb[0] + x0, bb[1] + y0, bb[2] + x0, bb[3] + y0)


def probe_calendar(shot, out):
    """Capture 16: the day button = today's accent circle."""
    (x0, y0, x1, y1), _ = _BOX[shot.file]
    b = accent_blob(shot, (x0, y0, x1, y1))
    if b:
        out.add(shot, 'calendar.day', b[2] - b[0], (b[0], b[1]), height=b[3] - b[1], color=hexc(shot.px[b[0] + (b[2] - b[0]) // 2, b[1] + 2]),
                note='diámetro del círculo de hoy')


def probe_menu(shot, out):
    """Capture 08 (power menu): row pitch of the items (no separators between them) and body text size."""
    (x0, y0, x1, y1), seed = _BOX[shot.file]
    s = shot.scale
    els = elements_of(out, shot, 'menu.power', (x0, y0))
    left = [e for e in els if e['X'] < x0 + 40 * s and e['w'] <= 24 * s]
    rows = rows_of(left, 4 * s)
    if len(rows) >= 2:
        pitch = median([b[0] - a[0] for a, b in zip(rows, rows[1:])])
        out.add(shot, 'menu.item.height', round(pitch), (left[0]['X'], left[0]['Y']),
                note=f'distancia entre filas de {len(rows)} elementos del menú de apagado (sin separadores)')
    words = sorted((e for e in els if e['X'] >= x0 + 40 * s), key=lambda e: e['Y'])
    if words:
        font_size(shot, out, 'font.body', words[0], median_patch(shot, tuple(seed), 2), 'primer elemento del menú de apagado')


def probe_alttab(shot, out):
    """Capture 25: thumbnail height = window image inside the selected (outlined) card.

    The card is the title strip (flat colour) over the thumbnail, inset from the accent outline
    by the same margin on every side; the margin is read on the left at the title strip's row."""
    (x0, y0, x1, y1), seed = _BOX[shot.file]
    b = accent_blob(shot, (x0, y0, x1, y1))
    if not b:
        return
    s = shot.scale
    x, ty = b[2] - int(30 * s), b[1] + int(20 * s)
    fill = shot.px[x, ty]                                   # title strip colour
    run = int(6 * s)   # the dark ring next to the outline has the title colour too, but is narrower
    off = next(xx for xx in range(b[0], b[0] + int(40 * s))
               if all(close(shot.px[xx + k, ty], fill, 3) for k in range(run))) - b[0]
    y = ty
    while y < b[3] and close(shot.px[x, y], fill, 3):
        y += 1
    top = y
    bottom = b[3] - off
    out.add(shot, 'switcher.thumbnail.height', bottom - top, (x, top), card_height=bottom - (b[1] + off),
            card_width=(b[2] - off) - (b[0] + off),
            title_strip=top - (b[1] + off), color=hexc(fill),
            note='imagen de la ventana dentro de la tarjeta seleccionada (sin la tira del título); depende de la proporción de la ventana')


def probe_title(shot, out, spec):
    """panels.json "title": a Win32 window visible in this capture: rows from its outer top edge
    to the first row of the client area, read down a column."""
    x, y = spec['at']
    c = shot.px[x, y]
    top = y
    while top > 0 and close(shot.px[x, top - 1], c, 2):
        top -= 1
    bot = y
    while bot < shot.H - 1 and close(shot.px[x, bot + 1], c, 2):
        bot += 1
    # outer border above the strip, a separator row below it
    edge = top - 1 if not close(shot.px[x, top - 1], shot.bg, 2) else top
    client = bot + 1
    while client < shot.H - 1 and not close(shot.px[x, client], shot.px[x, client + 3], 2):
        client += 1
    out.add(shot, 'window.title.height', client - edge, (x, edge), fill_rows=bot + 1 - top, color=hexc(c),
            note=spec.get('note', ''))


PROBES = {'01': [probe_taskbar], '06': [probe_start], '08': [probe_menu], '12': [probe_quick],
          '16': [probe_calendar], '25': [probe_alttab]}


GEOM = re.compile(r'(\.(x|y|width|height|radius|gap\.taskbar|edge\.left|edge\.right)|^taskbar\.(height|button)|'
                  r'^flyout\.(gap|edge|radius)|^(start|search|quick|notifications|toast|osd)\.(width|height)|'
                  r'^menu\.width\.min|^window\.button\.(width|height))$')
# token probes: compared with a tighter tolerance (small values) and, for the taskbar bars
# (the mode over every capture of a pass), across passes whatever capture they came from
TOKEN = re.compile(r'^(taskbar\.(icon|button|button\.height|indicator\..*)|search\.box\.(width|height)|start\.pinned\..*|'
                   r'start\.footer\.height|quick\.tile\.(width|height)|menu\.item\.height|calendar\.day|'
                   r'switcher\.thumbnail\.height|window\.title\.height)$')
BY_KEY = re.compile(r'^taskbar\.(button|button\.height|indicator\..*)$')
SCALE_FREE = {'start.pinned.columns'}
POS = re.compile(r'\.(x|y|edge\.left|edge\.right)$')


def add_note(e, note):
    e['note'] = f"{e['note']}; {note}" if e.get('note') else note


def font_consensus(entries):
    """Text size from cap heights in every pass: the sizes n (px at scale 1) whose rendered cap
    height round(n * CAP_HEIGHT * scale) can give each measured cap height (within 0.6 px, for
    hinting). One candidate left = reliable; none or several = not reliable."""
    groups = {}
    for e in entries:
        if e['key'].startswith('font.') and 'cap_height' in e:
            groups.setdefault(e['key'], []).append(e)
    for key, g in groups.items():
        cands = [n for n in range(6, 40) if all(abs(n * CAP_HEIGHT * e['scale'] - e['cap_height']) <= 0.6 for e in g)]
        caps = ', '.join(f"{e['cap_height']} px al {int(e['scale'] * 100)} %" for e in g)
        for e in g:
            if len(cands) == 1:
                e['value'] = round(cands[0] * e['scale'])
                e['reliable'] = e['reliable'] and True
                add_note(e, f'único tamaño compatible con las {len(g)} pasadas ({caps}): {cands[0]} px a escala 1')
            else:
                e['reliable'] = False
                add_note(e, f'tamaños compatibles con las pasadas ({caps}): {cands or "ninguno"}')


def cross_check(entries):
    """The same panel is captured in 4 passes (dark/light x 100/150 %). A geometry value that,
    divided by its scale, is off the median of the others by more than max(2 px, 4 %) (token
    probes: max(1 px, 4 %)) is kept but marked reliable=false: a wrong seed or a stray window,
    not a design difference. A panel height at 150 % that reaches the top of the screen is
    limited by the screen, not wrong: it is still marked, with that reason."""
    groups = {}
    idx = {(e['source'], e['key']): e for e in entries}
    for e in entries:
        if not isinstance(e['value'], (int, float)) or isinstance(e['value'], bool):
            continue
        tok = bool(TOKEN.search(e['key']))
        if not (tok or GEOM.search(e['key'])) or e.get('measured_as') or e.get('fullscreen'):
            continue
        stem = '*' if BY_KEY.search(e['key']) else e['source'].split('-', 2)[2]  # NN-name.png without theme/pct
        # positions of centred / pointer-anchored panels do not scale: compared within one scale only
        sc = e['scale'] if POS.search(e['key']) else None
        groups.setdefault((e['key'], stem, sc), []).append(e)
    for (key, _, _), g in groups.items():
        tok = bool(TOKEN.search(key))
        norm = lambda e: e['value'] if key in SCALE_FREE else e['value'] / e['scale']
        tol = lambda v: max(1 if tok else 2, 0.04 * abs(v))
        if len(g) == 1:
            if tok:
                add_note(g[0], 'una sola pasada: sin comprobación cruzada')
            continue
        if len(g) == 2:
            a_, b_ = (norm(e) for e in g)
            if abs(a_ - b_) > tol(max(abs(a_), abs(b_))):
                for e in g:
                    e['reliable'] = False
                    add_note(e, f'solo dos pasadas y no coinciden ({a_:g} / {b_:g} px a escala 1)')
            continue
        vals = sorted(norm(e) for e in g)
        med = vals[len(vals) // 2]
        for e in g:
            if abs(norm(e) - med) > tol(med):
                e['reliable'] = False
                y = idx.get((e['source'], key[:-len('height')] + 'y')) if key.endswith('.height') else None
                if y is not None and e['scale'] > 1 and y['value'] <= 16 * e['scale']:
                    add_note(e, f'limitado por la altura de la pantalla al {int(e["scale"] * 100)} % (mediana {med:g} px a escala 1)')
                else:
                    add_note(e, f'no cuadra con las otras pasadas (mediana {med:g} px a escala 1)')
    # the token aliases (measured_as) follow the panel value they copy
    for e in entries:
        if e.get('measured_as'):
            src = idx.get((e['source'], e['measured_as']))
            if src:
                e['reliable'], e['note'] = src['reliable'], src.get('note')
                if e['note'] is None:
                    del e['note']


OWN_KEYS = ('_comment', 'not_measured', 'skipped', 'entries')


def write_merged(path, doc):
    """Replace only this script's top-level keys in PATH. Other tools (the dialog measurements:
    file_dialog_*, print_dialog*, snip_*) add their own sections to the same file, so the file is
    re-read right before writing and every key this script does not produce is kept as it is.
    Written to a temporary file and renamed, so a reader never sees half a file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    try:
        with open(path) as fh:
            old = json.load(fh)
        if not isinstance(old, dict):
            old = {}
    except (OSError, ValueError):
        old = {}
    merged = {k: doc[k] for k in OWN_KEYS if k in doc}
    merged.update({k: v for k, v in old.items() if k not in OWN_KEYS})
    tmp = f'{path}.tmp{os.getpid()}'
    with open(tmp, 'w') as fh:
        json.dump(merged, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    os.replace(tmp, path)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shots', nargs='+', help='solid-background dir first, then wallpaper dirs')
    ap.add_argument('-o', '--out', default=os.path.join(repo, 'design/reference/measurements.json'))
    ap.add_argument('--panels', default=os.path.join(here, 'panels.json'))
    ap.add_argument('--motion', help='~/fenestra-ref/motion')
    ap.add_argument('--only', help='regex on file names')
    a = ap.parse_args()
    panels = json.load(open(a.panels))
    exclude = panels.get('exclude', {})
    out = Out()
    skipped, not_measured = [], []
    for d in a.shots:
        for f in sorted(os.listdir(d)):
            if not NAME.match(f) or (a.only and not re.search(a.only, f)):
                continue
            why = next((r for pat, r in exclude.items() if re.search(pat, f)), None)
            if why:
                not_measured.append({'source': f, 'reason': why})
                if d != a.shots[0] or not panels.get(f.split('-')[2], {}).get('bars', True):
                    continue
                # the panel is not there, but the taskbar is: its indicators still count
                shot = Shot(os.path.join(d, f))
                try:
                    probe_bars(shot, out)
                except (ValueError, StopIteration) as e:
                    skipped.append(f'{f}: {e}')
                continue
            shot = Shot(os.path.join(d, f))
            spec = panels.get(shot.num)
            if not spec:
                skipped.append(f'{f}: no entry {shot.num} in panels.json')
                continue
            try:
                if not shot.solid:
                    if not measure_wallpaper(shot, out, spec):
                        skipped.append(f'{f}: no solid-pass box to sample')
                    continue
                tb = measure_taskbar(shot, out, spec) if shot.num == '01' else bar_top(shot)
                if spec.get('key') and shot.num != '01':
                    measure_panel(shot, out, spec, tb)
                if spec.get('bars', True):
                    probe_bars(shot, out)
                for probe in PROBES.get(shot.num, []):
                    if spec_for(shot, spec).get('probe', True):
                        probe(shot, out)
            except (ValueError, StopIteration) as e:
                skipped.append(f'{f}: {e}')
            print(f'{f}: ok', file=sys.stderr)
    bars_entries(out)
    font_consensus(out.entries)
    for pr in panels.get('probes', []):
        f = os.path.join(a.shots[0], pr['source'])
        if os.path.exists(f) and not (a.only and not re.search(a.only, pr['source'])):
            {'title': probe_title}[pr['probe']](Shot(f), out, pr)
    for num, why in panels.get('missing', {}).items():
        not_measured.append({'panel': num, 'name': panels.get(num, {}).get('name'), 'reason': why})
    for f, why in panels.get('unmeasured_tokens', {}).items():
        not_measured.append({'token': f, 'reason': why})
    cross_check(out.entries)
    if a.motion:
        out.entries += motion_entries(a.motion, panels.get('motion', {}))
    doc = {'_comment': ['Measured on Windows 11 Enterprise Evaluation (build 26100, es-ES) in a QEMU/KVM VM by tests/visual/measure.py.',
                        'Keys follow design/tokens.json where one exists (measured_as = the panel key it was read from).',
                        'reliable=false: VM render (acrylic, shadow, motion) or a non-solid background.',
                        'source = screenshot in reference-shots/<pass>/ of the visual/screenshots branch (never in this branch); at = pixel it was read at.',
                        'Other top-level sections (file_dialog_*, print_dialog*, snip_*) come from the dialog measurements and are kept as they are.'],
           'not_measured': not_measured, 'skipped': skipped, 'entries': out.entries}
    write_merged(a.out, doc)
    print(f'{len(out.entries)} entries -> {a.out}; skipped {len(skipped)}, not measured {len(not_measured)}', file=sys.stderr)


if __name__ == '__main__':
    main()

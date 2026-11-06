#!/usr/bin/env python3
"""Measure shell panels in reference screenshots and write design/reference/measurements.json.

    tests/visual/measure.py SHOTS_DIR [-o design/reference/measurements.json] [--panels tests/visual/panels.json]

SHOTS_DIR holds PNGs named <theme>-<pct>-<NN>-<name>.png (dark-100-06-start.png) and, next to
each one, an optional <same>.json sidecar written by the capture script:
    {"seed": [x, y], "bg": "#1f1f1f", "wallpaper": "solid", "hover": [x, y], "note": "..."}
Screenshots never enter the repo: only this script and the numbers it prints.

Geometry is measured only on the solid-background pass (wallpaper "solid"): the panel is the
connected region around the seed whose luminance differs from the known background, so
shadows (darker than the background) and the background itself fall outside it. Anything
that depends on acrylic, mica, shadows or animation is written with "reliable": false.
Every value carries the screenshot it comes from and the pixel it was read at.
"""
import argparse
import json
import os
import re
import sys
from collections import deque

from PIL import Image, ImageDraw

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
    # the border line makes two edges (above and below it): the bar starts at the upper one
    return min(y for y, d in ds.items() if d >= 0.5 * peak)


def measure_taskbar(shot, out, spec):
    top = taskbar_top(shot)
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


def panel_mask(shot, limit_y):
    """1 where the pixel is lighter than the solid background (panel), 0 for background/shadow."""
    bl = lum(shot.bg)
    m = Image.new('L', (shot.W, shot.H), 0)
    mp = m.load()
    px = shot.px
    for y in range(limit_y):
        for x in range(shot.W):
            c = px[x, y]
            if lum(c) > bl + 3 or max(abs(c[i] - shot.bg[i]) for i in range(3)) > 10 and lum(c) >= bl:
                mp[x, y] = 255
    return m


def panel_box(shot, seed, limit_y):
    m = panel_mask(shot, limit_y)
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


def measure_panel(shot, out, spec, tb_top):
    # seed: a pixel inside the panel; the sidecar wins, else panels.json (100 % coords, y from the bottom)
    if 'seed' in shot.meta:
        seed = shot.meta['seed']
    else:
        sx, sy = spec['seed']
        seed = [shot.W // 2 if sx == 'center' else int(sx * shot.scale), shot.H - int(sy * shot.scale)]
    mode = spec.get('mode', 'panel')
    if mode == 'fullscreen':
        box = (0, 0, shot.W, shot.H)
        sel = Image.new('L', (shot.W, shot.H), 255)
    elif mode == 'region':
        # a flat-coloured area around the seed (hover highlight, caption button), any background
        sel = Image.new('L', (shot.W, shot.H), 0)
        ref = shot.px[seed[0], seed[1]]
        sp = sel.load()
        for y in range(max(0, seed[1] - 120), min(shot.H, seed[1] + 120)):
            for x in range(max(0, seed[0] - 200), min(shot.W, seed[0] + 200)):
                if close(shot.px[x, y], ref, 4):
                    sp[x, y] = 255
        ImageDraw.floodfill(sel, tuple(seed), 128)
        sel = sel.point(lambda v: 255 if v == 128 else 0)
        box = sel.getbbox()
    else:
        box, sel = panel_box(shot, seed, tb_top if spec.get('above_taskbar', True) else shot.H)
    x0, y0, x1, y1 = box
    p = spec['key']
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    out.add(shot, f'{p}.x', x0, (x0, cy))
    out.add(shot, f'{p}.y', y0, (cx, y0))
    out.add(shot, f'{p}.width', x1 - x0, (x0, cy))
    out.add(shot, f'{p}.height', y1 - y0, (cx, y0))
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
    for name, pt in spec.get('probes', {}).items():
        pt = [int(pt[0] * shot.scale) + x0, int(pt[1] * shot.scale) + y0]
        out.add(shot, f'{p}.{name}', hexc(shot.px[pt[0], pt[1]]), pt)
    for name, pt in shot.meta.get('probes', {}).items():
        out.add(shot, f'{p}.{name}', hexc(shot.px[pt[0], pt[1]]), pt)
    return box


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shots')
    ap.add_argument('-o', '--out', default=os.path.join(repo, 'design/reference/measurements.json'))
    ap.add_argument('--panels', default=os.path.join(here, 'panels.json'))
    ap.add_argument('--only', help='regex on file names')
    a = ap.parse_args()
    panels = json.load(open(a.panels))
    out = Out()
    skipped = []
    for f in sorted(os.listdir(a.shots)):
        if not NAME.match(f) or (a.only and not re.search(a.only, f)):
            continue
        shot = Shot(os.path.join(a.shots, f))
        spec = panels.get(shot.num)
        if not spec:
            skipped.append(f'{f}: no entry {shot.num} in panels.json')
            continue
        try:
            tb = measure_taskbar(shot, out, spec) if shot.num == '01' else taskbar_top(shot)
            if spec.get('key') and shot.num != '01':
                measure_panel(shot, out, spec, tb)
        except ValueError as e:
            skipped.append(str(e))
        print(f'{f}: ok', file=sys.stderr)
    doc = {'_comment': ['Measured on Windows 11 Enterprise Evaluation in a QEMU/KVM VM by tests/visual/measure.py.',
                        'Keys follow design/tokens.json; reliable=false: VM render (acrylic, shadow, motion) or non-solid background.',
                        'Screenshots stay outside the repo (~/fenestra-ref).'],
           'skipped': skipped, 'entries': out.entries}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    print(f'{len(out.entries)} entries -> {a.out}; skipped {len(skipped)}', file=sys.stderr)


if __name__ == '__main__':
    main()

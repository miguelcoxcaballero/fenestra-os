#!/usr/bin/env python3
"""Compare Fenestra Shell screenshots with the Windows 11 reference, panel by panel.

    tests/visual/compare.py REF_SHOTS FENESTRA_SHOTS [-o ~/fenestra-ref/compare] [--md table.md]

Both directories use the same names (dark-100-06-start.png) and sidecars as measure.py.
For every panel found in both, the panel boxes are measured, the crops are aligned on the
box's top-left corner and three images are written OUTSIDE the repo:
    <name>-diff.png     per-pixel difference (black = equal, red -> yellow = larger)
    <name>-overlay.png  50 % blend of both crops
    <name>-pair.png     reference | fenestra side by side
plus compare.json (all mismatching measurements) and, with --md, a Markdown table that
docs/fenestra-shell/VISUAL.md quotes. Only numbers go to the repo.
"""
import argparse
import json
import os
import re
import sys

from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure  # noqa: E402

PX_TOL = 1          # px: values within this are a match
COLOR_TOL = 3.0     # % of mean channel difference


def measure_dir(d, panels, only=None):
    out = measure.Out()
    boxes = {}
    for f in sorted(os.listdir(d)):
        if not measure.NAME.match(f) or (only and only not in f):
            continue
        why = next((r for pat, r in panels.get('exclude', {}).items() if re.search(pat, f)), None)
        if why:
            continue        # the capture does not show the panel (reason in measurements.json)
        shot = measure.Shot(os.path.join(d, f))
        spec = panels.get(shot.num)
        if not spec:
            continue
        try:
            if shot.num == '01':
                tb = measure.measure_taskbar(shot, out, spec)
                boxes[f] = (shot, (0, tb, shot.W, shot.H))
            elif spec.get('key'):
                tb = measure.bar_top(shot)
                boxes[f] = (shot, measure.measure_panel(shot, out, spec, tb))
        except ValueError as e:
            print(f'skip {e}', file=sys.stderr)
    return out.entries, boxes


def color_delta(a, b):
    a, b = measure.parse_hex(a), measure.parse_hex(b)
    return round(sum(abs(a[i] - b[i]) for i in range(3)) / 3 / 255 * 100, 1)


def heat(diff):
    """Max-channel difference -> black/red/yellow heatmap."""
    g = diff.convert('RGB').split()
    m = ImageChops.lighter(ImageChops.lighter(g[0], g[1]), g[2])
    m = m.point(lambda v: min(255, v * 4))
    r = m
    gg = m.point(lambda v: max(0, v * 2 - 255))
    return Image.merge('RGB', (r, gg, Image.new('L', m.size, 0))), m


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ref')
    ap.add_argument('fen')
    ap.add_argument('-o', '--out', default=os.path.expanduser('~/fenestra-ref/compare'))
    ap.add_argument('--panels', default=os.path.join(here, 'panels.json'))
    ap.add_argument('--md', help='write the per-panel Markdown table here')
    ap.add_argument('--only')
    a = ap.parse_args()
    repo = os.path.realpath(os.path.join(here, '..', '..'))
    if os.path.realpath(a.out).startswith(repo + os.sep):
        sys.exit('refusing to write comparison images inside the repo')
    os.makedirs(a.out, exist_ok=True)
    panels = json.load(open(a.panels))
    ref_e, ref_b = measure_dir(a.ref, panels, a.only)
    fen_e, fen_b = measure_dir(a.fen, panels, a.only)

    fen_idx = {(e['source'], e['key']): e for e in fen_e}
    mism = []
    for e in ref_e:
        f = fen_idx.get((e['source'], e['key']))
        if f is None:
            mism.append({'source': e['source'], 'key': e['key'], 'windows': e['value'], 'fenestra': None,
                         'reliable': e['reliable']})
            continue
        v, w = e['value'], f['value']
        if isinstance(v, (int, float)) and isinstance(w, (int, float)):
            if abs(v - w) > PX_TOL:
                mism.append({'source': e['source'], 'key': e['key'], 'windows': v, 'fenestra': w,
                             'delta_px': w - v, 'at': e['at'], 'reliable': e['reliable']})
        elif isinstance(v, dict) and isinstance(w, dict):
            dpx = max(abs(v[k] - w[k]) for k in ('x', 'y', 'w', 'h'))
            dc = color_delta(v['color'], w['color'])
            if dpx > PX_TOL or dc > COLOR_TOL:
                mism.append({'source': e['source'], 'key': e['key'], 'windows': v, 'fenestra': w,
                             'delta_px': dpx, 'delta_color_pct': dc, 'at': e['at'], 'reliable': e['reliable']})
        elif isinstance(v, str) and v.startswith('#') and isinstance(w, str) and w.startswith('#'):
            d = color_delta(v, w)
            if d > COLOR_TOL:
                mism.append({'source': e['source'], 'key': e['key'], 'windows': v, 'fenestra': w,
                             'delta_color_pct': d, 'at': e['at'], 'reliable': e['reliable']})

    rows = []
    for name in sorted(set(ref_b) & set(fen_b)):
        (rs, rb), (fs, fb) = ref_b[name], fen_b[name]
        w, h = max(rb[2] - rb[0], fb[2] - fb[0]), max(rb[3] - rb[1], fb[3] - fb[1])
        rc = rs.im.crop((rb[0], rb[1], rb[0] + w, rb[1] + h))
        fc = fs.im.crop((fb[0], fb[1], fb[0] + w, fb[1] + h))
        hm, mag = heat(ImageChops.difference(rc, fc))
        stem = os.path.join(a.out, name[:-4])
        hm.save(stem + '-diff.png')
        Image.blend(rc, fc, 0.5).save(stem + '-overlay.png')
        pair = Image.new('RGB', (w * 2 + 8, h), (255, 0, 255))
        pair.paste(rc, (0, 0))
        pair.paste(fc, (w + 8, 0))
        pair.save(stem + '-pair.png')
        hist = mag.histogram()
        changed = sum(hist[64:]) / (w * h) * 100  # >16 levels (x4 scaling in heat)
        mean = sum(i * n for i, n in enumerate(hist)) / 4 / (w * h) / 255 * 100
        n_bad = sum(1 for m in mism if m['source'] == name)
        n_unrel = sum(1 for m in mism if m['source'] == name and not m['reliable'])
        rows.append({'source': name, 'windows_box': [rb[0], rb[1], rb[2] - rb[0], rb[3] - rb[1]],
                     'fenestra_box': [fb[0], fb[1], fb[2] - fb[0], fb[3] - fb[1]],
                     'dx': fb[0] - rb[0], 'dy': fb[1] - rb[1],
                     'dw': (fb[2] - fb[0]) - (rb[2] - rb[0]), 'dh': (fb[3] - fb[1]) - (rb[3] - rb[1]),
                     'pixels_changed_pct': round(changed, 1), 'mean_color_diff_pct': round(mean, 1),
                     'mismatches': n_bad, 'mismatches_unreliable': n_unrel})
    missing = sorted(set(ref_b) - set(fen_b))
    with open(os.path.join(a.out, 'compare.json'), 'w') as fh:
        json.dump({'panels': rows, 'missing_in_fenestra': missing, 'mismatches': mism}, fh, indent=1)
    if a.md:
        with open(a.md, 'w') as fh:
            fh.write('| Captura | Caja Windows (x,y,w,h) | Δx | Δy | Δw | Δh | Píxeles distintos | Dif. color media | Medidas que no coinciden (no fiables) |\n')
            fh.write('|---|---|---|---|---|---|---|---|---|\n')
            for r in rows:
                fh.write(f"| {r['source']} | {','.join(map(str, r['windows_box']))} | {r['dx']} | {r['dy']} | {r['dw']} | {r['dh']} "
                         f"| {r['pixels_changed_pct']} % | {r['mean_color_diff_pct']} % | {r['mismatches']} ({r['mismatches_unreliable']}) |\n")
            for m in missing:
                fh.write(f'| {m} | — | | | | | sin captura de Fenestra | | |\n')
    print(f'{len(rows)} panels compared, {len(mism)} mismatching measurements, {len(missing)} missing -> {a.out}',
          file=sys.stderr)


if __name__ == '__main__':
    main()

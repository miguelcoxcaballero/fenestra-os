#!/usr/bin/env python3
"""Turn the headless KWin bench output (tests/shell-kwin/build.sh, OUT dir) into Fenestra
screenshots named like the Windows reference, recomposed over the same solid #1f1f1f
background so measure.py and compare.py treat both sides alike.

    fenestra_bench.py BENCH_OUT [-o ~/fenestra-ref/fenestra/solid]

The bench grabs only shell surfaces (no app windows, no blur): good for geometry and flat
colours, not for acrylic. Its run is dark theme at scale 1, except 16-start-light.
"""
import argparse
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'shell-kwin'))
from compose import place, TOP, BOTTOM, LEFT, RIGHT  # noqa: E402

# bench shot -> reference capture name
MAP = {
    '01-taskbar': 'dark-100-01-taskbar',
    '02-preview': 'dark-100-03-preview',
    '04-taskbar-menu': 'dark-100-04-taskbar-menu',
    '03-app-menu': 'dark-100-05-app-menu',
    '09-start': 'dark-100-06-start',
    '10-all-category': 'dark-100-07-start-all',
    '09b-power-menu': 'dark-100-08-power-menu',
    '09c-account-menu': 'dark-100-09-account-menu',
    '13-search-home': 'dark-100-10-search',
    '14-results': 'dark-100-11-search-query',
    '20-quick-settings': 'dark-100-12-quick',
    '19-center': 'dark-100-15-notifications',
    '17-banner': 'dark-100-17-toast',
    '21-osd': 'dark-100-18-osd-volume',
    '22-security': 'dark-100-20-secure-attention',
    '01b-overflow': 'dark-100-22-tray-overflow',
    '16-start-light': 'light-100-06-start',
}


def compose(src, bg):
    surfaces = json.load(open(f'{src}/surfaces.json'))
    x0 = min(s['screen'][0] for s in surfaces)
    y0 = min(s['screen'][1] for s in surfaces)
    w = max(s['screen'][0] + s['screen'][2] for s in surfaces) - x0
    h = max(s['screen'][1] + s['screen'][3] for s in surfaces) - y0
    dpr = max(s['dpr'] for s in surfaces)
    canvas = Image.new('RGBA', (round(w * dpr), round(h * dpr)), bg + (255,))

    def zone(screen, edge):
        return sum(o['exclusionZone'] for o in surfaces if o['screen'] == screen and o['exclusionZone'] > 0
                   and o['anchors'] & edge and bin(o['anchors']).count('1') in (1, 3))

    placed = []
    for s in sorted(surfaces, key=lambda s: s['layer']):
        img = Image.open(s['file'] if os.path.isabs(s['file']) and os.path.exists(s['file'])
                         else os.path.join(src, os.path.basename(s['file']))).convert('RGBA')
        sx, sy, sw, sh = s['screen']
        ml, mt, mr, mb = s['margins']
        a = s['anchors']
        if s['exclusionZone'] == 0:
            mt, mb = mt + zone(s['screen'], TOP), mb + zone(s['screen'], BOTTOM)
            ml, mr = ml + zone(s['screen'], LEFT), mr + zone(s['screen'], RIGHT)
        x = place(sx - x0, s['width'], sw, a & LEFT, a & RIGHT, ml, mr)
        y = place(sy - y0, s['height'], sh, a & TOP, a & BOTTOM, mt, mb)
        canvas.alpha_composite(img, (round(x * dpr), round(y * dpr)))
        placed.append({'layer': s['layer'], 'scope': s.get('scope'), 'excl': s['exclusionZone'],
                       'box': [round(x * dpr), round(y * dpr), img.width, img.height]})
    return canvas.convert('RGB'), placed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bench')
    ap.add_argument('-o', '--out', default=os.path.expanduser('~/fenestra-ref/fenestra/solid'))
    ap.add_argument('--bg', default='#1f1f1f')
    a = ap.parse_args()
    bg = tuple(int(a.bg.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    os.makedirs(a.out, exist_ok=True)
    for src, dst in MAP.items():
        d = os.path.join(a.bench, src)
        if not os.path.exists(os.path.join(d, 'surfaces.json')):
            print(f'missing {src}', file=sys.stderr)
            continue
        im, surfaces = compose(d, bg)
        im.save(os.path.join(a.out, dst + '.png'))
        # seed: centre of the topmost non-taskbar surface (the panel under test)
        meta = {'wallpaper': 'solid', 'bg': a.bg, 'note': f'KWin bench {src}, shell surfaces only'}
        panels = [s for s in surfaces if s['excl'] <= 0 and s['box'][3] < im.height]
        if panels:
            # the panel under test is the last placed non-taskbar surface; seed a point
            # 12 px inside its left edge, mid-height (inside the fill, off its text)
            b = panels[-1]['box']
            meta['seed'] = [b[0] + 12, b[1] + b[3] // 2]
            meta['surfaces'] = surfaces
        json.dump(meta, open(os.path.join(a.out, dst + '.json'), 'w'), ensure_ascii=False)
        print(dst)


if __name__ == '__main__':
    main()

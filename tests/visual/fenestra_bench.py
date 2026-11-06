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
MAP = {  # bench shot -> (reference capture name, scope of the surface under test)
    '01-taskbar': ('dark-100-01-taskbar', 'fenestra-taskbar'),
    '02-preview': ('dark-100-03-preview', 'fenestra-flyout'),
    '04-taskbar-menu': ('dark-100-04-taskbar-menu', 'fenestra-flyout'),
    '03-app-menu': ('dark-100-05-app-menu', 'fenestra-flyout'),
    '09-start': ('dark-100-06-start', 'fenestra-start'),
    '10-all-category': ('dark-100-07-start-all', 'fenestra-start'),
    '09b-power-menu': ('dark-100-08-power-menu', 'fenestra-flyout'),
    '09c-account-menu': ('dark-100-09-account-menu', 'fenestra-flyout'),
    '13-search-home': ('dark-100-10-search', 'fenestra-start'),
    '14-results': ('dark-100-11-search-query', 'fenestra-start'),
    '20-quick-settings': ('dark-100-12-quick', 'fenestra-flyout'),
    '19-center': ('dark-100-15-notifications', 'fenestra-flyout'),
    '17-banner': ('dark-100-17-toast', 'fenestra-toasts'),
    '21-osd': ('dark-100-18-osd-volume', 'fenestra-osd'),
    '22-security': ('dark-100-20-secure-attention', 'fenestra-security'),
    '01b-overflow': ('dark-100-22-tray-overflow', 'fenestra-flyout'),
    '24-desktop-menu': ('dark-100-23-desktop-menu', 'fenestra-flyout'),
    '27-snap-layouts': ('dark-100-27-snap-layouts', 'fenestra-snap'),
    '16-start-light': ('light-100-06-start', 'fenestra-start'),
}
SKIP = {'fenestra-wallpaper', 'fenestra-desktop'}  # replaced by the solid background


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
                   and zone_edge(o['anchors']) == edge)

    def zone_edge(a):
        # The edge an exclusive zone applies to: the only anchored edge, or of three anchored edges
        # the one whose opposite is free (a bottom taskbar anchored bottom|left|right reserves only
        # the bottom). Same rule as tests/shell-kwin/compose.py.
        if bin(a).count('1') == 1:
            return a
        if bin(a).count('1') == 3:
            for e, opposite in ((TOP, BOTTOM), (BOTTOM, TOP), (LEFT, RIGHT), (RIGHT, LEFT)):
                if a & e and not a & opposite:
                    return e
        return 0

    placed = []
    for s in sorted(surfaces, key=lambda s: s['layer']):
        if s.get('scope') in SKIP:
            continue
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
                       'box': [round(x * dpr), round(y * dpr), img.width, img.height], 'img': img})
    return canvas.convert('RGB'), placed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bench')
    ap.add_argument('-o', '--out', default=os.path.expanduser('~/fenestra-ref/fenestra/solid'))
    ap.add_argument('--bg', default='#1f1f1f')
    a = ap.parse_args()
    bg = tuple(int(a.bg.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    os.makedirs(a.out, exist_ok=True)
    for src, (dst, scope) in MAP.items():
        d = os.path.join(a.bench, src)
        if not os.path.exists(os.path.join(d, 'surfaces.json')):
            print(f'missing {src}', file=sys.stderr)
            continue
        im, placed = compose(d, bg)
        im.save(os.path.join(a.out, dst + '.png'))
        meta = {'wallpaper': 'solid', 'bg': a.bg, 'note': f'KWin bench {src} ({scope}), shell surfaces only'}
        under = [p for p in placed if p['scope'] == scope]
        if under and scope != 'fenestra-taskbar':
            p = under[-1]
            img = p['img']
            # seed: a pixel of the surface's most frequent opaque colour (its fill), nearest the centre
            cols = {}
            px = img.load()
            for yy in range(0, img.height, 2):
                for xx in range(0, img.width, 2):
                    c = px[xx, yy]
                    if c[3] >= 200:
                        cols[c[:3]] = cols.get(c[:3], 0) + 1
            if cols:
                fill = max(cols, key=cols.get)
                cx, cy = img.width // 2, img.height // 2
                best = min(((xx - cx) ** 2 + (yy - cy) ** 2, xx, yy) for yy in range(0, img.height, 2)
                           for xx in range(0, img.width, 2) if px[xx, yy][:3] == fill and px[xx, yy][3] >= 200)
                meta['seed'] = [p['box'][0] + best[1], p['box'][1] + best[2]]
        if under and scope not in ('fenestra-taskbar', 'fenestra-security'):
            # exact panel shape from the surface's alpha: fill and border count, the shadow
            # (dark, low alpha) does not. Saved next to the PNG for measure.py.
            p = under[-1]
            src_px = p['img'].load()
            mask = Image.new('L', im.size, 0)
            mp = mask.load()
            for yy in range(p['img'].height):
                for xx in range(p['img'].width):
                    r, g, b_, al = src_px[xx, yy]
                    if al >= 200 or (al >= 24 and max(r, g, b_) > 60):
                        X, Y = p['box'][0] + xx, p['box'][1] + yy
                        if 0 <= X < im.width and 0 <= Y < im.height:
                            mp[X, Y] = 255
            mask.save(os.path.join(a.out, dst + '.mask.png'))
            meta['mask'] = dst + '.mask.png'
        meta['surfaces'] = [{k: v for k, v in q.items() if k != 'img'} for q in placed]
        json.dump(meta, open(os.path.join(a.out, dst + '.json'), 'w'), ensure_ascii=False)
        print(dst)


if __name__ == '__main__':
    main()

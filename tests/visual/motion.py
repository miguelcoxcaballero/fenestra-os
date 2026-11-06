#!/usr/bin/env python3
"""Record a shell animation from the VM (QMP screendump, ~28 fps, real timestamps) and measure it.

    motion.py record NAME --keys meta_l [--click X,Y] [--frames 40] [--roi x0,y0,x1,y1]
    motion.py analyse DIR            (re-run the analysis on a recorded DIR)

Frames go to ~/fenestra-ref/motion/NAME/ (never the repo) with times.json. The analysis
tracks the bounding box of what changed against frame 0 inside ROI and prints, per frame,
t (ms after the trigger), the box and its mean luminance. From that it derives:
    duration  first change -> last frame whose box still moves (ms)
    offset    vertical travel of the box's top edge between its first and final position (px)
A VM has no real GPU and screendump is not vsync'd: every motion value is reliable=false.
"""
import argparse
import json
import os
import sys
import time

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'vm'))
import qmp  # noqa: E402

VM = os.path.expanduser('~/VMs/win11-ref')


def record(a):
    d = os.path.expanduser(f'~/fenestra-ref/motion/{a.name}')
    os.makedirs(d, exist_ok=True)
    s1, f1 = qmp.connect(os.path.join(VM, 'qmp.sock'))
    s2, f2 = qmp.connect(os.path.join(VM, 'qmp2.sock'))
    qmp.cmd(f2, 'screendump', filename=f'{d}/f000.ppm')
    t0 = time.monotonic()
    if a.click:
        x, y = (int(v) for v in a.click.split(','))
        qmp.cmd(f1, 'input-send-event', events=[{'type': 'abs', 'data': {'axis': 'x', 'value': int(x * 32767 / 1919)}},
                                                {'type': 'abs', 'data': {'axis': 'y', 'value': int(y * 32767 / 1079)}}])
        time.sleep(0.3)
        t0 = time.monotonic()
        for down in (True, False):
            qmp.cmd(f1, 'input-send-event', events=[{'type': 'btn', 'data': {'down': down, 'button': 'left'}}])
    if a.keys:
        t0 = time.monotonic()
        qmp.cmd(f1, 'send-key', keys=[{'type': 'qcode', 'data': k} for k in a.keys.split('-')])
    times = [0.0]
    for i in range(1, a.frames):
        qmp.cmd(f2, 'screendump', filename=f'{d}/f{i:03d}.ppm')
        times.append(round((time.monotonic() - t0) * 1000, 1))
    for i in range(a.frames):
        Image.open(f'{d}/f{i:03d}.ppm').save(f'{d}/f{i:03d}.png')
        os.unlink(f'{d}/f{i:03d}.ppm')
    json.dump({'times_ms': times, 'trigger': a.keys or a.click, 'roi': a.roi}, open(f'{d}/times.json', 'w'))
    return d


def analyse(d):
    meta = json.load(open(f'{d}/times.json'))
    times = meta['times_ms']
    f0 = Image.open(f'{d}/f000.png').convert('RGB')
    roi = tuple(int(v) for v in meta['roi'].split(',')) if meta.get('roi') else (0, 0, f0.width, f0.height - 48)
    base = f0.crop(roi)
    rows = []
    for i in range(1, len(times)):
        fr = Image.open(f'{d}/f{i:03d}.png').convert('RGB').crop(roi)
        diff = ImageChops.difference(base, fr).convert('L').point(lambda v: 255 if v > 12 else 0)
        bb = diff.getbbox()
        if bb:
            bb = (bb[0] + roi[0], bb[1] + roi[1], bb[2] + roi[0], bb[3] + roi[1])
            region = fr.crop((bb[0] - roi[0], bb[1] - roi[1], bb[2] - roi[0], bb[3] - roi[1])).convert('L')
            lumv = sum(i * n for i, n in enumerate(region.histogram())) / (region.width * region.height)
        else:
            lumv = None
        rows.append({'frame': i, 't_ms': times[i], 'box': bb, 'lum': round(lumv, 1) if lumv else None})
    moving = [r for r in rows if r['box']]
    res = {'frames': rows}
    if moving:
        final = moving[-1]['box']
        first = moving[0]
        settled = next((r for r in moving if r['box'] == final), moving[-1])
        res.update({'first_change_ms': first['t_ms'], 'settled_ms': settled['t_ms'],
                    'duration_ms': round(settled['t_ms'] - first['t_ms'], 1),
                    'offset_px': first['box'][1] - final[1], 'final_box': final,
                    'frame_interval_ms': round((times[-1] - times[1]) / max(1, len(times) - 2), 1),
                    'reliable': False})
    json.dump(res, open(f'{d}/analysis.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'frames'}))


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest='cmd', required=True)
r = sub.add_parser('record')
r.add_argument('name')
r.add_argument('--keys')
r.add_argument('--click')
r.add_argument('--frames', type=int, default=40)
r.add_argument('--roi')
an = sub.add_parser('analyse')
an.add_argument('dir')
a = ap.parse_args()
analyse(record(a) if a.cmd == 'record' else a.dir)

#!/usr/bin/env python3
"""Take one reference screenshot from the Windows VM and write its sidecar for measure.py.

    cap.py NAME [--seed X,Y] [--wall solid|bloom] [--bg #1f1f1f] [--note TEXT] [--dir DIR] [--probe key=X,Y ...]

NAME is <theme>-<pct>-<NN>-<name> (dark-100-06-start). Files go to DIR (default
~/fenestra-ref/raw/<wall>/), never into the repo. The sidecar records how the panel was
reached (note), where it is (seed) and what is behind it (wall/bg), so every number in
measurements.json can be traced back to a file and a pixel.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'vm'))
import qmp  # noqa: E402
from measure import NAME  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--seed')
ap.add_argument('--wall', default='solid')
ap.add_argument('--bg', default='#1f1f1f')
ap.add_argument('--note', default='')
ap.add_argument('--dir')
ap.add_argument('--probe', action='append', default=[])
ap.add_argument('--sock', default=os.path.expanduser('~/VMs/win11-ref/qmp.sock'))
a = ap.parse_args()
if not NAME.match(a.name + '.png'):
    sys.exit('NAME must be <dark|light>-<pct>-<NN>-<name>')
d = a.dir or os.path.expanduser(f'~/fenestra-ref/raw/{a.wall}')
repo = os.path.realpath(os.path.join(HERE, '..', '..'))
if os.path.realpath(d).startswith(repo + os.sep):
    sys.exit('refusing to write Windows screenshots inside the repo')
os.makedirs(d, exist_ok=True)
png = os.path.join(d, a.name + '.png')
s, f = qmp.connect(a.sock)
tmp = png + '.ppm'
qmp.cmd(f, 'screendump', filename=tmp)
from PIL import Image  # noqa: E402
Image.open(tmp).save(png)
os.unlink(tmp)
meta = {'wallpaper': a.wall, 'bg': a.bg, 'note': a.note}
if a.seed:
    meta['seed'] = [int(v) for v in a.seed.split(',')]
if a.probe:
    meta['probes'] = {k: [int(v) for v in xy.split(',')] for k, xy in (p.split('=') for p in a.probe)}
with open(png[:-4] + '.json', 'w') as fh:
    json.dump(meta, fh, ensure_ascii=False)
print(png)

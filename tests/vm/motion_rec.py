#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""motion_rec.py OUT ms ACTION... (env QMP = socket): record Windows (QMP screendump as fast as it answers) while doing ACTIONs.
ACTION: key:<qcode>[-<qcode>]  click:x,y  move:x,y  down  up  wait:ms  rec (start recording here; frames until ms after it)."""
import json, os, socket, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qmp
out, ms = sys.argv[1], int(sys.argv[2])
os.makedirs(out, exist_ok=True)
s, f = qmp.connect(os.environ.get('QMP', os.path.expanduser('~/VMs/win11-ref/qmp.sock')))
shm = '/dev/shm/vmrec'; os.makedirs(shm, exist_ok=True)
def mv(x, y):
    qmp.cmd(f, 'input-send-event', events=[{'type': 'abs', 'data': {'axis': 'x', 'value': int(x * 32767 / 1919)}},
                                           {'type': 'abs', 'data': {'axis': 'y', 'value': int(y * 32767 / 1079)}}])
frames, t0 = [], None
def grab():
    a = time.monotonic(); p = f'{shm}/r{len(frames):03d}.ppm'
    qmp.cmd(f, 'screendump', filename=p)
    frames.append((p, round(((a + time.monotonic()) / 2 - t0) * 1000, 1)))
acts = sys.argv[3:]
for a in acts:
    if a == 'rec':
        t0 = time.monotonic(); grab(); continue
    kind, _, arg = a.partition(':')
    if kind == 'key':
        if t0 is not None: tk = round((time.monotonic() - t0) * 1000, 1)
        qmp.cmd(f, 'send-key', keys=[{'type': 'qcode', 'data': k} for k in arg.split('-')])
        if t0 is not None: print('trigger at', tk)
    elif kind in ('click', 'move'):
        x, y = map(int, arg.split(',')); mv(x, y)
        if kind == 'click':
            time.sleep(0.3)
            if t0 is not None: print('trigger at', round((time.monotonic() - t0) * 1000, 1))
            for d in (True, False):
                qmp.cmd(f, 'input-send-event', events=[{'type': 'btn', 'data': {'down': d, 'button': 'left'}}]); time.sleep(0.05)
    elif kind in ('down', 'up'):
        if t0 is not None: print(kind, 'at', round((time.monotonic() - t0) * 1000, 1))
        qmp.cmd(f, 'input-send-event', events=[{'type': 'btn', 'data': {'down': kind == 'down', 'button': 'left'}}])
    elif kind == 'wait':
        end = time.monotonic() + int(arg) / 1000
        while time.monotonic() < end:
            if t0 is not None: grab()
            else: time.sleep(0.01)
if t0 is not None:
    end = t0 + ms / 1000 + (time.monotonic() - t0)
    while time.monotonic() < end: grab()
from PIL import Image
for i, (p, t) in enumerate(frames):
    Image.open(p).save(f'{out}/f{i:03d}.png'); os.unlink(p)
json.dump({'times_ms': [t for _, t in frames], 'actions': acts}, open(f'{out}/times.json', 'w'))
print(len(frames), 'frames, interval', round((frames[-1][1] - frames[0][1]) / max(1, len(frames) - 1), 1) if frames else 0)

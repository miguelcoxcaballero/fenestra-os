#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""vm_rec.py OUT PRE_MS POST_MS KEYS : records the Windows 11 reference VM (QMP screendump as fast
as QEMU answers, ~25 ms at 2880x1800) PRE_MS before and POST_MS after sending KEYS (qcodes joined
by '-', e.g. meta_l-2, alt-f4, meta_l-down). OUT/fNNN.png + times.json, times relative to the key
press (the middle of each screendump call). env QMP (socket, default ~/VMs/win11-ref/qmp.sock)."""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'vm'))
import qmp
from PIL import Image

out, pre, post, keys = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
os.makedirs(out, exist_ok=True)
s, f = qmp.connect(os.environ.get('QMP', os.path.expanduser('~/VMs/win11-ref/qmp.sock')))
shm = f'/dev/shm/winanim-{os.getpid()}'; os.makedirs(shm, exist_ok=True)
frames = []
def grab(t0):
    a = time.monotonic(); p = f'{shm}/r{len(frames):04d}.ppm'
    qmp.cmd(f, 'screendump', filename=p)
    frames.append([p, ((a + time.monotonic()) / 2 - t0) * 1000])
t0 = time.monotonic()
while (time.monotonic() - t0) * 1000 < pre:
    grab(t0)
tk = time.monotonic()
qmp.cmd(f, 'send-key', keys=[{'type': 'qcode', 'data': k} for k in keys.split('-')])
while (time.monotonic() - tk) * 1000 < post:
    grab(t0)
shift = (tk - t0) * 1000
for i, (p, t) in enumerate(frames):
    Image.open(p).save(f'{out}/f{i:03d}.png'); os.unlink(p)
os.rmdir(shm)
json.dump({'times_ms': [round(t - shift, 1) for _, t in frames], 'keys': keys}, open(f'{out}/times.json', 'w'))
print(len(frames), 'frames, mean interval', round((frames[-1][1] - frames[0][1]) / max(1, len(frames) - 1), 1))

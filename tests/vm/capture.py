#!/usr/bin/env python3
"""Record a region of a QEMU VM screen as fast as QMP screendump allows.

    capture.py QMP_SOCKET OUT_DIR SECONDS [X Y W H]

Each frame is cropped and saved as OUT_DIR/NNNNN.png; OUT_DIR/times.txt has the
monotonic time (s) of every frame. Used to measure Windows 11's boot/restart spinners
(timing and per-dot motion), which only exist on a running Windows.
"""
import json
import os
import socket
import sys
import time

from PIL import Image


def main():
    sock, out, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
    box = tuple(int(v) for v in sys.argv[4:8]) if len(sys.argv) >= 8 else None
    os.makedirs(out, exist_ok=True)
    s = socket.socket(socket.AF_UNIX)
    s.connect(sock)
    f = s.makefile('rw')
    json.loads(f.readline())

    def cmd(c, **a):
        f.write(json.dumps({'execute': c, 'arguments': a} if a else {'execute': c}) + '\n')
        f.flush()
        while True:
            r = json.loads(f.readline())
            if 'return' in r or 'error' in r:
                return r

    cmd('qmp_capabilities')
    tmp = f'/dev/shm/fenestra-cap-{os.getpid()}.ppm'
    t0 = time.monotonic()
    n = 0
    times = []
    while time.monotonic() - t0 < secs:
        t = time.monotonic()
        try:
            r = cmd('screendump', filename=tmp)
        except (OSError, ValueError):          # the VM went away: keep what was recorded
            break
        if 'error' in r:
            time.sleep(0.05)
            continue
        im = Image.open(tmp)
        im.load()
        if box:
            x, y, w, h = box
            im = im.crop((x, y, x + w, y + h))
        im.save(f'{out}/{n:05d}.png', compress_level=1)
        times.append(f'{t - t0:.4f} {im.size[0]}x{im.size[1]}')
        n += 1
    if os.path.exists(tmp):
        os.remove(tmp)
    open(f'{out}/times.txt', 'w').write('\n'.join(times) + '\n')
    print(f'{n} frames, {n / max(1e-3, time.monotonic() - t0):.1f} fps')


if __name__ == '__main__':
    main()

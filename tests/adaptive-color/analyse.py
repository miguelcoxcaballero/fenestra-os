#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summary of a bench recording (recorder.py TSV): per scene, the colour temperature KWin
ended at, how it got there (commits, largest single step, fastest commit rate, transition
time) and whether it ever reversed direction (a swing back and forth = visible pumping)."""
import sys
from collections import OrderedDict

rows = []
for line in open(sys.argv[1]):
    p = line.rstrip("\n").split("\t")
    if len(p) < 4 or p[1] != "currentTemperature":
        continue
    rows.append((float(p[0]), int(p[2]), p[3]))

scenes = OrderedDict()
for t, k, s in rows:
    scenes.setdefault(s, []).append((t, k))

print(f"\n{'scene':<62} {'start':>6} {'end':>6} {'commits':>7} {'maxstep':>7} {'min dt':>7} {'ramp s':>7} {'reversals':>9}")
prev_end = None
for s, pts in scenes.items():
    ks = [k for _t, k in pts]
    start = prev_end if prev_end is not None else ks[0]
    seq = ([start] if prev_end is not None else []) + ks
    steps = [b - a for a, b in zip(seq, seq[1:]) if b != a]
    maxstep = max((abs(x) for x in steps), default=0)
    dts = [b[0] - a[0] for a, b in zip(pts, pts[1:])]
    mindt = min(dts, default=0)
    ramp = pts[-1][0] - pts[0][0] if len(pts) > 1 else 0
    rev, d = 0, 0
    for x in steps:
        sd = 1 if x > 0 else -1
        if d and sd != d:
            rev += 1
        d = sd
    print(f"{s[:62]:<62} {start:>6} {ks[-1]:>6} {len(steps):>7} {maxstep:>7} {mindt:>7.3f} {ramp:>7.1f} {rev:>9}")
    prev_end = ks[-1]

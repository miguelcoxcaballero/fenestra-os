#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""udwm_map.py uDWM.dll: finds DWM's transition -> storyboard function (26100: at 0x18000c1c4) by its
shape - a switch on the transition (edx) whose cases store the storyboard into [r8] and target 1
into [r9] - and runs it for each transition. Needs objdump (binutils, pei-x86-64). Transitions as
DWM's WindowAnimationType: 1 open, 2 maximize, 3 minimize, 4 restore from maximized,
5 restore from minimized, 6 close."""
import re, subprocess, sys
asm = subprocess.run(['objdump', '-d', '--no-show-raw-insn', sys.argv[1]], capture_output=True, text=True).stdout.split('\n')
ins = []
for l in asm:
    m = re.match(r'^\s*([0-9a-f]+):\s+(.*)$', l)
    if m: ins.append((int(m.group(1), 16), m.group(2).strip()))
at = {a: i for i, (a, _) in enumerate(ins)}
for k, (a, t) in enumerate(ins):
    if t != 'movl   $0x1,(%r9)': continue
    s = k
    while s > 0 and ins[s - 1][1] != 'int3': s -= 1
    if not any('cmp    $0xa,%edx' in t for _, t in ins[s:k]): continue
    print('function at', hex(ins[s][0]))
    for n in range(0, 32):
        edx, flags, i, out = n, None, s, None
        for _ in range(200):
            a, t = ins[i]
            m = re.match(r'(cmp|sub)\s+\$0x([0-9a-f]+),%edx', t)
            if m:
                v = int(m.group(2), 16); r = edx - v
                if m.group(1) == 'sub': edx = r
                flags = r; i += 1; continue
            m = re.match(r'(je|jne|jg|jmp)\s+0x([0-9a-f]+)', t)
            if m:
                c = m.group(1)
                take = c == 'jmp' or (c == 'je' and flags == 0) or (c == 'jne' and flags != 0) or (c == 'jg' and flags > 0)
                i = at[int(m.group(2), 16)] if take else i + 1; continue
            m = re.match(r'movl\s+\$0x([0-9a-f]+),\(%r8\)', t)
            if m: out = int(m.group(1), 16); break
            if t.startswith('ret') or 'mov    $0x80070057' in t: break
            i += 1
        if out is not None: print(f'  transition {n}: storyboard {out}')
    break

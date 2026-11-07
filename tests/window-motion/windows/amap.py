#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""amap.py aero.msstyles [SB...]: prints the theme's animation map (resource AMAP): the cubic-Bézier
timing functions (class "timingfunction") and the storyboards (class "animations", part =
storyboard, state = target) with their transforms (uxtheme.h TA_TRANSFORM*: type, timing function,
start, duration, flags, values). Records: 32-byte header (property, primitive type, class, part,
state, -, -, size), data, padding to 8 bytes; storyboard data: size, 16, offset of the transforms,
0, TA_PROPERTIES-like block, then the transforms, each padded to 8 bytes."""
import struct, sys

def resources(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec, optsz = struct.unpack_from('<H', d, pe + 6)[0], struct.unpack_from('<H', d, pe + 20)[0]
    opt = pe + 24
    dd = opt + (96 if struct.unpack_from('<H', d, opt)[0] == 0x10b else 112)
    rva_res = struct.unpack_from('<I', d, dd + 16)[0]
    secs = [(struct.unpack_from('<I', d, o + 12)[0], struct.unpack_from('<I', d, o + 8)[0], struct.unpack_from('<I', d, o + 20)[0],
             struct.unpack_from('<I', d, o + 16)[0]) for o in (opt + optsz + 40 * i for i in range(nsec))]
    off = lambda r: next(r - va + rp for va, vs, rp, rs in secs if va <= r < va + max(vs, rs))
    base = off(rva_res)
    def name(n):
        if n & 0x80000000:
            p = base + (n & 0x7fffffff)
            return d[p + 2:p + 2 + 2 * struct.unpack_from('<H', d, p)[0]].decode('utf-16le')
        return n
    def walk(p, path):
        nn, ni = struct.unpack_from('<HH', d, base + p + 12)
        for i in range(nn + ni):
            n, o = struct.unpack_from('<II', d, base + p + 16 + 8 * i)
            if o & 0x80000000:
                yield from walk(o & 0x7fffffff, path + [name(n)])
            else:
                rva, size = struct.unpack_from('<II', d, base + o)
                yield path + [name(n)], d[off(rva):off(rva) + size]
    return dict(('/'.join(map(str, p)), b) for p, b in walk(0, []))

TYPES = {0: 'translate', 1: 'scale', 2: 'opacity', 3: 'clip', 258: 'translate3d', 259: 'scale3d', 260: 'rotate3d'}
FLOATS = {0: 6, 1: 6, 2: 2, 3: 8, 258: 9, 259: 9, 260: 9}

def parse(amap):
    p, timing, boards = 0, {}, {}
    while p + 32 <= len(amap):
        h = struct.unpack_from('<8I', amap, p)
        data = amap[p + 32:p + 32 + h[7]]
        p = (p + 32 + h[7] + 7) & ~7
        if h[0] == 20100:  # timing function: TA_CUBIC_BEZIER
            t, x1, y1, x2, y2 = struct.unpack_from('<I4f', data)
            timing[h[3]] = tuple(round(v, 4) for v in (x1, y1, x2, y2))
        elif h[0] == 20000:  # storyboard h[3], target h[4]
            _, _, toff = struct.unpack_from('<3I', data)
            count = struct.unpack_from('<I', data, 20)[0]
            o, tr = toff, []
            for _ in range(count):
                typ, tf, start, dur, flags = struct.unpack_from('<5I', data, o); o += 20
                n = min(FLOATS.get(typ, 0), (len(data) - o) // 4)
                vals = [round(v, 4) for v in struct.unpack_from('<%df' % n, data, o)]
                o = (o + 4 * n + 7) & ~7
                tr.append({'type': TYPES.get(typ, typ), 'timing': tf, 'start': start, 'duration': dur, 'flags': flags, 'values': vals})
            boards[(h[3], h[4])] = tr
    return timing, boards

if __name__ == '__main__':
    res = resources(open(sys.argv[1], 'rb').read())
    timing, boards = parse(res['AMAP/AMAP/1033'])
    want = set(map(int, sys.argv[2:]))
    for (sb, tg), tr in sorted(boards.items()):
        if want and sb not in want: continue
        print(f'storyboard {sb} target {tg}')
        for t in tr:
            print(f"  {t['type']:9s} {t['start']}+{t['duration']} ms  timing {t['timing']} {timing.get(t['timing'])}  flags {t['flags']}  {t['values']}")

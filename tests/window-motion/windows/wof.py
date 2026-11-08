#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""wof.py STREAM SIZE OUT: decompresses a WOF (CompactOS) file - the ":WofCompressedData" stream 7-Zip
extracts next to an empty file - with XPRESS8K chunks (XPRESS Huffman, [MS-XCA] 2.2)."""
import struct, sys
def xpress_huff(src, outlen):
    lens = []
    for b in src[:256]: lens += [b & 15, b >> 4]
    # canonical decode table for 15-bit lookup
    table = [None] * (1 << 15)
    code = 0
    syms = sorted([(l, s) for s, l in enumerate(lens) if l])
    for l, s in syms:
        pass
    # assign codes
    code = 0; prev = 0
    for bitlen in range(1, 16):
        for s in range(512):
            if lens[s] == bitlen:
                start = code << (15 - bitlen); n = 1 << (15 - bitlen)
                for k in range(start, start + n): table[k] = (s, bitlen)
                code += 1
        code <<= 1
    out = bytearray(); pos = 256
    nb = (struct.unpack_from('<H', src, pos)[0] << 16) | struct.unpack_from('<H', src, pos + 2)[0]; pos += 4; extra = 16
    def u16(p): return struct.unpack_from('<H', src, p)[0] if p + 1 < len(src) else 0
    while len(out) < outlen:
        s, l = table[nb >> 17]
        nb = (nb << l) & 0xFFFFFFFF; extra -= l
        if extra < 0:
            nb |= u16(pos) << (-extra); extra += 16; pos += 2
        if s < 256:
            out.append(s); continue
        s -= 256; ml = s & 15; ob = s >> 4
        if ml == 15:
            ml = src[pos]; pos += 1
            if ml == 255:
                ml = u16(pos); pos += 2
                if ml == 0:
                    ml = struct.unpack_from('<I', src, pos)[0]; pos += 4
                ml -= 15
            ml += 15
        ml += 3
        off = ((nb >> (32 - ob)) if ob else 0) + (1 << ob)
        nb = (nb << ob) & 0xFFFFFFFF; extra -= ob
        if extra < 0:
            nb |= u16(pos) << (-extra); extra += 16; pos += 2
        for _ in range(ml): out.append(out[-off])
    return bytes(out[:outlen])
def wof(data, size, cs=8192):
    n = (size + cs - 1) // cs
    t = [0] + list(struct.unpack_from('<%dI' % (n - 1), data, 0)); base = 4 * (n - 1)
    t.append(len(data) - base)
    out = bytearray()
    for i in range(n):
        c = data[base + t[i]: base + t[i + 1]]; ul = min(cs, size - i * cs)
        out += c if len(c) == ul else xpress_huff(c, ul)
    return bytes(out)
if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read(); open(sys.argv[3], 'wb').write(wof(d, int(sys.argv[2])))

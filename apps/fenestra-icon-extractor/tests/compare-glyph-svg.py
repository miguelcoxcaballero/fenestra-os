#!/usr/bin/python3
"""Compares the SVGs written by tests/TrueTypeTests (src/TrueType.cs) with FreeType's own rendering.

Usage: compare-glyph-svg.py FONT.ttf SVGDIR [--size 256] [--sheet sheet.png]
Needs cairosvg (renders the SVG), freetype-py (FreeType, renders the font) and Pillow. For each glyph
the SVG is rasterised at SIZE x SIZE (the em square) and FreeType renders the same character from the
font, unhinted, at SIZE px per em with its origin at the SVG's baseline; the two coverage masks must
match (IoU >= 0.97, or mean |difference| < 0.2 % for hairline glyphs).
Exit 0 when every glyph matches.
"""
import argparse
import io
import json
import sys
from pathlib import Path

import cairosvg
import freetype
from PIL import Image, ImageChops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('font')
    ap.add_argument('svgdir')
    ap.add_argument('--size', type=int, default=256)
    ap.add_argument('--sheet')
    a = ap.parse_args()
    s = a.size
    summary = json.loads((Path(a.svgdir) / 'summary.json').read_text())
    upem, base = summary['units_per_em'], summary['baseline']
    face = freetype.Face(a.font)
    face.set_pixel_sizes(0, s)
    bpx = base * s / upem
    by = int(bpx)
    # Fractional part of the baseline: move the outline down by it (26.6 units, FreeType y grows up).
    face.set_transform(freetype.Matrix(0x10000, 0, 0, 0x10000), freetype.Vector(0, -round((bpx - by) * 64)))
    rows, worst, failed = [], 1.0, 0
    for e in summary['entries']:
        if not e['svg']:
            print(f"{e['cp']}: no outline (glyph {e['glyph']})")
            continue
        cp = int(e['cp'][2:], 16)
        png = cairosvg.svg2png(url=str(Path(a.svgdir) / f'{cp:04X}.svg'), output_width=s, output_height=s)
        mine = Image.open(io.BytesIO(png)).convert('RGBA').getchannel('A')
        face.load_char(chr(cp), freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_RENDER)
        g = face.glyph
        bm = g.bitmap
        ref = Image.new('L', (s, s), 0)
        if bm.width and bm.rows:
            pitch = bm.pitch
            img = Image.frombytes('L', (bm.width, bm.rows), bytes(bm.buffer), 'raw', 'L', pitch)
            ref.paste(img, (g.bitmap_left, by - g.bitmap_top))
        m = mine.point(lambda v: 255 if v >= 128 else 0)
        r = ref.point(lambda v: 255 if v >= 128 else 0)
        inter = ImageChops.multiply(m, r).histogram()[255]
        union = ImageChops.lighter(m, r).histogram()[255]
        iou = inter / union if union else 1.0
        diff = ImageChops.difference(mine, ref)
        mad = sum(i * n for i, n in enumerate(diff.histogram())) / (s * s * 255)
        ok = iou >= 0.97 or mad < 0.002   # hairline glyphs: IoU is noisy, the coverage still matches
        failed += not ok
        worst = min(worst, iou)
        print(f"{e['cp']} glyph {e['glyph']:5d} contours {e['contours']:2d}: IoU {iou:.4f}  mean |diff| {mad:.4f}  {'ok' if ok else 'MISMATCH'}")
        rows.append((mine, ref))
    if a.sheet and rows:
        t = 96
        sheet = Image.new('L', (2 * t + 8, len(rows) * (t + 4)), 40)
        for i, (mi, re_) in enumerate(rows):
            sheet.paste(mi.resize((t, t)), (0, i * (t + 4)))
            sheet.paste(re_.resize((t, t)), (t + 8, i * (t + 4)))
        sheet.save(a.sheet)
    print(f"{summary['font']}: {len(rows)} glyphs, worst IoU {worst:.4f}, {failed} mismatches")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

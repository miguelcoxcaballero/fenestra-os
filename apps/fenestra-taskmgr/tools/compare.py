#!/usr/bin/env python3
"""Side-by-side comparison: Windows reference (left) vs Fenestra render (right).

    compare.py REF.png REF_BOX FENESTRA.png OUT.png [--label]
REF_BOX = x,y,w,h of the Task Manager window inside the reference capture.
"""
import sys

from PIL import Image, ImageDraw


def main():
    ref, box, ours, out = sys.argv[1:5]
    x, y, w, h = (int(v) for v in box.split(","))
    a = Image.open(ref).convert("RGB").crop((x, y, x + w, y + h))
    b = Image.open(ours).convert("RGB")
    b = b.crop((0, 0, min(w, b.width), min(h, b.height)))
    gap = 16
    im = Image.new("RGB", (w * 2 + gap, h + 28), (60, 60, 60))
    im.paste(a, (0, 28))
    im.paste(b, (w + gap, 28))
    d = ImageDraw.Draw(im)
    d.text((8, 8), "Windows 11 Task Manager (reference)", fill=(255, 255, 255))
    d.text((w + gap + 8, 8), "Fenestra Task Manager", fill=(255, 255, 255))
    im.save(out)


if __name__ == "__main__":
    main()

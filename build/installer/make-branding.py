#!/usr/bin/env python3
"""Render the Fenestra installer artwork (sidebar/topbar backgrounds, logo).

  build/installer/make-branding.py OUT_DIR

Original artwork: a deep blue gradient with soft light blooms and the
Fenestra logo + wordmark. Needs Pillow; uses rsvg-convert for the logo and
Selawik (OFL) for the wordmark when available, otherwise DejaVu/sans.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGO_SVG = os.path.join(REPO, "assets/generated/branding/fenestra-logo.svg")
TOP, BOTTOM = (11, 42, 99), (20, 64, 150)


def gradient(w, h, horizontal=False):
    im = Image.new("RGB", (w, h))
    px = im.load()
    n = (w if horizontal else h) - 1 or 1
    for i in range(w if horizontal else h):
        t = i / n
        c = tuple(int(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        if horizontal:
            for y in range(h):
                px[i, y] = c
        else:
            for x in range(w):
                px[x, i] = c
    return im


def bloom(im, blobs):
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (cx, cy, r, color) in blobs:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(min(im.size) // 3 or 1))
    out = im.convert("RGBA")
    out.alpha_composite(layer)
    return out


def font(size):
    for path in (os.path.join(REPO, "build/out/rootfs/usr/share/fonts/selawik/selawk.ttf"),  # build-overlay.sh
                 "/usr/share/fonts/selawik/selawk.ttf",
                 "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def logo_png(size):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "logo.png")
        subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), "-o", out, LOGO_SVG], check=True)
        return Image.open(out).convert("RGBA")


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # Sidebar: 406x767 like Anaconda's own (scaled with background-size: cover).
    side = bloom(gradient(406, 1080), [(60, 900, 260, (90, 150, 255, 120)),
                                       (380, 200, 220, (130, 110, 255, 90))])
    side.convert("RGB").save(os.path.join(out_dir, "sidebar-bg.png"))
    top = bloom(gradient(1600, 132, horizontal=True), [(1300, 60, 200, (120, 130, 255, 80))])
    top.convert("RGB").save(os.path.join(out_dir, "topbar-bg.png"))
    # Logo + wordmark, white text, transparent background (fits the 170 px sidebar).
    logo = logo_png(72)
    f = font(30)
    text = "Fenestra"
    tw = int(f.getlength(text))
    w = max(150, tw + 8)
    img = Image.new("RGBA", (w, 72 + 12 + 40), (0, 0, 0, 0))
    img.alpha_composite(logo, ((w - 72) // 2, 0))
    ImageDraw.Draw(img).text(((w - tw) // 2, 84), text, font=f, fill=(255, 255, 255, 255))
    img.save(os.path.join(out_dir, "sidebar-logo.png"))


if __name__ == "__main__":
    main(sys.argv[1])

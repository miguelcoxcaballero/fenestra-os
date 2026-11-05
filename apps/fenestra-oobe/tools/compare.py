#!/usr/bin/python3
"""Side-by-side comparison of Fenestra OOBE pages with reference captures.

For every pair it renders the Fenestra page at 1920x1080 (headless compositor
only: WAYLAND_DISPLAY=fenestra-test, GDK_BACKEND=wayland, no DISPLAY) and
writes screenshots/compare-<name>.png: reference left, Fenestra right, with
small captions.

  tools/compare.py [--ref-dir DIR] [--scale 0.5] [names...]
"""

import argparse
import os
import subprocess
import sys

import cairo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REF = os.path.normpath(os.path.join(HERE, "..", "..", "tests", "vm", "shots", "win11"))

# name -> (reference file, fenestra page id)
PAIRS = {
    "region": ("oobe-01-region.png", "region"),
    "keyboard": ("oobe-03-second-keyboard.png", "keyboard"),
    "second-keyboard": ("oobe-04.png", "keyboard-second"),
    "checking-for-updates": ("oobe-05.png", "updates"),
}


def render(page, out):
    env = dict(os.environ, WAYLAND_DISPLAY=os.environ.get("OOBE_WAYLAND_DISPLAY", "fenestra-test"),
               GDK_BACKEND="wayland")
    env.pop("DISPLAY", None)
    subprocess.run([os.path.join(HERE, "bin", "fenestra-oobe"), "--lang", "en", "--country", "US",
                    "--size", "1920x1080", "--page", page, "--screenshot", out],
                   env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)


def surface_from(path):
    return cairo.ImageSurface.create_from_png(path)


def compose(ref_png, fen_png, out, scale):
    a, b = surface_from(ref_png), surface_from(fen_png)
    w, h = int(a.get_width() * scale), int(a.get_height() * scale)
    gap, cap = 16, 34
    out_s = cairo.ImageSurface(cairo.FORMAT_RGB24, w * 2 + gap * 3, h + cap + gap * 2)
    cr = cairo.Context(out_s)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    for i, (surf, label) in enumerate(((a, "Reference OOBE"), (b, "Fenestra OOBE"))):
        x = gap + i * (w + gap)
        cr.save()
        cr.translate(x, gap + cap)
        cr.scale(scale, scale)
        cr.set_source_surface(surf, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.paint()
        cr.restore()
        cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(16)
        cr.move_to(x, gap + 20)
        cr.show_text(label)
    out_s.write_to_png(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-dir", default=DEFAULT_REF)
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("names", nargs="*", default=list(PAIRS))
    args = ap.parse_args()
    shots = os.path.join(HERE, "screenshots")
    os.makedirs(shots, exist_ok=True)
    for name in args.names:
        ref, page = PAIRS[name]
        ref_path = os.path.join(args.ref_dir, ref)
        if not os.path.exists(ref_path):
            print(f"skip {name}: {ref_path} missing", file=sys.stderr)
            continue
        fen = os.path.join(shots, f"compare-{name}-fenestra.png")
        render(page, fen)
        out = os.path.join(shots, f"compare-{name}.png")
        compose(ref_path, fen, out, args.scale)
        print("wrote", out)


if __name__ == "__main__":
    main()

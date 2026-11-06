#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds the "frozen screen" for the snipping overlay checks (Q04). KWin's ScreenShot2 needs
OpenGL, which the bench lacks, so the shell reads FENESTRA_SHELL_SNIP_IMAGE instead: the shell
surfaces saved by the test probe (Grab), composed like compose.py, with a plain frame where each
app window is (WindowsModel geometry, bottom to top) between the wallpaper and the taskbar layer,
so window mode has something to point at. Fixture only: the frames are drawn here, they are not
the apps' pixels.
    snip-source.py GRAB_DIR OUT.png
"""
import json
import os
import sys

import gi
from PIL import ImageDraw, ImageFont

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose  # noqa: E402

WINDOWS = """JSON.stringify(Array.from({length: WindowsModel.count}, (_, i) => {
    const ix = WindowsModel.index(i, 0), g = WindowsModel.data(ix, 266)
    return {title: WindowsModel.data(ix, 257), x: g.x, y: g.y, w: g.width, h: g.height,
            stacking: WindowsModel.data(ix, 267), minimized: WindowsModel.data(ix, 261)} }))"""


def probe(expression):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    reply = bus.call_sync("org.fenestra.Shell", "/org/fenestra/Shell/Test", "org.fenestra.Shell.Test", "Eval",
                          GLib.Variant("(s)", (expression,)), GLib.VariantType("(s)"), 0, 5000)
    return json.loads(reply.unpack()[0])[0]


def main(grab_dir, out):
    dark = probe("Theme.dark")
    windows = sorted((w for w in json.loads(probe(WINDOWS)) if not w["minimized"]), key=lambda w: w["stacking"])
    try:
        font = ImageFont.truetype("/usr/share/fonts/google-noto/NotoSans-Regular.ttf", 12)
    except OSError:
        font = ImageFont.load_default()

    def draw_windows(canvas, x0, y0, dpr):
        d = ImageDraw.Draw(canvas)
        for w in windows:
            x, y = round((w["x"] - x0) * dpr), round((w["y"] - y0) * dpr)
            x2, y2 = x + round(w["w"] * dpr) - 1, y + round(w["h"] * dpr) - 1
            d.rectangle((x, y, x2, y2), fill=(32, 32, 32) if dark else (249, 249, 249), outline=(90, 90, 90))
            d.rectangle((x + 1, y + 1, x2 - 1, y + round(32 * dpr)), fill=(43, 43, 43) if dark else (238, 238, 238))
            try:
                d.text((x + 12, y + 9), w["title"], font=font, fill=(255, 255, 255) if dark else (26, 26, 26))
            except UnicodeEncodeError:  # the built-in bitmap font (fallback) is Latin-1 only
                pass

    compose.main(grab_dir, out, below_top=draw_windows)


if __name__ == "__main__":
    main(*sys.argv[1:3])

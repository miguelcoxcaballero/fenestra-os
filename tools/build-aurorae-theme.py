#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generates the Fenestra window decoration for KWin (Aurorae SVG themes Fenestra-Dark and
Fenestra-Light) into kwin/aurorae/ (or the directory given as the first argument).

Windows 11 standard (Win32) frame, measured on the reference shots (100 %):
  - caption buttons 46 x 32, no gap, flush with the 1 px top and right border
    (dialogs/dark-100-32-print-hover-close: close #c42b1c at x 1179-1224, y 118-149 under the
    border row 117; apps/dark-100-40-explorer-home: glyphs 18 px from the button's left edge);
  - glyphs = Segoe Fluent Icons ChromeMinimize / ChromeMaximize / ChromeRestore / ChromeClose at
    10 px (their outlines are 1/10 em strokes with round ends: drawn here as the same 1 px line
    art, no Microsoft artwork), the minimize bar on the 6th row of the 10 px box;
  - hover 6 % / pressed 4 % of the text colour (#2d2d2d on #202020, solid/dark-100-24), close
    #c42b1c with a white glyph, glyphs of an inactive window at 40 %;
  - 1 px border #3e3e3e (dark; the reference frames measure 61-63), 8 px corner radius
    (DWMWCP_ROUND), the window shadow of the GTK theme (window.csd box-shadow) so server-side
    and client-side frames match.

Aurorae draws the frame *under* the client, so only the title-bar corners can be round: the
client's own bottom corners stay square (KWin rounds client corners only for decorations that
set KDecoration3::BorderRadius, which Aurorae does not).

Every frame piece is an <image> whose bounds are exactly the piece (KSvg sizes the 9-slice pieces
from the element bounds, and clip-paths do not shrink them: the old theme drew a whole rounded
rectangle in every piece, a grid of seams on screen). The pieces are rasters at 4x (shadow,
body and border, antialiased), so they stay smooth at fractional scales; the shadow lives in the
padding, which Aurorae hands to KWin as the window shadow.
"""
import base64
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
T = json.loads((ROOT / "design/tokens.json").read_text())
BW, BH = T.get("window.button.width", 46), T.get("window.button.height", 32)
TITLE = T.get("window.title.height", 32)
R = T.get("window.radius", 8)
SS = 4                      # shadow raster supersampling (crisp enough at 150-200 %)
PAD_L = PAD_R = 36          # shadow extents (logical px): see SHADOWS
PAD_T, PAD_B = 24, 48
C = 48                      # frame corner size beyond the padding (covers the shadow fall-off)
E = 40                      # edge / centre piece length (tiled: uniform along the edge)
# CSS box-shadows (offset-y, blur radius, alpha) of the GTK theme's window.csd, active / inactive.
SHADOWS = {"active": [(1, 3, 0.10), (16, 18, 0.15), (11, 23, 0.13)],
           "inactive": [(1, 2, 0.10), (3, 4, 0.14), (1, 6, 0.12)]}
SCHEMES = {
    "Dark": {"bar": "#202020", "bar_inactive": "#202020", "fg": "#ffffff", "fg_inactive": "#9a9a9a",
             "border": "#3e3e3e", "border_inactive": "#3a3a3a", "shadow": 1.0},
    "Light": {"bar": "#f3f3f3", "bar_inactive": "#f9f9f9", "fg": "#000000", "fg_inactive": "#8a8a8a",
              "border": "#c8c8c8", "border_inactive": "#d0d0d0", "shadow": 0.85},
}
# 10 x 10 glyph box, 1 px strokes with round ends: the Chrome* glyphs of Segoe Fluent Icons.
GLYPHS = {
    "minimize": '<path d="M0.5 5.5H9.5"/>',
    "maximize": '<rect x="0.5" y="0.5" width="9" height="9" rx="1"/>',
    "restore": '<rect x="0.5" y="2.5" width="7" height="7" rx="1"/>'
               '<path d="M2.1 0.5H7a2.5 2.5 0 0 1 2.5 2.5V7.9"/>',
    "close": '<path d="M0.5 0.5L9.5 9.5M9.5 0.5L0.5 9.5"/>',
}


def blur(a, sigma):
    k = int(3 * sigma) + 1
    x = np.arange(-k, k + 1)
    g = np.exp(-x * x / (2 * sigma * sigma)); g /= g.sum()
    a = np.apply_along_axis(lambda r: np.convolve(r, g, mode="same"), 1, a)
    return np.apply_along_axis(lambda c: np.convolve(c, g, mode="same"), 0, a)


def rounded(w, h, x0, y0, x1, y1, r, top_only):
    """Antialiased coverage (0-1) of a box, round top corners (and bottom ones unless top_only),
    at SS x, from a 4x finer mask."""
    f = 4
    im = Image.new("L", (w * SS * f, h * SS * f), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    X0, Y0, X1, Y1 = (int(round(v * SS * f)) for v in (x0, y0, x1, y1))
    if r > 0:
        d.rounded_rectangle([X0, Y0, X1 - 1, Y1 - 1], radius=int(round(r * SS * f)), fill=255)
        if top_only:
            d.rectangle([X0, (Y0 + Y1) // 2, X1 - 1, Y1 - 1], fill=255)
    else:
        d.rectangle([X0, Y0, X1 - 1, Y1 - 1], fill=255)
    im = im.resize((w * SS, h * SS), Image.BOX)
    return np.asarray(im, dtype=np.float32) / 255


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


def frame(prefix, fill, stroke, layers, shadow_scale, radius, pad=True):
    """9-slice frame rendered as SS x rasters (shadow, body, 1 px border), one <image> per piece
    whose bounds are exactly the piece: KSvg takes the 9-slice sizes from the element bounds."""
    pl, pr, pt, pb = (PAD_L, PAD_R, PAD_T, PAD_B) if pad else (0, 0, 0, 0)
    body = 2 * C + E
    w, h = pl + body + pr, pt + body + pb
    bx0, by0, bx1, by1 = pl, pt, pl + body, pt + body
    outer = rounded(w, h, bx0, by0, bx1, by1, radius, True)
    alpha = np.zeros_like(outer)
    if pad:
        base = rounded(w, h, bx0, by0, bx1, by1, radius, False)
        for dy, b, a in layers:
            m = blur(np.roll(base, int(round(dy * SS)), axis=0), b / 2 * SS)
            alpha = 1 - (1 - alpha) * (1 - a * shadow_scale * m)
    rgb = np.zeros(outer.shape + (3,), np.float32)
    if stroke:
        inner = rounded(w, h, bx0 + 1, by0 + 1, bx1 - 1, by1 - 1, max(radius - 1, 0), True)
        inner[(by1 - 1) * SS:, :] = 0                       # bottom border row
        col = hexrgb(stroke)[None, None] * (outer - inner)[..., None] + hexrgb(fill)[None, None] * inner[..., None]
    else:
        col = hexrgb(fill)[None, None] * outer[..., None]
    # premultiplied: window (outer) over shadow (black, alpha)
    a_tot = outer + alpha * (1 - outer)
    rgb = col  # black shadow adds no colour
    with np.errstate(invalid="ignore", divide="ignore"):
        straight = np.where(a_tot[..., None] > 0, rgb / np.maximum(a_tot[..., None], 1e-6), 0)
    rgba = np.concatenate([straight, a_tot[..., None]], axis=2)
    rgba = (np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8)
    cx, cy, ex, ey = pl + C, pt + C, pl + C + E, pt + C + E
    parts = {"topleft": (0, 0, cx, cy), "top": (cx, 0, ex, cy), "topright": (ex, 0, w, cy),
             "left": (0, cy, cx, ey), "center": (cx, cy, ex, ey), "right": (ex, cy, w, ey),
             "bottomleft": (0, ey, cx, h), "bottom": (cx, ey, ex, h), "bottomright": (ex, ey, w, h)}
    out = []
    for name, (x0, y0, x1, y1) in parts.items():
        tile = rgba[y0 * SS:y1 * SS, x0 * SS:x1 * SS]
        buf = io.BytesIO(); Image.fromarray(tile, "RGBA").save(buf, "PNG", optimize=True)
        href = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        out.append(f'<image id="{prefix}-{name}" x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
                   f'preserveAspectRatio="none" xlink:href="{href}"/>')
    return w, h, out


def _shift(image_tag, dy):
    """Moves an <image ... y="Y" ...> down by dy (no transforms: KSvg bounds stay exact)."""
    return re.sub(r' y="(\d+)"', lambda m: f' y="{int(m.group(1)) + dy}"', image_tag, count=1)


def decoration(s):
    pieces, W, H = [], 0, 0
    for prefix, fill, stroke, layers, pad, radius in (
            ("decoration", s["bar"], s["border"], SHADOWS["active"], True, R),
            ("decoration-inactive", s["bar_inactive"], s["border_inactive"], SHADOWS["inactive"], True, R),
            ("decoration-maximized", s["bar"], None, None, False, 0),
            ("decoration-maximized-inactive", s["bar_inactive"], None, None, False, 0)):
        w, h, out = frame(prefix, fill, stroke, layers, s["shadow"], radius, pad)
        # Stack the four frames vertically so their pieces do not overlap.
        pieces.append("\n".join(_shift(o, H) for o in out))
        W, H = max(W, w), H + h + 4
    # No hint-stretch-borders: KSvg tiles the edge pieces at their native size (their content is
    # uniform along the edge), while stretching resamples them and blurs the border off the
    # corners' pixel rows at fractional scales.
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}">\n'
            + "\n".join(pieces) + "\n</svg>\n")


def button(s, glyph, close):
    fg, inact = s["fg"], s["fg_inactive"]
    hover_bg = ("#c42b1c", 1) if close else (fg, 0.0605)
    pressed_bg = ("#c42b1c", 0.9) if close else (fg, 0.0419)
    hover_fg = "#ffffff" if close else fg
    states = {  # prefix: (background, glyph colour, glyph opacity)
        "active": (None, fg, 1), "hover": (hover_bg, hover_fg, 1), "pressed": (pressed_bg, hover_fg, 0.786),
        "inactive": (None, fg, 0.40), "hover-inactive": (hover_bg, hover_fg, 1),
        "pressed-inactive": (pressed_bg, hover_fg, 0.786),
        "deactivated": (None, inact, 0.5), "deactivated-inactive": (None, inact, 0.4),
    }
    parts = []
    gx, gy = (BW - 10) // 2, (BH - 10) // 2          # 18, 11: the reference's glyph position
    for state, (bg, col, op) in states.items():
        # Close sits in the window's round top-right corner: its plate follows the border's inner
        # curve (radius R - 1). Aurorae has no maximized button state, so a maximized window's
        # close plate keeps that curve too.
        r = R - 1
        shape = (f'<path d="M0 0H{BW - r}A{r} {r} 0 0 1 {BW} {r}V{BH}H0Z" ' if close else f'<rect width="{BW}" height="{BH}" ')
        rect = shape + (f'fill="{bg[0]}" fill-opacity="{bg[1]}"/>' if bg else 'fill="#000" fill-opacity="0"/>')
        if not bg:
            rect = f'<rect width="{BW}" height="{BH}" fill="#000" fill-opacity="0"/>'
        g = (f'<g transform="translate({gx} {gy})" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="1" '
             f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[glyph]}</g>')
        parts.append(f'<g id="{state}-center">{rect}{g}</g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{BW}" height="{BH}">\n' + "\n".join(parts) + "\n</svg>\n"


def rc(s):
    rgb = lambda h: ",".join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5))
    return f"""[General]
ActiveTextColor={rgb(s['fg'])}
InactiveTextColor={rgb(s['fg_inactive'])}
TitleAlignment=Left
TitleVerticalAlignment=Center
Animation=83
Shadow=true
HaloActive=false
HaloInactive=false

[Layout]
BorderLeft=1
BorderRight=1
BorderBottom=1
TitleEdgeTop=1
TitleEdgeBottom=0
TitleEdgeLeft=1
TitleEdgeRight=1
TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=0
TitleEdgeRightMaximized=0
TitleBorderLeft=12
TitleBorderRight=0
TitleHeight={TITLE}
ButtonWidth={BW}
ButtonHeight={BH}
ButtonSpacing=0
ButtonMarginTop=0
ExplicitButtonSpacer=0
PaddingTop={PAD_T}
PaddingBottom={PAD_B}
PaddingLeft={PAD_L}
PaddingRight={PAD_R}
"""


def main():
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "kwin/aurorae"
    for scheme, s in SCHEMES.items():
        name = f"Fenestra-{scheme}"
        out = dest / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "decoration.svg").write_text(decoration(s))
        for glyph in GLYPHS:
            (out / f"{glyph}.svg").write_text(button(s, glyph, glyph == "close"))
        (out / f"{name}rc").write_text(rc(s))
        (out / "metadata.json").write_text(json.dumps({
            "KPlugin": {"Id": name, "Name": f"Fenestra ({'dark' if scheme == 'Dark' else 'light'})",
                        "Description": "Fenestra window decoration", "License": "GPL-3.0-or-later",
                        "Version": "1.1"},
            "X-Plasma-API": "javascript",
        }, indent=2) + "\n")
        print(out)


if __name__ == "__main__":
    main()

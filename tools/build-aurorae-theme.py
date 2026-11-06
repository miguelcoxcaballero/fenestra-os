#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generates the Fenestra window decoration for KWin (Aurorae SVG themes Fenestra-Dark and
Fenestra-Light) into kwin/aurorae/. Values: design/tokens.json (window.*), the same as the GTK
caption buttons (desktop/gtk/caption-buttons-gtk4.css): 46 × 32 buttons, close #c42b1c on hover,
16 px glyph area, hover 6.05 % and pressed 4.19 % of the text colour, inactive glyphs at 36 %.
The glyphs are plain 1 px line art drawn here (no external artwork)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = json.loads((ROOT / "design/tokens.json").read_text())
BW, BH = T.get("window.button.width", 46), T.get("window.button.height", 32)
TITLE = T.get("window.title.height", 32)
R = T.get("window.radius", 8)
SCHEMES = {
    "Dark": {"bar": "#202020", "bar_inactive": "#2b2b2b", "fg": "#ffffff", "fg_inactive": "#9a9a9a", "border": "#3a3a3a"},
    "Light": {"bar": "#f3f3f3", "bar_inactive": "#f9f9f9", "fg": "#000000", "fg_inactive": "#8a8a8a", "border": "#c8c8c8"},
}
GLYPHS = {  # in a 10 × 10 box, centred in the button
    "minimize": '<path d="M0 5.5H10" />',
    "maximize": '<rect x="0.5" y="0.5" width="9" height="9" rx="1" />',
    "restore": '<rect x="0.5" y="2.5" width="7" height="7" rx="1" /><path d="M2.5 2.5V1.5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H7.5" />',
    "close": '<path d="M0.5 0.5L9.5 9.5M9.5 0.5L0.5 9.5" />',
}


def frame(prefix, w, h, fill, stroke, radius):
    """9-slice frame (Plasma FrameSvg element names) for a w × h decoration."""
    c = radius
    parts = {
        "topleft": (0, 0, c, c), "top": (c, 0, w - 2 * c, c), "topright": (w - c, 0, c, c),
        "left": (0, c, c, h - 2 * c), "center": (c, c, w - 2 * c, h - 2 * c), "right": (w - c, c, c, h - 2 * c),
        "bottomleft": (0, h - c, c, c), "bottom": (c, h - c, w - 2 * c, c), "bottomright": (w - c, h - c, c, c),
    }
    out = []
    for name, (x, y, ww, hh) in parts.items():
        out.append(f'<g id="{prefix}-{name}"><clipPath id="c-{prefix}-{name}"><rect x="{x}" y="{y}" width="{ww}" height="{hh}"/></clipPath>'
                   f'<rect clip-path="url(#c-{prefix}-{name})" x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{radius}" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="1"/></g>')
    return "\n".join(out)


def decoration(s):
    w, h = 200, 200
    body = [frame("decoration", w, h, s["bar"], s["border"], R),
            frame("decoration-inactive", w, h, s["bar_inactive"], s["border"], R),
            frame("decoration-maximized", w, h, s["bar"], s["bar"], 0),
            frame("decoration-maximized-inactive", w, h, s["bar_inactive"], s["bar_inactive"], 0)]
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">\n' + "\n".join(body) + "\n</svg>\n"


def button(s, glyph, close):
    states = {
        "active": (None, s["fg"], 1),
        "hover": ("#c42b1c" if close else s["fg"], "#ffffff" if close else s["fg"], 1),
        "pressed": ("#c42b1c" if close else s["fg"], "#ffffff" if close else s["fg"], 0.786),
        "inactive": (None, s["fg"], 0.3628),
        "deactivated": (None, s["fg_inactive"], 0.5),
    }
    alpha = {"hover": 1 if close else 0.0605, "pressed": 0.9 if close else 0.0419}
    parts = []
    for state, (bg, fg, opacity) in states.items():
        rect = f'<rect width="{BW}" height="{BH}" fill="{bg}" fill-opacity="{alpha.get(state, 1)}"/>' if bg else \
            f'<rect width="{BW}" height="{BH}" fill="none"/>'
        g = (f'<g transform="translate({(BW - 10) / 2} {(BH - 10) / 2})" fill="none" stroke="{fg}" stroke-width="1" '
             f'stroke-opacity="{opacity}" shape-rendering="crispEdges">{GLYPHS[glyph]}</g>')
        parts.append(f'<g id="{state}-center">{rect}{g}</g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{BW}" height="{BH}">\n' + "\n".join(parts) + "\n</svg>\n"


def rc(name, s):
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
TitleEdgeTop=0
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
PaddingTop=0
PaddingBottom=0
PaddingLeft=0
PaddingRight=0
"""


def main():
    for scheme, s in SCHEMES.items():
        name = f"Fenestra-{scheme}"
        out = ROOT / "kwin/aurorae" / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "decoration.svg").write_text(decoration(s))
        for glyph in GLYPHS:
            (out / f"{glyph}.svg").write_text(button(s, glyph, glyph == "close"))
        (out / f"{name}rc").write_text(rc(name, s))
        (out / "metadata.json").write_text(json.dumps({
            "KPlugin": {"Id": name, "Name": f"Fenestra ({'dark' if scheme == 'Dark' else 'light'})",
                        "Description": "Fenestra window decoration", "License": "GPL-3.0-or-later",
                        "Version": "1.0"},
            "X-Plasma-API": "javascript",
        }, indent=2) + "\n")
        print(out)


if __name__ == "__main__":
    main()

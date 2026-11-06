"""Scripted demo drawing (screenshots and smoke test): drives the real tools."""
from __future__ import annotations

import math

from .ribbon import hex_rgba


def stroke(win, tool, pts, color="#000000", size=None, opacity=1.0, button=1):
    win.set_tool(tool) if tool not in ("shape",) else None
    if color:
        win.set_primary(hex_rgba(color))
    if size is not None:
        win.set_size(size)
    win.set_opacity(opacity)
    t = win.tool
    t.press(pts[0][0], pts[0][1], button, 0, 1)
    for x, y in pts[1:]:
        t.drag(x, y, 0)
    t.release(pts[-1][0], pts[-1][1], button)


def shape(win, kind, box, line, fill, size=3, outline="solid", fill_style="solid"):
    win.set_shape(kind)
    win.outline_style = outline
    win.fill_style = fill_style if fill else "none"
    win.set_primary(hex_rgba(line))
    if fill:
        win.set_secondary(hex_rgba(fill))
    win.set_size(size)
    win.set_opacity(1.0)
    t = win.tool
    x0, y0, x1, y1 = box
    t.press(x0, y0, 1, 0, 1)
    for i in range(1, 6):
        t.drag(x0 + (x1 - x0) * i / 5, y0 + (y1 - y0) * i / 5, 0)
    t.release(x1, y1, 1)
    t.commit()


def wave(x0, y0, x1, amp=12, n=40, periods=1.5):
    return [(x0 + (x1 - x0) * i / n, y0 - amp * math.sin(i / n * periods * 2 * math.pi)) for i in range(n + 1)]


def draw_demo(win):
    doc = win.doc
    w, h = doc.width, doc.height
    sx, sy = w / 1152, h / 648
    # sky
    win.set_tool("fill")
    win.set_primary(hex_rgba("#99d9ea"))
    win.tool.press(10, 10, 1, 0, 1)
    win.tool.release(10, 10, 1)
    # sun, ground, hills
    shape(win, "oval", (900 * sx, 50 * sy, 1030 * sx, 180 * sy), "#ff7f27", "#fff200", 4)
    shape(win, "rectangle", (-10, 470 * sy, w + 10, h + 10), "#22b14c", "#22b14c", 1, outline="none")
    # house
    shape(win, "rectangle", (190 * sx, 300 * sy, 430 * sx, 480 * sy), "#3f2a1d", "#efe4b0", 3)
    shape(win, "triangle", (170 * sx, 175 * sy, 450 * sx, 300 * sy), "#3f2a1d", "#880015", 3)
    shape(win, "rectangle", (285 * sx, 380 * sy, 335 * sx, 480 * sy), "#3f2a1d", "#b97a57", 2)
    shape(win, "rectangle", (210 * sx, 330 * sy, 260 * sx, 370 * sy), "#3f2a1d", "#99d9ea", 2)
    shape(win, "rectangle", (360 * sx, 330 * sy, 410 * sx, 370 * sy), "#3f2a1d", "#99d9ea", 2)
    # tree: oil-brush trunk, watercolour crown
    win.brush = "oil"
    stroke(win, "brush", [(560 * sx, 480 * sy), (562 * sx, 400 * sy), (565 * sx, 330 * sy)], "#7a4a24", 18)
    win.brush = "watercolor"
    for cx, cy, r in ((565, 290, 60), (530, 320, 45), (605, 320, 45)):
        pts = [((cx + r * 0.6 * math.cos(a / 12 * 2 * math.pi)) * sx, (cy + r * 0.6 * math.sin(a / 12 * 2 * math.pi)) * sy)
               for a in range(13)]
        stroke(win, "brush", pts, "#22b14c", 40)
    # clouds (airbrush)
    win.brush = "airbrush"
    stroke(win, "brush", wave(80 * sx, 90 * sy, 300 * sx, 8, 30), "#ffffff", 40)
    stroke(win, "brush", wave(620 * sx, 120 * sy, 800 * sx, 6, 30), "#ffffff", 34)
    # shapes
    shape(win, "star5", (700 * sx, 360 * sy, 790 * sx, 450 * sy), "#ff7f27", "#fff200", 2)
    shape(win, "heart", (820 * sx, 370 * sy, 900 * sx, 450 * sy), "#880015", "#ed1c24", 2)
    shape(win, "callout_oval", (930 * sx, 300 * sy, 1110 * sx, 420 * sy), "#3f48cc", "#ffffff", 2)
    # brush samples along the bottom
    y = 540 * sy
    samples = [("brush", "#000000"), ("calligraphy_brush", "#3f48cc"), ("calligraphy_pen", "#880015"),
               ("airbrush", "#a349a4"), ("oil", "#ff7f27"), ("crayon", "#ed1c24"), ("marker", "#fff200"),
               ("natural_pencil", "#3f3f3f"), ("watercolor", "#00a2e8")]
    for i, (bid, col) in enumerate(samples):
        win.brush = bid
        x0 = (40 + i * 122) * sx
        stroke(win, "brush", wave(x0, y + 30 * sy, x0 + 105 * sx, 14 * sy, 30, 1), col, 10)
    win.set_tool("pencil")
    stroke(win, "pencil", [(40 * sx, 620 * sy), (1110 * sx, 620 * sy)], "#000000", 1)
    # text in the callout
    win.text_props.update({"size": 16, "bold": True, "family": win.text_props["family"]})
    t = win.tools["text"]
    win.set_tool("text")
    win.set_primary(hex_rgba("#3f48cc"))
    t.press(955 * sx, 330 * sy, 1, 0, 1)
    t.drag(1090 * sx, 370 * sy, 0)
    t.release(1090 * sx, 370 * sy, 1)
    t.insert("Hello, Paint!")
    t.commit()
    win.text_props["bold"] = False
    # restore pleasant defaults
    win.brush = "brush"
    win.set_primary(hex_rgba("#000000"))
    win.set_secondary(hex_rgba("#ffffff"))
    win.set_tool("brush")
    win.set_size(5)


def open_text(win):
    t = win.tools["text"]
    win.set_tool("text")
    t.press(120, 80, 1, 0, 1)
    t.drag(460, 140, 0)
    t.release(460, 140, 1)
    t.insert("Type here")


def open_selection(win):
    """Leave a moved selection and an editable shape on screen (screenshots)."""
    s = win.tools["select"]
    win.set_tool("select")
    s.press(560, 300, 1, 0, 1)
    s.drag(800, 470, 0)
    s.release(800, 470, 1)
    s.press(600, 350, 1, 0, 1)
    s.drag(640, 330, 0)
    s.release(640, 330, 1)

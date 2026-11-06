"""Generated artwork: placeholder app icons, screenshots and banner backgrounds.

Demo apps carry an (hue, glyph) pair; real apps without an icon get one derived from their id.
Everything is drawn here with cairo at runtime, so the repository ships no third-party
images and screenshots never show a real product.
"""
from __future__ import annotations

import colorsys
import math

import cairo
from gi.repository import Gdk, GLib

from . import util

GLYPHS = ["brush", "note", "wave", "grid", "pen", "star", "pin", "lock", "book", "code", "prompt", "prism", "drum",
          "bubble", "mail", "play", "box", "ring", "atom", "calc", "blocks", "moon", "knight", "flag", "leaf",
          "letters", "branch"]

_cache: dict = {}


def rgb(hue, light, sat=0.62):
    return colorsys.hls_to_rgb(hue % 1.0, light, sat)


def art_for(app) -> tuple:
    if app.art:
        return app.art
    h = util.stable_hash(app.app_id or app.name)
    return ((h % 360) / 360.0, GLYPHS[(h // 360) % len(GLYPHS)])


def _texture(surface: cairo.ImageSurface) -> Gdk.Texture:
    surface.flush()
    data = GLib.Bytes.new(bytes(surface.get_data()))
    return Gdk.MemoryTexture.new(surface.get_width(), surface.get_height(),
                                 Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, data, surface.get_stride())


def rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


# --------------------------------------------------------------------------- glyphs (unit box)

def _line(cr, pts, w=0.07):
    cr.set_line_width(w)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.stroke()


def _dot(cr, x, y, r):
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.fill()


def _ring(cr, x, y, r, w=0.07):
    cr.set_line_width(w)
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.stroke()


def _box(cr, x, y, w, h, r=0.04, fill=True, lw=0.07):
    rounded(cr, x, y, w, h, r)
    if fill:
        cr.fill()
    else:
        cr.set_line_width(lw)
        cr.stroke()


def glyph(cr, name):
    """Draw glyph `name` in the current source colour inside the unit square. Drawn in a group,
    so the cut-outs some glyphs make (OPERATOR_CLEAR) never punch through the background."""
    src = cr.get_source()
    cr.push_group()
    cr.set_source(src)
    _glyph(cr, name)
    cr.pop_group_to_source()
    cr.paint()


def _glyph(cr, name):
    if name == "brush":
        _line(cr, [(0.72, 0.22), (0.45, 0.52)], 0.09)
        cr.move_to(0.42, 0.5)
        cr.curve_to(0.3, 0.5, 0.28, 0.62, 0.26, 0.72)
        cr.curve_to(0.36, 0.74, 0.5, 0.7, 0.5, 0.58)
        cr.close_path()
        cr.fill()
    elif name == "note":
        _box(cr, 0.27, 0.24, 0.46, 0.52, 0.06, False)
        for y in (0.4, 0.5, 0.6):
            _line(cr, [(0.36, y), (0.64 if y < 0.6 else 0.52, y)], 0.05)
    elif name == "wave":
        cr.set_line_width(0.08)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(0.2, 0.55)
        cr.curve_to(0.33, 0.3, 0.42, 0.3, 0.5, 0.5)
        cr.curve_to(0.58, 0.7, 0.67, 0.7, 0.8, 0.45)
        cr.stroke()
        _dot(cr, 0.8, 0.45, 0.05)
    elif name == "grid":
        for i in range(3):
            for j in range(3):
                _box(cr, 0.25 + i * 0.18, 0.25 + j * 0.18, 0.14, 0.14, 0.02)
    elif name == "pen":
        _line(cr, [(0.3, 0.72), (0.68, 0.28)], 0.1)
        _line(cr, [(0.26, 0.76), (0.3, 0.72)], 0.05)
        _line(cr, [(0.28, 0.8), (0.75, 0.8)], 0.04)
    elif name == "star":
        cr.move_to(0.5, 0.2)
        for k in range(1, 10):
            r = 0.3 if k % 2 == 0 else 0.13
            a = -math.pi / 2 + k * math.pi / 5
            cr.line_to(0.5 + r * math.cos(a), 0.52 + r * math.sin(a))
        cr.close_path()
        cr.fill()
    elif name == "pin":
        cr.arc(0.5, 0.42, 0.18, math.pi * 0.85, math.pi * 2.15)
        cr.line_to(0.5, 0.8)
        cr.close_path()
        cr.fill()
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        _dot(cr, 0.5, 0.42, 0.07)
        cr.restore()
    elif name == "lock":
        _box(cr, 0.3, 0.46, 0.4, 0.32, 0.05)
        cr.set_line_width(0.07)
        cr.new_path()
        cr.move_to(0.37, 0.48)
        cr.line_to(0.37, 0.38)
        cr.arc(0.5, 0.38, 0.13, math.pi, 2 * math.pi)
        cr.line_to(0.63, 0.48)
        cr.stroke()
    elif name == "book":
        _line(cr, [(0.5, 0.3), (0.5, 0.74)], 0.05)
        _line(cr, [(0.5, 0.3), (0.24, 0.26), (0.24, 0.7), (0.5, 0.74), (0.76, 0.7), (0.76, 0.26), (0.5, 0.3)], 0.06)
    elif name == "code":
        _line(cr, [(0.38, 0.32), (0.22, 0.5), (0.38, 0.68)], 0.08)
        _line(cr, [(0.62, 0.32), (0.78, 0.5), (0.62, 0.68)], 0.08)
        _line(cr, [(0.55, 0.28), (0.45, 0.72)], 0.06)
    elif name == "prompt":
        _line(cr, [(0.26, 0.34), (0.42, 0.5), (0.26, 0.66)], 0.08)
        _line(cr, [(0.5, 0.68), (0.74, 0.68)], 0.08)
    elif name == "prism":
        cr.set_line_width(0.06)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for r, fill in ((0.28, False), (0.12, True)):
            cr.move_to(0.5, 0.5 - r)
            cr.line_to(0.5 + r * 0.8, 0.5)
            cr.line_to(0.5, 0.5 + r)
            cr.line_to(0.5 - r * 0.8, 0.5)
            cr.close_path()
            cr.fill() if fill else cr.stroke()
    elif name == "drum":
        cr.save()
        cr.translate(0.5, 0.36)
        cr.scale(1, 0.4)
        _ring(cr, 0, 0, 0.26, 0.15)
        cr.restore()
        _line(cr, [(0.24, 0.36), (0.24, 0.66)], 0.06)
        _line(cr, [(0.76, 0.36), (0.76, 0.66)], 0.06)
        cr.save()
        cr.translate(0.5, 0.66)
        cr.scale(1, 0.4)
        cr.set_line_width(0.15)
        cr.arc(0, 0, 0.26, 0, math.pi)
        cr.stroke()
        cr.restore()
    elif name == "bubble":
        _box(cr, 0.22, 0.26, 0.56, 0.38, 0.12)
        cr.move_to(0.32, 0.6)
        cr.line_to(0.3, 0.78)
        cr.line_to(0.48, 0.62)
        cr.close_path()
        cr.fill()
    elif name == "mail":
        _box(cr, 0.22, 0.3, 0.56, 0.4, 0.05, False)
        _line(cr, [(0.24, 0.33), (0.5, 0.53), (0.76, 0.33)], 0.06)
    elif name == "play":
        cr.move_to(0.38, 0.27)
        cr.line_to(0.74, 0.5)
        cr.line_to(0.38, 0.73)
        cr.close_path()
        cr.fill()
    elif name == "box":
        _line(cr, [(0.5, 0.22), (0.76, 0.35), (0.76, 0.65), (0.5, 0.78), (0.24, 0.65), (0.24, 0.35), (0.5, 0.22)], 0.06)
        _line(cr, [(0.24, 0.35), (0.5, 0.48), (0.76, 0.35)], 0.05)
        _line(cr, [(0.5, 0.48), (0.5, 0.78)], 0.05)
    elif name == "ring":
        cr.set_line_width(0.12)
        cr.arc(0.5, 0.5, 0.22, -math.pi / 2, math.pi * 0.9)
        cr.stroke()
        cr.save()
        cr.set_source_rgba(1, 1, 1, 0.5)
        cr.arc(0.5, 0.5, 0.22, math.pi * 0.95, math.pi * 1.45)
        cr.stroke()
        cr.restore()
    elif name == "atom":
        for a in (0, math.pi / 3, -math.pi / 3):
            cr.save()
            cr.translate(0.5, 0.5)
            cr.rotate(a)
            cr.scale(1, 0.38)
            _ring(cr, 0, 0, 0.28, 0.11)
            cr.restore()
        _dot(cr, 0.5, 0.5, 0.06)
    elif name == "calc":
        _box(cr, 0.3, 0.22, 0.4, 0.56, 0.06, False)
        _box(cr, 0.37, 0.3, 0.26, 0.1, 0.02)
        for i in range(2):
            for j in range(2):
                _dot(cr, 0.42 + i * 0.16, 0.52 + j * 0.13, 0.035)
    elif name == "blocks":
        for x, y in ((0.26, 0.56), (0.42, 0.56), (0.58, 0.56), (0.42, 0.4), (0.58, 0.24)):
            _box(cr, x, y, 0.14, 0.14, 0.02)
    elif name == "moon":
        cr.arc(0.5, 0.5, 0.25, 0, 2 * math.pi)
        cr.fill()
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.arc(0.6, 0.42, 0.22, 0, 2 * math.pi)
        cr.fill()
        cr.restore()
    elif name == "knight":
        cr.move_to(0.32, 0.76)
        cr.line_to(0.68, 0.76)
        cr.line_to(0.64, 0.66)
        cr.curve_to(0.66, 0.5, 0.64, 0.3, 0.46, 0.24)
        cr.line_to(0.42, 0.3)
        cr.line_to(0.3, 0.44)
        cr.line_to(0.34, 0.5)
        cr.line_to(0.46, 0.46)
        cr.line_to(0.38, 0.66)
        cr.close_path()
        cr.fill()
    elif name == "flag":
        _line(cr, [(0.3, 0.78), (0.3, 0.22)], 0.06)
        for i in range(3):
            for j in range(2):
                if (i + j) % 2 == 0:
                    cr.rectangle(0.32 + i * 0.13, 0.24 + j * 0.13, 0.13, 0.13)
        cr.fill()
        cr.rectangle(0.32, 0.24, 0.39, 0.26)
        cr.set_line_width(0.03)
        cr.stroke()
    elif name == "leaf":
        cr.move_to(0.26, 0.74)
        cr.curve_to(0.24, 0.4, 0.46, 0.24, 0.76, 0.24)
        cr.curve_to(0.76, 0.56, 0.6, 0.76, 0.26, 0.74)
        cr.fill()
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        _line(cr, [(0.3, 0.7), (0.62, 0.38)], 0.04)
        cr.restore()
    elif name == "letters":
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(0.34)
        cr.move_to(0.24, 0.62)
        cr.show_text("Aa")
    elif name == "branch":
        _line(cr, [(0.34, 0.26), (0.34, 0.74)], 0.06)
        _line(cr, [(0.34, 0.62), (0.34, 0.56), (0.66, 0.44), (0.66, 0.36)], 0.06)
        for x, y in ((0.34, 0.26), (0.34, 0.74), (0.66, 0.32)):
            _dot(cr, x, y, 0.07)
    else:
        _dot(cr, 0.5, 0.5, 0.2)


# --------------------------------------------------------------------------- icons

def draw_icon(cr, size, hue, name):
    top, bottom = rgb(hue, 0.58), rgb(hue + 0.04, 0.40)
    g = cairo.LinearGradient(0, 0, size, size)
    g.add_color_stop_rgb(0, *top)
    g.add_color_stop_rgb(1, *bottom)
    pad = size * 0.06
    rounded(cr, pad, pad, size - 2 * pad, size - 2 * pad, size * 0.2)
    cr.set_source(g)
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, 0.16)
    cr.set_line_width(max(1, size / 64))
    cr.stroke()
    cr.save()
    cr.scale(size, size)
    cr.set_source_rgb(1, 1, 1)
    glyph(cr, name)
    cr.restore()


def icon_texture(app, size: int, scale: int = 2) -> Gdk.Texture:
    hue, name = art_for(app)
    key = ("icon", hue, name, size, scale)
    if key not in _cache:
        px = size * scale
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, px, px)
        draw_icon(cairo.Context(s), px, hue, name)
        _cache[key] = _texture(s)
    return _cache[key]


# --------------------------------------------------------------------------- screenshots

def screenshot_texture(app, variant: int, w=960, h=600, dark=True) -> Gdk.Texture:
    hue, name = art_for(app)
    key = ("shot", hue, name, variant, w, h, dark)
    if key in _cache:
        return _cache[key]
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    g = cairo.LinearGradient(0, 0, w, h)
    g.add_color_stop_rgb(0, *rgb(hue, 0.30 if dark else 0.80, 0.45))
    g.add_color_stop_rgb(1, *rgb(hue + 0.08, 0.18 if dark else 0.68, 0.45))
    cr.set_source(g)
    cr.paint()
    # mock window
    mx, my, mw, mh = w * 0.07, h * 0.08, w * 0.86, h * 0.86
    cr.set_source_rgba(0, 0, 0, 0.25)
    rounded(cr, mx + 4, my + 8, mw, mh, 14)
    cr.fill()
    win_bg = (0.16, 0.16, 0.17) if dark else (0.98, 0.98, 0.98)
    ink = (1, 1, 1) if dark else (0.1, 0.1, 0.1)
    cr.set_source_rgb(*win_bg)
    rounded(cr, mx, my, mw, mh, 12)
    cr.fill()
    accent = rgb(hue, 0.55 if dark else 0.45, 0.7)
    # header
    cr.save()
    cr.translate(mx + 18, my + 14)
    hs = 30
    cr.save()
    cr.scale(hs / 64.0, hs / 64.0)
    draw_icon(cr, 64, hue, name)
    cr.restore()
    cr.restore()
    cr.set_source_rgba(*ink, 0.75)
    rounded(cr, mx + 60, my + 23, 140, 12, 6)
    cr.fill()
    cr.set_source_rgba(*ink, 0.08)
    cr.rectangle(mx, my + 56, mw, 1)
    cr.fill()
    body_y = my + 57
    body_h = mh - 57
    if variant == 0:  # sidebar + tiles
        cr.set_source_rgba(*ink, 0.04)
        cr.rectangle(mx, body_y, mw * 0.24, body_h)
        cr.fill()
        for i in range(6):
            cr.set_source_rgba(*(accent if i == 1 else ink), 0.9 if i == 1 else 0.28)
            rounded(cr, mx + 20, body_y + 22 + i * 38, mw * 0.24 - 46 - (i % 3) * 18, 12, 6)
            cr.fill()
        tw, th = (mw * 0.76 - 70) / 3, (body_h - 70) / 2
        for i in range(3):
            for j in range(2):
                x = mx + mw * 0.24 + 24 + i * (tw + 11)
                y = body_y + 24 + j * (th + 12)
                cr.set_source_rgba(*rgb(hue + 0.06 * (i + j * 3), 0.55, 0.5), 0.85)
                rounded(cr, x, y, tw, th, 10)
                cr.fill()
    elif variant == 1:  # canvas with the glyph
        cr.set_source_rgba(*ink, 0.05)
        rounded(cr, mx + 24, body_y + 22, mw - 48, body_h - 46, 10)
        cr.fill()
        cr.save()
        gs = min(mw, body_h) * 0.55
        cr.translate(mx + mw / 2 - gs / 2, body_y + body_h / 2 - gs / 2)
        cr.scale(gs, gs)
        cr.set_source_rgb(*accent)
        glyph(cr, name)
        cr.restore()
        for i in range(5):
            cr.set_source_rgba(*rgb(hue + i * 0.12, 0.55, 0.65), 1)
            cr.arc(mx + 52 + i * 34, my + mh - 46, 11, 0, 2 * math.pi)
            cr.fill()
    else:  # preferences list
        for i in range(5):
            y = body_y + 26 + i * 64
            if y + 52 > my + mh:
                break
            cr.set_source_rgba(*ink, 0.05)
            rounded(cr, mx + 40, y, mw - 80, 52, 8)
            cr.fill()
            cr.set_source_rgba(*ink, 0.6)
            rounded(cr, mx + 62, y + 15, 180 - i * 14, 10, 5)
            cr.fill()
            cr.set_source_rgba(*ink, 0.25)
            rounded(cr, mx + 62, y + 31, 260 - i * 20, 8, 4)
            cr.fill()
            on = i % 2 == 0
            cr.set_source_rgba(*(accent if on else ink), 1 if on else 0.35)
            rounded(cr, mx + mw - 120, y + 16, 40, 20, 10)
            cr.fill()
            cr.set_source_rgb(*win_bg)
            cr.arc(mx + mw - 120 + (30 if on else 10), y + 26, 6, 0, 2 * math.pi)
            cr.fill()
    _cache[key] = _texture(s)
    return _cache[key]


# --------------------------------------------------------------------------- banner background

def draw_banner(cr, w, h, hue, name, radius=8):
    rounded(cr, 0, 0, w, h, radius)
    cr.clip()
    g = cairo.LinearGradient(0, 0, w, h)
    g.add_color_stop_rgb(0, *rgb(hue, 0.30, 0.55))
    g.add_color_stop_rgb(0.6, *rgb(hue + 0.05, 0.22, 0.55))
    g.add_color_stop_rgb(1, *rgb(hue + 0.1, 0.16, 0.5))
    cr.set_source(g)
    cr.paint()
    # soft discs and a large faint glyph on the right
    for i, (fx, fy, fr) in enumerate(((0.82, 0.2, 0.42), (0.98, 0.9, 0.36), (0.6, 1.05, 0.25))):
        rg = cairo.RadialGradient(w * fx, h * fy, 0, w * fx, h * fy, h * fr * 1.6)
        rg.add_color_stop_rgba(0, *rgb(hue + 0.08 * i, 0.6, 0.7), 0.35)
        rg.add_color_stop_rgba(1, *rgb(hue, 0.5, 0.6), 0.0)
        cr.set_source(rg)
        cr.paint()
    cr.save()
    gs = h * 1.1
    cr.translate(w - gs * 0.78, h * 0.5 - gs / 2)
    cr.scale(gs, gs)
    cr.set_source_rgba(1, 1, 1, 0.07)
    glyph(cr, name)
    cr.restore()

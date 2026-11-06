# SPDX-License-Identifier: GPL-3.0-or-later
"""Appearance in the GNOME session: org.gnome.desktop.* GSettings (read by GNOME Shell, Mutter,
the fenestra-tray extension and, through the Settings portal, by GTK apps).

The Fenestra implementation (fenestra.py) reuses these functions as its GSettings mirror."""
from __future__ import annotations

import colorsys

from gi.repository import Gio

from ... import util
from . import gtkaccent

IFACE = "org.gnome.desktop.interface"
BG = "org.gnome.desktop.background"
FENESTRA = "org.fenestra.desktop"

FONT_KEYS = {"ui": "font-name", "document": "document-font-name", "monospace": "monospace-font-name"}
FITS = ("zoom", "scaled", "stretched", "wallpaper", "centered", "spanned", "none")


def supports(feature: str) -> bool:
    return feature != "wallpaper-spotlight"


# ---- mode and accent ----------------------------------------------------------------------

def color_scheme() -> str:
    """'dark' or 'light'."""
    return "dark" if util.gget(IFACE, "color-scheme", "default") == "prefer-dark" else "light"


def set_color_scheme(value: str) -> bool:
    dark = value in ("dark", "prefer-dark")
    ok = util.gset(IFACE, "color-scheme", "prefer-dark" if dark else "default")
    gtkaccent.sync(dark=dark)
    return ok


def nearest_gnome_accent(hexc: str) -> str:
    """GNOME accent-color enum value closest to '#rrggbb' (for libadwaita apps)."""
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.18:
        return "slate"
    hues = {"red": 0, "orange": 25, "yellow": 48, "green": 120, "teal": 178, "blue": 210, "purple": 270, "pink": 320}
    deg = h * 360
    return min(hues, key=lambda k: min(abs(deg - hues[k]), 360 - abs(deg - hues[k])))


def accent() -> str:
    """Custom accent '#RRGGBB' if set, else the GNOME accent name."""
    c = util.gget(FENESTRA, "accent-color-custom", "") or ""
    if len(c) == 7 and c.startswith("#"):
        return c.upper()
    return util.gget(IFACE, "accent-color", "blue") or "blue"


def accent_hex() -> str:
    """The accent as '#RRGGBB' (GNOME names map to their base colour)."""
    a = accent()
    return a if a.startswith("#") else gtkaccent.ENUM.get(a, gtkaccent.ENUM["blue"])[0].upper()


def set_accent(value: str) -> bool:
    """value: '#RRGGBB' (exact accent for the shell and GTK, nearest name for libadwaita) or a
    GNOME accent name."""
    if value.startswith("#"):
        hexc = value.upper()
        a = util.gset(FENESTRA, "accent-color-custom", hexc)
        b = util.gset(IFACE, "accent-color", nearest_gnome_accent(hexc))
    else:
        a = util.gset(IFACE, "accent-color", value)
        b = util.gset(FENESTRA, "accent-color-custom", "") if util.has_key(FENESTRA, "accent-color-custom") else True
    gtkaccent.sync()
    return a and b


# ---- wallpaper ----------------------------------------------------------------------------

def wallpaper(dark: bool = False) -> str | None:
    """Path of the desktop picture (None for none / a missing file)."""
    from .. import system_info
    return system_info.gnome_wallpaper_path(dark)


def set_wallpaper(path: str) -> bool:
    uri = Gio.File.new_for_path(path).get_uri()
    a = util.gset(BG, "picture-uri", uri)
    b = util.gset(BG, "picture-uri-dark", uri)
    return a and b


def background_mode() -> str:
    """'picture' or 'solid'."""
    return "solid" if util.gget(BG, "picture-options") == "none" else "picture"


def set_background_mode(mode: str) -> bool:
    return util.gset(BG, "picture-options", "none" if mode == "solid" else "zoom")


def wallpaper_fit() -> str | None:
    return util.gget(BG, "picture-options")


def set_wallpaper_fit(value: str) -> bool:
    return util.gset(BG, "picture-options", value)


# ---- themes, cursor, fonts, text, motion --------------------------------------------------

def _get(key, default=None):
    return util.gget(IFACE, key, default)


def gtk_theme():
    return _get("gtk-theme")


def set_gtk_theme(v) -> bool:
    ok = util.gset(IFACE, "gtk-theme", v)
    gtkaccent.sync()  # a Fenestra family gets its accent wrapper back
    return ok


def icon_theme():
    return _get("icon-theme")


def set_icon_theme(v) -> bool:
    return util.gset(IFACE, "icon-theme", v)


def cursor_theme():
    return _get("cursor-theme")


def set_cursor_theme(v) -> bool:
    return util.gset(IFACE, "cursor-theme", v)


def cursor_size():
    return _get("cursor-size", 24)


def set_cursor_size(v) -> bool:
    return util.gset(IFACE, "cursor-size", int(v))


def fonts() -> dict:
    """{'ui'|'document'|'monospace': Pango font description string or None}."""
    return {k: _get(sk) for k, sk in FONT_KEYS.items()}


def set_font(kind: str, desc: str) -> bool:
    return util.gset(IFACE, FONT_KEYS[kind], desc)


def font_rendering():
    """(antialiasing, hinting)."""
    return _get("font-antialiasing"), _get("font-hinting")


def set_font_rendering(antialiasing=None, hinting=None) -> bool:
    ok = True
    if antialiasing is not None:
        ok = util.gset(IFACE, "font-antialiasing", antialiasing) and ok
    if hinting is not None:
        ok = util.gset(IFACE, "font-hinting", hinting) and ok
    return ok


def text_scale() -> float:
    return _get("text-scaling-factor", 1.0)


def set_text_scale(v: float) -> bool:
    return util.gset(IFACE, "text-scaling-factor", float(v))


def animations() -> bool:
    return bool(_get("enable-animations", True))


def set_animations(on: bool) -> bool:
    return util.gset(IFACE, "enable-animations", bool(on))


def has(key: str) -> bool:
    """Whether the GSettings key behind a control exists (old setups may lack accent-color)."""
    return util.has_key(IFACE, key)


WATCH = ((IFACE, "color-scheme"), (IFACE, "accent-color"), (FENESTRA, "accent-color-custom"),
         (BG, "picture-uri"), (BG, "picture-uri-dark"), (BG, "picture-options"))


def connect(cb):
    """cb() on any appearance change made elsewhere."""
    for schema, key in WATCH:
        util.gconnect(schema, key, cb)


def sync() -> bool:
    """Regenerate derived files (GTK accent theme, caption buttons)."""
    return gtkaccent.sync()

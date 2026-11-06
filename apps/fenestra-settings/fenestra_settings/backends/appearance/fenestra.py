# SPDX-License-Identifier: GPL-3.0-or-later
"""Appearance in the Fenestra session (KWin + Fenestra Shell).

Fenestra Shell reads ~/.config/fenestra/shell.conf ([Appearance] ColorScheme, Accent,
Wallpaper, ReduceMotion) and applies changes live. GTK apps still take the colour scheme,
accent, themes, cursor, fonts and text scale from org.gnome.desktop.interface through the
Settings portal, so every change is mirrored there too (gnome.py), and the GTK accent theme
is regenerated (gtkaccent.py). KWin draws the cursor, so the cursor also goes to kcminputrc.
"""
from __future__ import annotations

import os
import re

from ... import util
from .. import shellconf
from . import gnome, gtkaccent

# Values the shell already defaults to when a key is missing (shellsettings.cpp).
DEFAULT_ACCENT = "#0078D4"
DEFAULT_WALLPAPER = "/usr/share/backgrounds/fenestra/fenestra-bloom-dark.jpg"

HEX = re.compile(r"#[0-9a-fA-F]{6}")

# Not stored by Fenestra Shell (yet): rows using them are hidden (backends/session.py).
UNSUPPORTED = {"wallpaper-fit"}


def supports(feature: str) -> bool:
    return feature not in UNSUPPORTED


# ---- mode and accent ----------------------------------------------------------------------

def color_scheme() -> str:
    v = shellconf.get("Appearance/ColorScheme")
    return v if v in ("dark", "light") else gnome.color_scheme()


def set_color_scheme(value: str) -> bool:
    scheme = "dark" if value in ("dark", "prefer-dark") else "light"
    a = shellconf.set("Appearance/ColorScheme", scheme)
    b = gnome.set_color_scheme(scheme)
    return a and b


def accent() -> str:
    """'#RRGGBB' from shell.conf, or the GNOME name when shell.conf holds that name's colour."""
    v = shellconf.get("Appearance/Accent")
    g = gnome.accent()
    if isinstance(v, str) and HEX.fullmatch(v):
        if not g.startswith("#") and gnome.accent_hex() == v.upper():
            return g
        return v.upper()
    return g


def set_accent(value: str) -> bool:
    if value.startswith("#"):
        hexc = value.upper()
    else:
        hexc = gtkaccent.ENUM.get(value, gtkaccent.ENUM["blue"])[0].upper()
    a = shellconf.set("Appearance/Accent", hexc)
    b = gnome.set_accent(value)
    return a and b


# ---- wallpaper ----------------------------------------------------------------------------

def _shell_wallpaper():
    v = shellconf.get("Appearance/Wallpaper")
    return v if isinstance(v, str) and v else None


def wallpaper(dark: bool = False) -> str | None:
    v = _shell_wallpaper()
    if v and v.startswith("/") and os.path.isfile(v):
        return v
    return gnome.wallpaper(dark)


def set_wallpaper(path: str) -> bool:
    a = shellconf.set("Appearance/Wallpaper", path)
    b = gnome.set_wallpaper(path)  # mirror: previews, Paint, apps that read the GNOME key
    return a and b


def background_mode() -> str:
    """'picture', 'solid' (a colour) or 'spotlight' (the shell's daily picture)."""
    v = _shell_wallpaper()
    if v == "spotlight":
        return "spotlight"
    if v and HEX.fullmatch(v):
        return "solid"
    return "picture"


def background_color() -> str:
    v = _shell_wallpaper()
    if v and HEX.fullmatch(v):
        return v.upper()
    c = util.gget(gnome.BG, "primary-color", "") or ""
    return c.upper() if HEX.fullmatch(c) else "#000000"


def set_background_mode(mode: str) -> bool:
    if mode == "spotlight":
        return shellconf.set("Appearance/Wallpaper", "spotlight")
    if mode == "solid":
        return shellconf.set("Appearance/Wallpaper", background_color())
    pic = gnome.wallpaper(False) or DEFAULT_WALLPAPER
    return shellconf.set("Appearance/Wallpaper", pic)


def wallpaper_fit():
    return None


def set_wallpaper_fit(_value) -> bool:
    return False


# ---- themes, cursor, fonts, text, motion --------------------------------------------------

gtk_theme = gnome.gtk_theme
set_gtk_theme = gnome.set_gtk_theme
icon_theme = gnome.icon_theme
set_icon_theme = gnome.set_icon_theme
cursor_theme = gnome.cursor_theme
cursor_size = gnome.cursor_size
fonts = gnome.fonts
set_font = gnome.set_font
font_rendering = gnome.font_rendering
set_font_rendering = gnome.set_font_rendering
text_scale = gnome.text_scale
set_text_scale = gnome.set_text_scale
animations = gnome.animations
has = gnome.has


def kcminputrc() -> str:
    return os.path.join(shellconf.config_dir(), "kcminputrc")


def _kwin_cursor(**values) -> bool:
    """KWin reads the cursor from kcminputrc [Mouse] and reloads on kconfig's change signal."""
    ok = shellconf.set_many({f"Mouse/{k}": v for k, v in values.items()}, file=kcminputrc())
    if ok and not util.SANDBOX and not util.READ_ONLY:
        try:
            from gi.repository import Gio, GLib
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.emit_signal(None, "/kcminputrc", "org.kde.kconfig.notify", "ConfigChanged",
                            GLib.Variant("(a{saay})", ({"Mouse": [k.encode() for k in values]},)))
        except Exception as e:  # noqa: BLE001 - no session bus: KWin picks it up next start
            util.log("kconfig notify failed", e)
    return ok


def set_cursor_theme(v) -> bool:
    a = gnome.set_cursor_theme(v)
    b = _kwin_cursor(cursorTheme=v)
    return a and b


def set_cursor_size(v) -> bool:
    a = gnome.set_cursor_size(v)
    b = _kwin_cursor(cursorSize=int(v))
    return a and b


def set_animations(on: bool) -> bool:
    a = gnome.set_animations(on)
    b = shellconf.set("Appearance/ReduceMotion", not on)
    return a and b


def connect(cb):
    gnome.connect(cb)
    shellconf.watch(cb)


def sync_from_shell() -> bool:
    """Bring the GSettings mirror (and so GTK apps) in line with shell.conf, e.g. after the
    shell changed the mode from its quick settings, then regenerate the GTK accent files."""
    if util.READ_ONLY and not util.SANDBOX:
        return False
    ok = True
    scheme = shellconf.get("Appearance/ColorScheme")
    if scheme in ("dark", "light") and scheme != gnome.color_scheme():
        ok = util.gset(gnome.IFACE, "color-scheme", "prefer-dark" if scheme == "dark" else "default") and ok
    acc = shellconf.get("Appearance/Accent")
    if isinstance(acc, str) and HEX.fullmatch(acc) and acc.upper() != gnome.accent_hex():
        ok = util.gset(gnome.FENESTRA, "accent-color-custom", acc.upper()) and ok
        ok = util.gset(gnome.IFACE, "accent-color", gnome.nearest_gnome_accent(acc)) and ok
    wp = _shell_wallpaper()
    if wp and wp.startswith("/") and os.path.isfile(wp) and wp != gnome.wallpaper(False):
        ok = gnome.set_wallpaper(wp) and ok
    return gtkaccent.sync() and ok


def sync() -> bool:
    return sync_from_shell()

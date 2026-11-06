# SPDX-License-Identifier: GPL-3.0-or-later
"""Appearance backend: mode, accent, wallpaper, themes, cursor, fonts, text size, motion.

The implementation follows the session (backends/session.py): gnome.py writes the GNOME
GSettings keys; fenestra.py writes Fenestra Shell's shell.conf and mirrors to the same keys
for GTK apps. Both regenerate the GTK accent theme (gtkaccent.py). The choice is made per
call, so tools can switch XDG_CURRENT_DESKTOP at runtime.
"""
from __future__ import annotations

from .. import session
from . import fenestra, gnome, gtkaccent  # noqa: F401  (gtkaccent re-exported for callers)

API = ("supports", "color_scheme", "set_color_scheme", "accent", "set_accent", "wallpaper", "set_wallpaper",
       "background_mode", "set_background_mode", "wallpaper_fit", "set_wallpaper_fit", "gtk_theme",
       "set_gtk_theme", "icon_theme", "set_icon_theme", "cursor_theme", "set_cursor_theme", "cursor_size",
       "set_cursor_size", "fonts", "set_font", "font_rendering", "set_font_rendering", "text_scale",
       "set_text_scale", "animations", "set_animations", "has", "connect", "sync")


def impl():
    return fenestra if session.is_fenestra() else gnome


def _forward(name):
    def call(*args, **kwargs):
        return getattr(impl(), name)(*args, **kwargs)
    call.__name__ = name
    call.__doc__ = getattr(gnome, name).__doc__
    return call


for _n in API:
    globals()[_n] = _forward(_n)
del _n

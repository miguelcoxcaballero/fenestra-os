# SPDX-License-Identifier: GPL-3.0-or-later
"""Taskbar / Start options of the desktop shell.

gnome.py: Dash to Panel, ArcMenu and org.fenestra.desktop (GNOME Shell session).
fenestra.py: Fenestra Shell's shell.conf (Fenestra session).
Options one shell does not have report supports(option) == False; their rows are hidden.
"""
from __future__ import annotations

from .. import session
from . import fenestra, gnome

API = ("supports", "alignment", "set_alignment", "search_mode", "set_search_mode", "weather", "set_weather",
       "taskbar_pins", "set_taskbar_pins", "start_pins", "set_start_pins", "reset_start_pins",
       "pinned_count")

# Settings' search-mode values (the GNOME org.fenestra.desktop taskbar-search enum).
SEARCH_MODES = ("hide", "icon", "icon-label", "box")


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

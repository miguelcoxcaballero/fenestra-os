# SPDX-License-Identifier: GPL-3.0-or-later
"""Notifications in the GNOME session: org.gnome.desktop.notifications (GNOME Shell).
Do not disturb is the inverse of show-banners."""
from __future__ import annotations

from ... import util

NOTIF = "org.gnome.desktop.notifications"


def supports(feature: str) -> bool:
    return True


def available() -> bool:
    return util.has_key(NOTIF, "show-banners")


def dnd() -> bool:
    return not bool(util.gget(NOTIF, "show-banners", True))


def set_dnd(on: bool) -> bool:
    return util.gset(NOTIF, "show-banners", not on)


def connect_dnd(cb):
    """cb() when do not disturb changes elsewhere."""
    util.gconnect(NOTIF, "show-banners", cb)


def lockscreen() -> bool:
    return bool(util.gget(NOTIF, "show-in-lock-screen", True))


def set_lockscreen(on: bool) -> bool:
    return util.gset(NOTIF, "show-in-lock-screen", bool(on))

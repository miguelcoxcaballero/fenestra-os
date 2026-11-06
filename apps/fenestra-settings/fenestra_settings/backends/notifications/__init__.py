# SPDX-License-Identifier: GPL-3.0-or-later
"""Notification policy: do not disturb, lock screen notifications, per-app switches.

gnome.py: org.gnome.desktop.notifications (GNOME Shell's notification daemon).
fenestra.py: Fenestra Shell's notification server, which keeps do not disturb in
shell.conf [Notifications] DoNotDisturb.
"""
from __future__ import annotations

from .. import session
from . import fenestra, gnome

API = ("supports", "available", "dnd", "set_dnd", "connect_dnd", "lockscreen", "set_lockscreen")


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

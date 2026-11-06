# SPDX-License-Identifier: GPL-3.0-or-later
"""Notifications in the Fenestra session: Fenestra Shell's notification server keeps do not
disturb in shell.conf [Notifications] DoNotDisturb (shell/src/services/notifications.cpp).

The shell has no lock-screen notification option and no per-app list yet; those rows are
hidden (backends/session.py)."""
from __future__ import annotations

from .. import shellconf

KEY = "Notifications/DoNotDisturb"
UNSUPPORTED = {"lock-screen-notifications", "notification-apps"}


def supports(feature: str) -> bool:
    return feature not in UNSUPPORTED


def available() -> bool:
    return True


def dnd() -> bool:
    return shellconf.get_bool(KEY, False)


def set_dnd(on: bool) -> bool:
    return shellconf.set(KEY, bool(on))


def connect_dnd(cb):
    shellconf.watch(cb)


def lockscreen() -> bool:
    return False


def set_lockscreen(_on: bool) -> bool:
    return False

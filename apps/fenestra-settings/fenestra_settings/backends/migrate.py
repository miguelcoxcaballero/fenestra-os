# SPDX-License-Identifier: GPL-3.0-or-later
"""«Migrar a KDE»: drives /usr/libexec/fenestra/fenestra-migrate (root through polkit) and reads
its state file. Settings never runs as root."""
from __future__ import annotations

import json
import os

from .. import util

HELPER = "/usr/libexec/fenestra/fenestra-migrate"
STATE = "/var/lib/fenestra/migrate.json"
PHASES = ["detect", "check", "backup", "simulate", "install", "register", "boottest", "available"]
PHASE_TEXT = {
    "detect": "Checking this device",
    "check": "Checking compatibility and free space",
    "backup": "Backing up system settings",
    "simulate": "Checking that the new desktop can be installed",
    "install": "Downloading and installing the new desktop",
    "register": "Adding the new desktop to the sign-in screen",
    "boottest": "Testing that the new desktop starts",
    "available": "Finishing",
}


def available() -> bool:
    return os.path.exists(HELPER)


def state() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def session_ok() -> bool:
    """The Fenestra session started successfully for this user at least once."""
    return os.path.exists(os.path.join(os.path.expanduser("~"), ".local/state/fenestra/session-ok"))


def installed() -> bool:
    return os.path.exists("/usr/share/wayland-sessions/fenestra.desktop")


def _run(args, callback):
    util.run_async(["pkexec", HELPER, *args], lambda ok, out, err: callback(ok, (err or out).strip()), mutating=True)


def check(callback):
    """Dry run: checks, backup preview and the download size, nothing installed."""
    _run(["run", "--dry-run"], callback)


def start(callback):
    _run(["run"], callback)


def set_default(callback):
    _run(["set-default", os.environ.get("USER", "")], callback)


def rollback(callback):
    _run(["rollback", "--remove-packages"], callback)

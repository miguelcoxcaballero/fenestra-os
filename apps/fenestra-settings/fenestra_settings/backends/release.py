"""Fedora release upgrades through fenestra-release-upgrade (see desktop/libexec)."""
from __future__ import annotations

import json
import os
import re
import subprocess

from gi.repository import GLib

from .. import util

STATE = "/var/lib/fenestra/release-upgrade.json"
LOG = "/var/log/fenestra-release-upgrade.log"
ROOT_HELPERS = ("/usr/libexec/fenestra/fenestra-release-upgrade",
                "/usr/local/libexec/fenestra/fenestra-release-upgrade")
USER_HELPER = os.path.join(GLib.get_home_dir(), ".local", "libexec", "fenestra", "fenestra-release-upgrade")


def helper():
    """The newest copy: a per-user copy updated after the system one wins (it re-installs itself
    as the root-owned copy when started through pkexec)."""
    found = [p for p in ROOT_HELPERS + (USER_HELPER,) if os.access(p, os.X_OK)]
    if not found:
        return None
    return max(found, key=lambda p: os.stat(p).st_mtime)


def root_helper():
    found = [p for p in ROOT_HELPERS if os.access(p, os.X_OK)]
    return max(found, key=lambda p: os.stat(p).st_mtime) if found else helper()


def kits():
    """Upgrade kits: prebuilt packages/SRPMs and system pieces for this machine."""
    cands = [os.path.join(GLib.get_user_data_dir(), "fenestra", "upgrade-kit"), "/usr/share/fenestra/upgrade"]
    return [c for c in cands if os.path.isdir(c)]


def current_version():
    # /usr/lib/os-release belongs to the installed fedora-release package; Fenestra's
    # rebranded /etc/os-release can lag behind right after an upgrade.
    for path in ("/usr/lib/os-release", "/etc/os-release"):
        try:
            for line in open(path):
                if line.startswith("VERSION_ID="):
                    return int(line.split("=", 1)[1].strip().strip('"'))
        except (OSError, ValueError):
            continue
    return 0


def available(callback):
    """callback({'current': n, 'next': m|None})"""
    h = helper()
    if util.DEMO or not h:
        nxt = os.environ.get("FENESTRA_DEMO_RELEASE")  # screenshots/tests only
        GLib.idle_add(lambda: (callback({"current": current_version(), "next": int(nxt) if nxt else None}), False)[1])
        return

    def done(ok, out, _err):
        try:
            callback(json.loads(out.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            callback({"current": current_version(), "next": None})
    util.run_async([h, "available"], done)


def state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def running():
    try:
        r = subprocess.run(["systemctl", "is-active", "fenestra-release-upgrade.service"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() in ("active", "activating")
    except (OSError, subprocess.SubprocessError):
        return False


def progress():
    """(percent, step text, last log line, warnings, error or None)"""
    pct, text, last, warns, err = 0, "", "", [], None
    try:
        with open(LOG, errors="replace") as f:
            lines = f.read().splitlines()[-4000:]
    except OSError:
        lines = []
    for line in lines:
        kind, _, rest = line.partition(" ")
        if kind == "STEP":
            m = re.match(r"(\d+)\s*(.*)", rest)
            if m:
                pct, text = int(m.group(1)), m.group(2)
        elif kind == "LOG":
            last = rest
        elif kind == "WARN":
            warns.append(rest)
        elif kind == "ERROR":
            err = rest
    return pct, text, last, warns, err


def start(target, callback):
    h = helper()
    if not h:
        GLib.idle_add(lambda: (callback(False, "fenestra-release-upgrade is not installed"), False)[1])
        return
    args = ["pkexec", h, "start", str(target)]
    for k in kits():
        args += ["--kit", k]
    args += ["--user", GLib.get_user_name()]
    util.run_async(args, lambda ok, out, err: callback(ok, (err or out).strip()), mutating=True)


def reboot(callback):
    util.run_async(["pkexec", root_helper(), "reboot"], lambda ok, out, err: callback(ok, (err or out).strip()),
                   mutating=True)

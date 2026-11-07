"""System updates through PackageKit (pkcon) and Flatpak."""
from __future__ import annotations

import json
import os
import re
import time

from gi.repository import GLib

from .. import util

STATE_FILE = os.path.join(GLib.get_user_state_dir(), "fenestra-settings", "state.json")


def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(d):
    if util.READ_ONLY:
        return
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(d, f)
    except OSError:
        pass


def get_state(key, default=None):
    return _load_state().get(key, default)


def set_state(key, value):
    d = _load_state()
    d[key] = value
    _save_state(d)


def last_checked():
    if util.DEMO:
        from . import demo
        return demo.last_checked()
    t = get_state("last_checked")
    return float(t) if t else None


class Update:
    def __init__(self, name, version, arch, repo, kind="rpm", severity="Normal"):
        self.name, self.version, self.arch, self.repo = name, version, arch, repo
        self.kind, self.severity = kind, severity

    @property
    def title(self):
        return f"{self.name} {self.version}"


_PKG_RE = re.compile(r"^(?P<sev>\w+)\s+(?P<nevra>\S+)\s*(?:\((?P<repo>[^)]*)\))?")
_NEVRA = re.compile(r"^(?P<name>.+)-(?P<ver>[^-]+-[^-]+)\.(?P<arch>[^.]+)$")


def parse_get_updates(text):
    ups = []
    started = False
    for line in text.splitlines():
        if line.startswith("Results:"):
            started = True
            continue
        if not started or not line.strip():
            continue
        m = _PKG_RE.match(line.strip())
        if not m:
            continue
        n = _NEVRA.match(m.group("nevra"))
        if n:
            ups.append(Update(n.group("name"), n.group("ver"), n.group("arch"), m.group("repo") or "",
                              severity=m.group("sev")))
    return ups


def check(callback, refresh=True):
    """Refresh metadata (unless read-only) and list updates: callback(ok, [Update], error)."""
    result = []

    def got_flatpak(ok, out, _e):
        if ok:
            for line in out.strip().splitlines():
                p = line.split("\t")
                if p and p[0]:
                    result.append(Update(p[1] if len(p) > 1 and p[1] else p[0],
                                         p[2] if len(p) > 2 else "", "", "flathub", kind="flatpak"))
        if not util.READ_ONLY:
            set_state("last_checked", time.time())
        callback(True, result, "")

    def got_updates(ok, out, err):
        if not ok and "no updates" not in (out + err).lower() and "There are no updates" not in out:
            if not out.strip():
                callback(False, [], err.strip() or "pkcon failed")
                return
        result.extend(parse_get_updates(out))
        if util.have("flatpak"):
            util.run_async(["flatpak", "remote-ls", "--updates", "--columns=application,name,version"],
                           got_flatpak)
        else:
            got_flatpak(False, "", "")

    def refreshed(_ok, _out, _err):
        util.run_async(["pkcon", "get-updates", "--plain"], got_updates)

    if not util.have("pkcon"):
        GLib.idle_add(lambda: (callback(False, [], "PackageKit (pkcon) is not installed"), False)[1])
        return
    if refresh and not util.READ_ONLY:
        # Refreshing the cache is not a system change but can take minutes; skip in tests.
        util.run_async(["pkcon", "refresh", "--plain"], refreshed)
    else:
        refreshed(True, "", "")


def download_and_prepare(callback):
    """Download updates and schedule the offline update: callback(ok, message)."""
    def triggered(ok, out, err):
        if ok:
            set_state("pending_restart", _boot_id() or True)
        callback(ok, (out + err).strip())

    def downloaded(ok, out, err):
        if not ok and "no packages" not in (out + err).lower():
            callback(False, (err or out).strip())
            return
        util.run_async(["pkcon", "offline-trigger", "--plain"], triggered, mutating=True)

    util.run_async(["pkcon", "update", "--only-download", "-y", "--plain"], downloaded, mutating=True)


def update_flatpaks(callback):
    util.run_async(["flatpak", "update", "-y", "--noninteractive"], lambda ok, o, e: callback(ok, e),
                   mutating=True)


def _boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            return f.read().strip()
    except OSError:
        return None


def offline_pending() -> bool:
    """An offline update is waiting for a restart: PackageKit's /system-update link exists, or this
    Settings scheduled one during the current boot. The flag of an earlier boot is stale (the
    restart happened: the update ran, or PackageKit dropped it), so it is cleared — otherwise
    "Restart required" stayed forever after restarting."""
    if util.DEMO:
        return False
    if os.path.exists("/system-update"):
        return True
    flag = get_state("pending_restart")
    if not flag:
        return False
    if flag is True or flag != _boot_id():
        set_state("pending_restart", False)
        return False
    return True


def reboot(callback=None):
    util.run_async(["systemctl", "reboot"], callback, mutating=True)


def history(callback):
    """Recent dnf transactions: callback([(date, summary)])."""
    if util.DEMO:
        from . import demo
        demo.later(callback, demo.update_history())
        return
    def done(ok, out, _e):
        rows = []
        if ok:
            for line in out.splitlines():
                p = [x.strip() for x in line.split("|")]
                if len(p) >= 4 and p[0].isdigit():  # dnf4 table
                    rows.append((p[2], p[1], p[4] if len(p) > 4 else ""))
                    continue
                m = re.match(r"^(\d+)\s+(.*?)\s+(\d{4}-\d\d-\d\d \d\d:\d\d(?::\d\d)?)\s+(.*?)\s*(\d+)?$",
                             line)
                if m:  # dnf5
                    rows.append((m.group(3), m.group(2), m.group(5) or ""))
        callback(rows[:30])
    if util.have("dnf"):
        util.run_async(["dnf", "history", "list"], done)
    else:
        GLib.idle_add(lambda: (callback([]), False)[1])

"""Fenestra updates from GitHub (Settings > Fenestra Update).

The installed build is described by /usr/share/fenestra/release.json (written
by build/build-overlay.sh). Checking only reads GitHub's public API; installing
runs /usr/libexec/fenestra/fenestra-update through pkexec, which downloads the
exact commit shown here, builds it and installs it (see that script).
"""
from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request

from gi.repository import GLib

from .. import util

RELEASE = "/usr/share/fenestra/release.json"
HELPER = "/usr/libexec/fenestra/fenestra-update"
API = "https://api.github.com/repos/{repo}"
_SHA = re.compile(r"^[0-9a-f]{40}$")


class FenestraUpdate:
    """A newer Fenestra build: commit, date and the changes since the installed one."""
    kind = "fenestra"
    name = "Fenestra"
    severity = "Normal"
    arch = ""
    repo = "GitHub"

    def __init__(self, commit, date, changes, total=None):
        self.commit, self.date, self.changes = commit, date, changes
        self.total = len(changes) if total is None else total

    @property
    def version(self):
        return f"{self.date[:10]} ({self.commit[:7]})"


def installed():
    """{'repo', 'branch', 'commit', 'date'} of this build, or None (not a Fenestra build)."""
    if util.DEMO:
        return {"repo": "fenestra/fenestra-os", "branch": "main", "commit": "0" * 40,
                "date": "2026-10-01T09:00:00Z"}
    try:
        with open(RELEASE) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", d.get("repo", "")):
        return None
    d.setdefault("branch", "main")
    return d


def available() -> bool:
    return installed() is not None and (util.DEMO or os.access(HELPER, os.X_OK))


def restart_pending() -> bool:
    """An update was installed after this boot (the desktop still runs the old one)."""
    if util.DEMO:
        return False
    try:
        mtime = os.stat(RELEASE).st_mtime
        with open("/proc/stat") as f:
            btime = next(int(line.split()[1]) for line in f if line.startswith("btime"))
    except (OSError, StopIteration, ValueError):
        return False
    return mtime > btime + 120  # files installed during the first boot don't count


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "fenestra-settings"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _subject(c):
    return (c.get("commit", {}).get("message") or "").splitlines()[0].strip()


def _changes(commits):
    """Commit subjects, newest first, without merge commits."""
    out = []
    for c in reversed(commits):
        s = _subject(c)
        if s and not s.startswith("Merge "):
            out.append(s)
    return out


def _demo():
    return FenestraUpdate("1" * 40, "2026-11-01T09:00:00Z", [
        "Settings: Reset this PC without reinstalling",
        "Taskbar: right-click menu with Task Manager and Taskbar settings",
        "Flyouts: the same 12 px gap above the taskbar",
    ])


def check(callback):
    """callback(ok, FenestraUpdate | None, error) on the main loop."""
    if util.DEMO:
        from . import demo
        demo.later(callback, True, _demo(), "")
        return
    rel = installed()
    if not rel:
        GLib.idle_add(lambda: (callback(False, None, "not a Fenestra build"), False)[1])
        return

    def work():
        try:
            api = API.format(repo=rel["repo"])
            head = _get(f"{api}/commits/{rel['branch']}")
            sha, date = head["sha"], head["commit"]["committer"]["date"]
            mine = rel.get("commit", "")
            if sha == mine:
                result = None
            elif _SHA.match(mine):
                try:
                    cmp = _get(f"{api}/compare/{mine}...{sha}")
                except urllib.error.HTTPError as e:
                    if e.code != 404:
                        raise
                    cmp = {"status": "diverged", "commits": [], "ahead_by": 0}
                if cmp.get("status") in ("identical", "behind"):
                    result = None
                else:
                    ch = _changes(cmp.get("commits", []))
                    result = FenestraUpdate(sha, date, ch, max(len(ch), cmp.get("ahead_by", 0)))
            else:
                # Built without a commit id (local build): offer the latest build.
                recent = _get(f"{api}/commits?sha={rel['branch']}&per_page=20")
                result = FenestraUpdate(sha, date, _changes(list(reversed(recent))))
            GLib.idle_add(lambda: (callback(True, result, ""), False)[1])
        except Exception as e:  # network, rate limit, unexpected JSON
            msg = str(getattr(e, "reason", "") or e)
            GLib.idle_add(lambda: (callback(False, None, msg), False)[1])

    threading.Thread(target=work, daemon=True).start()


def install(update, callback):
    """callback(ok, message). Needs an administrator (pkexec)."""
    if util.DEMO:
        from . import demo
        demo.later(callback, False, "demo mode")
        return
    util.run_async(["pkexec", HELPER, "apply", update.commit, update.date],
                   lambda ok, out, err: callback(ok, (err or out).strip()), mutating=True)

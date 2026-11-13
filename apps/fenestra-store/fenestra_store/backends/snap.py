"""Snap backend: the Snap Store through the snapd on this computer.

Search only: snapd has no catalogue to load, so snaps never show on Home or in the categories;
they are found by Store.search_packages (GET /v2/find on snapd's socket, what `snap find` asks).
Installing and removing run the `snap` command, which authorises through polkit like the terminal
does. The store never runs as root.
"""
from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import subprocess
import urllib.parse

from .. import util
from ..model import App, Screenshot, StoreError
from . import Backend

SOCKET = "/run/snapd.socket"
DESKTOP_DIR = "/var/lib/snapd/desktop/applications"


class _Conn(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=15)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(15)
        self.sock.connect(SOCKET)


def _get(path):
    c = _Conn()
    try:
        c.request("GET", path)
        r = c.getresponse()
        data = json.loads(r.read().decode("utf-8", "replace"))
    finally:
        c.close()
    if data.get("type") == "error":
        raise StoreError((data.get("result") or {}).get("message", "snapd error"))
    return data.get("result") or []


class SnapBackend(Backend):
    id = "snap"
    label = "Snap"

    def __init__(self):
        self.why = ""

    def available(self):
        if not shutil.which("snap") or not os.path.exists(SOCKET):
            self.why = "snapd is not installed"
            return False
        return True

    def load(self):
        return []

    def _installed(self):
        try:
            return {s.get("name"): s for s in _get("/v2/snaps")}
        except (OSError, ValueError, StoreError) as e:
            util.log("snap list failed", e)
            return {}

    def search(self, text, limit=60):
        try:
            found = _get("/v2/find?q=" + urllib.parse.quote(text))
        except (OSError, ValueError, StoreError) as e:
            util.log("snap find failed", e)
            return []
        installed = self._installed()
        apps = []
        for s in found[:limit]:
            name = s.get("name") or ""
            if not name:
                continue
            media = s.get("media") or []
            icon = next((m.get("url", "") for m in media if m.get("type") == "icon"), "")
            shots = [Screenshot(url=m.get("url", ""), large=m.get("url", "")) for m in media
                     if m.get("type") == "screenshot" and m.get("url")]
            here = installed.get(name)
            a = App(uid=f"snap:{name}", app_id=f"snap.{name}", backend=self.id, source="snap", packaging="snap",
                    name=s.get("title") or name, summary=s.get("summary") or "",
                    description=[p.strip() for p in (s.get("description") or "").split("\n\n") if p.strip()],
                    developer=(s.get("publisher") or {}).get("display-name", ""), categories=["utilities"],
                    kind="app", version=(here or s).get("version", ""), license=s.get("license", ""),
                    homepage=s.get("website") or s.get("contact") or "", icon_url=icon,
                    screenshots=shots, download_size=int(s.get("download-size") or 0),
                    installed=here is not None, ref=name, origin="snapcraft", pkgname=name,
                    details_loaded=True, search_only=True,
                    verified=(s.get("publisher") or {}).get("validation") in ("verified", "starred"),
                    project_urls=[u for k in ("source", "website", "issues")
                                  for u in ((s.get("links") or {}).get(k) or [])])
            a.sync_state()
            apps.append(a)
        return apps

    def launcher(self, app):
        from gi.repository import Gio
        try:
            for f in sorted(os.listdir(DESKTOP_DIR)):
                if f.startswith(app.ref + "_") and f.endswith(".desktop"):
                    return Gio.DesktopAppInfo.new_from_filename(os.path.join(DESKTOP_DIR, f))
        except OSError:
            pass
        return None

    def _run(self, args, progress, status):
        progress(None, status)
        try:
            r = subprocess.run(["snap", *args], capture_output=True, text=True, timeout=1800, check=False)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise StoreError(str(e)) from e
        return r

    def install(self, app, progress):
        r = self._run(["install", app.ref], progress, "Installing")
        if r.returncode != 0 and "--classic" in (r.stderr or ""):
            # Snaps without confinement (editors, compilers) must be asked for by name.
            r = self._run(["install", "--classic", app.ref], progress, "Installing")
        if r.returncode != 0:
            raise StoreError((r.stderr or r.stdout or "snap install failed").strip().splitlines()[-1])
        progress(1.0, "")

    def remove(self, app, progress):
        r = self._run(["remove", app.ref], progress, "Uninstalling")
        if r.returncode != 0:
            raise StoreError((r.stderr or r.stdout or "snap remove failed").strip().splitlines()[-1])
        progress(1.0, "")

    def update(self, app, progress):
        r = self._run(["refresh", app.ref], progress, "Updating")
        if r.returncode != 0:
            raise StoreError((r.stderr or r.stdout or "snap refresh failed").strip().splitlines()[-1])
        progress(1.0, "")

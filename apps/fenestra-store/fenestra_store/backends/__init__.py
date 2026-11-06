"""Software backends. Every backend implements `Backend`; `choose()` picks them at runtime.

* demo       deterministic in-memory catalogue (--demo-data, screenshots, tests)
* flatpak    libflatpak (gi Flatpak-1.0) + the remotes' AppStream data (Flathub)
* packagekit PackageKit (gi PackageKitGlib-1.0) + the system AppStream pool (Fedora RPMs)

All methods except `launch()` are called from worker threads and may block. `progress`
callbacks take (fraction 0..1 or None, status text) and may be called from any thread;
the Store marshals them to the UI thread. Root work only ever goes through PackageKit or
the flatpak system helper, both authorised by polkit; the store itself never runs as root.
"""
from __future__ import annotations

from .. import util
from ..model import App, Source


class Backend:
    id = "base"
    label = "base"

    def load(self) -> list[App]:
        """Full catalogue (with installed state and versions)."""
        raise NotImplementedError

    def refresh_updates(self, apps: list[App]) -> dict[str, str]:
        """uid -> new version for installed apps of this backend that can be updated."""
        return {}

    def details(self, app: App) -> None:
        """Fill in slow fields (sizes, permissions, license...) in place."""

    def install(self, app: App, progress) -> None:
        raise NotImplementedError

    def remove(self, app: App, progress) -> None:
        raise NotImplementedError

    def update(self, app: App, progress) -> None:
        raise NotImplementedError

    def launch(self, app: App) -> bool:
        """UI thread. Start the installed app."""
        from gi.repository import Gio, GLib
        did = app.desktop_id or f"{app.app_id}.desktop"
        try:
            info = Gio.DesktopAppInfo.new(did if did.endswith(".desktop") else did + ".desktop")
        except TypeError:
            info = None
        if info is None:
            return False
        try:
            return info.launch([], None)
        except GLib.Error:
            return False

    def sources(self) -> list[Source]:
        return []

    def set_source_enabled(self, source: Source, enabled: bool) -> None:
        raise NotImplementedError


def choose(demo: bool) -> list[Backend]:
    """Backends for this run. Real backends are optional: missing typelibs/daemons are skipped."""
    if demo:
        from .demo import DemoBackend
        return [DemoBackend()]
    found = []
    for modname, clsname in (("flatpak", "FlatpakBackend"), ("packagekit", "PackageKitBackend")):
        try:
            mod = __import__(f"fenestra_store.backends.{modname}", fromlist=[clsname])
            b = getattr(mod, clsname)()
            if b.available():
                found.append(b)
            else:
                util.log("backend unavailable:", modname, getattr(b, "why", ""))
        except (ImportError, ValueError) as e:  # typelib missing: gi raises ValueError
            util.log("backend not loaded:", modname, e)
    return found

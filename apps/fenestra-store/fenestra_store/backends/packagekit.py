"""PackageKit backend for Fedora RPM applications.

The catalogue is the system AppStream pool (Fedora's appstream-data: names, icons,
descriptions, screenshots); installed state, versions, updates and every change go through
the PackageKit daemon (gi PackageKitGlib-1.0), which authorises with polkit. The store never
runs as root and never calls rpm/dnf directly.
"""
from __future__ import annotations

import gi

gi.require_version("PackageKitGlib", "1.0")
from gi.repository import Gio, GLib, PackageKitGlib as PK  # noqa: E402

from .. import util  # noqa: E402
from ..model import App, Screenshot, Source, StoreError, map_categories  # noqa: E402
from . import Backend, appstream  # noqa: E402

BUS_NAME = "org.freedesktop.PackageKit"

_STATUS_NAMES = {
    "DOWNLOAD": "Downloading", "DOWNLOAD_PACKAGELIST": "Preparing", "DOWNLOAD_REPOSITORY": "Preparing",
    "INSTALL": "Installing", "REMOVE": "Uninstalling", "UPDATE": "Updating", "CLEANUP": "Finishing",
    "WAITING_FOR_AUTH": "Waiting for authorisation", "WAITING_FOR_LOCK": "Waiting", "WAIT": "Waiting",
    "QUERY": "Preparing", "INFO": "Preparing", "DEP_RESOLVE": "Preparing", "SETUP": "Preparing",
    "LOADING_CACHE": "Preparing", "SIG_CHECK": "Checking", "TEST_COMMIT": "Checking", "COMMIT": "Installing",
    "FINISHED": "Finishing", "RUNNING": "Preparing",
}
# PackageKit status -> English status key (names differ a little between PackageKit versions)
STATUS = {getattr(PK.StatusEnum, k): v for k, v in _STATUS_NAMES.items() if hasattr(PK.StatusEnum, k)}


def _filters(s):
    return PK.filter_bitfield_from_string(s)


def _trusted():
    return PK.transaction_flag_bitfield_from_string("only-trusted")


def _check(results):
    err = results.get_error_code() if results is not None else None
    if err is not None:
        raise StoreError(err.get_details() or PK.error_enum_to_string(err.get_code()))
    return results


def pretty_version(v: str) -> str:
    """'1:51.0.1-1.fc45' -> '51.0.1' (epoch and release are noise for people)."""
    v = v.split(":", 1)[-1]
    return v.rsplit("-", 1)[0] if "-" in v else v


class PackageKitBackend(Backend):
    id = "packagekit"
    label = "PackageKit"

    def __init__(self):
        self.why = ""
        self.client = PK.Client()
        self.client.set_interactive(True)     # polkit may ask for a password
        self.client.set_background(False)
        self._by_pkg = {}
        self._update_ids = {}

    def available(self):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            names = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                  "ListActivatableNames", None, GLib.VariantType("(as)"),
                                  Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
            running = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                    "NameHasOwner", GLib.Variant("(s)", (BUS_NAME,)), GLib.VariantType("(b)"),
                                    Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
        except GLib.Error as e:
            self.why = e.message
            return False
        if BUS_NAME not in names and not running:
            self.why = "PackageKit is not installed"
            return False
        return True

    # ------------------------------------------------------------------ progress
    @staticmethod
    def _progress_cb(progress):
        def cb(p, ptype, *_a):
            if ptype == PK.ProgressType.PERCENTAGE:
                pct = p.get_property("percentage")
                if 0 <= pct <= 100:
                    progress(min(pct / 100.0, 0.99), STATUS.get(p.get_property("status"), "Installing"))
            elif ptype == PK.ProgressType.STATUS:
                progress(None, STATUS.get(p.get_property("status"), "Preparing"))
        return cb

    @staticmethod
    def _quiet(*_a):
        pass

    # ------------------------------------------------------------------ catalogue
    def load(self):
        comps = appstream.system_components()
        names = sorted({c.pkgname for c in comps})
        installed = {}
        for i in range(0, len(names), 400):     # keep each D-Bus message reasonable
            try:
                res = _check(self.client.resolve(_filters("installed"), names[i:i + 400], None, self._quiet, None))
                for pkg in res.get_package_array():
                    installed[pkg.get_name()] = pkg
            except (GLib.Error, StoreError) as e:
                util.log("resolve failed", e)
                break
        apps, seen = [], set()
        for c in comps:
            if c.pkgname in seen or (c.bundle and not c.pkgname):
                continue
            seen.add(c.pkgname)
            cats = map_categories(c.categories)
            pkg = installed.get(c.pkgname)
            a = App(uid=f"packagekit:{c.pkgname}", app_id=c.id.removesuffix(".desktop"), backend=self.id,
                    source="fedora", packaging="rpm", name=c.name, summary=c.summary, description=c.description,
                    developer=c.developer, categories=cats, kind="game" if "games" in cats else "app",
                    version=pretty_version(pkg.get_version()) if pkg else c.version, license=c.license, homepage=c.homepage,
                    keywords=c.keywords, icon_path=c.icon_path, icon_url=c.icon_url, icon_name=c.icon_name,
                    screenshots=[Screenshot(url=u, caption=cap) for u, cap in c.screenshots],
                    released=c.released, ref=pkg.get_id() if pkg else c.pkgname, origin=c.origin or "fedora",
                    desktop_id=c.desktop_id or c.id, installed=pkg is not None, pkgname=c.pkgname)
            a.sync_state()
            apps.append(a)
        self._by_pkg = {a.pkgname: a for a in apps}
        return apps

    def _resolve_one(self, name, filters):
        res = _check(self.client.resolve(_filters(filters), [name], None, self._quiet, None))
        pkgs = res.get_package_array()
        if not pkgs:
            raise StoreError("Package not found: %s" % name)
        return pkgs[0].get_id()

    def details(self, app):
        try:
            pid = self._resolve_one(app.pkgname, "installed" if app.installed else "~installed;newest;arch")
            res = _check(self.client.get_details([pid], None, self._quiet, None))
            for d in res.get_details_array():
                size = d.get_size()
                if app.installed:
                    app.installed_size = size
                else:
                    app.download_size = size
                    if hasattr(d, "get_download_size") and d.get_download_size() not in (0, GLib.MAXUINT64):
                        app.download_size = d.get_download_size()
                app.license = app.license or d.get_license()
                app.homepage = app.homepage or d.get_url()
        except (GLib.Error, StoreError) as e:
            util.log("details failed", app.pkgname, e)

    # ------------------------------------------------------------------ transactions
    def install(self, app, progress):
        try:
            progress(None, "Preparing")
            pid = self._resolve_one(app.pkgname, "~installed;newest;arch")
            _check(self.client.install_packages(_trusted(), [pid], None, self._progress_cb(progress), None))
        except GLib.Error as e:
            raise StoreError(e.message) from e
        app.ref = pid
        progress(1.0, "")

    def remove(self, app, progress):
        try:
            progress(None, "Preparing")
            pid = self._resolve_one(app.pkgname, "installed")
            # allow_deps: remove what depends on it, autoremove: keep unrelated leftovers
            _check(self.client.remove_packages(_trusted(), [pid], True, False, None,
                                               self._progress_cb(progress), None))
        except GLib.Error as e:
            raise StoreError(e.message) from e
        progress(1.0, "")

    def update(self, app, progress):
        try:
            progress(None, "Preparing")
            pid = self._update_ids.get(app.pkgname) or self._resolve_one(app.pkgname, "newest;arch")
            _check(self.client.update_packages(_trusted(), [pid], None, self._progress_cb(progress), None))
        except GLib.Error as e:
            raise StoreError(e.message) from e
        self._update_ids.pop(app.pkgname, None)
        progress(1.0, "")

    def refresh_updates(self, apps):
        try:
            self.client.refresh_cache(False, None, self._quiet, None)
        except GLib.Error as e:
            util.log("refresh cache failed", e.message)
        try:
            res = _check(self.client.get_updates(_filters("none"), None, self._quiet, None))
        except (GLib.Error, StoreError) as e:
            util.log("get updates failed", e)
            return {}
        found = {}
        self._update_ids = {}
        for pkg in res.get_package_array():
            a = self._by_pkg.get(pkg.get_name())
            if a is not None and a.installed:
                found[a.uid] = pretty_version(pkg.get_version())
                self._update_ids[pkg.get_name()] = pkg.get_id()
        return found

    # ------------------------------------------------------------------ repositories
    def sources(self):
        try:
            res = _check(self.client.get_repo_list(_filters("none"), None, self._quiet, None))
        except (GLib.Error, StoreError) as e:
            util.log("repo list failed", e)
            return []
        out = []
        for r in res.get_repo_detail_array():
            rid = r.get_id()
            if rid.endswith(("-debuginfo", "-source", "-debug")):
                continue
            out.append(Source(rid, self.id, "fedora", r.get_description() or rid, rid, r.get_enabled(), True))
        return out

    def set_source_enabled(self, source, enabled):
        try:
            _check(self.client.repo_enable(source.id, enabled, None, self._quiet, None))
        except GLib.Error as e:
            raise StoreError(e.message) from e

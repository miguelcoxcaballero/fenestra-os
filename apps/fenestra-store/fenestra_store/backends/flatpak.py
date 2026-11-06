"""Flatpak backend: libflatpak (gi Flatpak-1.0) for installations, remotes and transactions;
the remotes' AppStream data (appstream.py) for the catalogue.

System installations are changed through flatpak-system-helper, which asks polkit; the store
itself never needs root. Remotes named or pointing at Flathub get the "Flathub" badge, Fedora's
own Flatpak registry gets "Fedora".
"""
from __future__ import annotations

import os

import gi

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, GLib  # noqa: E402

from .. import util  # noqa: E402
from ..model import App, Screenshot, Source, StoreError, map_categories  # noqa: E402
from . import Backend, appstream  # noqa: E402

FLATHUB_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"

STATUS = {"downloading": "Downloading", "install": "Installing", "update": "Updating",
          "uninstall": "Uninstalling"}

# [Context] keys of a Flatpak metadata file -> permission keys of model.PERMISSIONS
_FS = {"home": "home", "": "home", "host": "host", "host-os": "host", "xdg-download": "downloads",
       "xdg-documents": "documents", "xdg-pictures": "pictures", "xdg-music": "music", "xdg-videos": "videos"}


def parse_permissions(keyfile_text: str) -> list[str]:
    kf = GLib.KeyFile()
    try:
        kf.load_from_data(keyfile_text, len(keyfile_text.encode()), GLib.KeyFileFlags.NONE)
    except GLib.Error:
        return []

    def lst(group, key):
        try:
            return [x for x in kf.get_string_list(group, key) if x]
        except GLib.Error:
            return []
    perms = []
    shared, sockets, devices = lst("Context", "shared"), lst("Context", "sockets"), lst("Context", "devices")
    if "network" in shared:
        perms.append("network")
    for fs in lst("Context", "filesystems"):
        if fs.startswith("!"):
            continue
        ro = fs.endswith(":ro")
        base = fs.split(":")[0].split("/")[0].lstrip("~")
        p = "host-ro" if base == "host" and ro else _FS.get(base)
        if p and p not in perms:
            perms.append(p)
    if "all" in devices:
        perms.append("devices")
    elif "dri" in devices:
        perms.append("dri")
    if "pulseaudio" in sockets:
        perms.append("audio")
    if "x11" in sockets and "fallback-x11" not in sockets:
        perms.append("x11")
    if "wayland" in sockets or "fallback-x11" in sockets:
        perms.append("wayland")
    if "bluetooth" in shared or "bluetooth" in devices:
        perms.append("bluetooth")
    if "system-bus" in sockets:
        perms.append("system-bus")
    if "session-bus" in sockets:
        perms.append("session-bus")
    try:
        talks = kf.get_keys("Session Bus Policy")[0]
        if any(k.startswith("ca.desrt.dconf") for k in talks):
            perms.append("settings")
    except GLib.Error:
        pass
    return perms or ["none"]


def _source_kind(remote) -> str:
    name = (remote.get_name() or "").lower()
    url = (remote.get_url() or "").lower()
    if "fedora" in name or "fedoraproject.org" in url:
        return "fedora"
    return "flathub"


class FlatpakBackend(Backend):
    id = "flatpak"
    label = "Flatpak"

    def __init__(self):
        self.why = ""
        self.installations = []
        try:
            self.installations += list(Flatpak.get_system_installations(None))
        except GLib.Error as e:
            self.why = e.message
        try:
            self.installations.append(Flatpak.Installation.new_user(None))
        except GLib.Error as e:
            self.why = self.why or e.message
        self.arch = Flatpak.get_default_arch()
        self._inst = {i.get_id(): i for i in self.installations}
        self._apps_by_ref = {}

    def available(self):
        return bool(self.installations)

    # ------------------------------------------------------------------ catalogue
    def _appstream_file(self, inst, remote):
        d = remote.get_appstream_dir(self.arch)
        path = d.get_path() if d else ""
        for name in ("appstream.xml.gz", "appstream.xml"):
            p = os.path.join(path, name)
            if os.path.isfile(p):
                return path, p
        return path, ""

    def load(self):
        apps = {}
        for inst in self.installations:
            iid = inst.get_id()
            try:
                remotes = list(inst.list_remotes(None))
            except GLib.Error:
                remotes = []
            for remote in remotes:
                if remote.get_disabled() or remote.get_noenumerate():
                    continue
                rname = remote.get_name()
                base, xml = self._appstream_file(inst, remote)
                if not xml and not util.READ_ONLY:
                    try:  # first run: fetch the remote's AppStream data (no root needed)
                        inst.update_appstream_sync(rname, self.arch, None)
                        base, xml = self._appstream_file(inst, remote)
                    except GLib.Error as e:
                        util.log("appstream update failed", rname, e.message)
                if not xml:
                    continue
                kind = _source_kind(remote)
                for c in appstream.parse_file(xml, os.path.join(base, "icons"), rname):
                    ref = c.bundle or f"app/{c.id.removesuffix('.desktop')}/{self.arch}/stable"
                    uid = f"flatpak:{iid}:{rname}:{ref}"
                    apps[uid] = self._from_component(c, uid, ref, iid, rname, kind)
            try:
                installed = list(inst.list_installed_refs_by_kind(Flatpak.RefKind.APP, None))
            except GLib.Error:
                installed = []
            for ir in installed:
                ref = ir.format_ref()
                uid = f"flatpak:{iid}:{ir.get_origin()}:{ref}"
                a = apps.get(uid)
                if a is None:  # installed from a remote without (or with disabled) AppStream data
                    r = inst.get_remote_by_name(ir.get_origin(), None) if ir.get_origin() else None
                    a = App(uid=uid, app_id=ir.get_name(), backend=self.id,
                            source=_source_kind(r) if r else "flathub", packaging="flatpak",
                            name=ir.get_appdata_name() or ir.get_name(), summary=ir.get_appdata_summary() or "",
                            license=ir.get_appdata_license() or "", ref=ref, origin=ir.get_origin() or "",
                            desktop_id=f"{ir.get_name()}.desktop", categories=["utilities"])
                    apps[uid] = a
                a.installed = True
                a.version = ir.get_appdata_version() or a.version
                a.installed_size = ir.get_installed_size()
                a.sync_state()
        self._apps_by_ref = {(a.uid.split(":")[1], a.origin, a.ref): a for a in apps.values()}
        return list(apps.values())

    def _from_component(self, c, uid, ref, iid, remote, kind):
        cats = map_categories(c.categories)
        return App(uid=uid, app_id=c.id.removesuffix(".desktop"), backend=self.id, source=kind, packaging="flatpak",
                   name=c.name, summary=c.summary, description=c.description, developer=c.developer,
                   categories=cats, kind="game" if "games" in cats else "app", version=c.version,
                   license=c.license, homepage=c.homepage, keywords=c.keywords, icon_path=c.icon_path,
                   icon_url=c.icon_url, icon_name=c.icon_name,
                   screenshots=[Screenshot(url=u, caption=cap) for u, cap in c.screenshots],
                   released=c.released, ref=ref, origin=remote,
                   desktop_id=c.desktop_id or f"{c.id.removesuffix('.desktop')}.desktop")

    def _installation(self, app) -> Flatpak.Installation:
        return self._inst[app.uid.split(":")[1]]

    # ------------------------------------------------------------------ details
    def details(self, app):
        inst = self._installation(app)
        ref = Flatpak.Ref.parse(app.ref)
        meta = None
        if app.installed:
            try:
                ir = inst.get_installed_ref(ref.get_kind(), ref.get_name(), ref.get_arch(), ref.get_branch(), None)
                meta = ir.load_metadata(None)
                app.installed_size = ir.get_installed_size()
            except GLib.Error:
                pass
        if not app.installed or not app.download_size:
            try:
                ok, dl, inst_size = inst.fetch_remote_size_sync(app.origin, ref, None)
                if ok:
                    app.download_size = dl
                    app.installed_size = app.installed_size or inst_size
            except (GLib.Error, TypeError, ValueError) as e:
                util.log("size failed", app.ref, e)
        if meta is None:
            try:
                meta = inst.fetch_remote_metadata_sync(app.origin, ref, None)
            except GLib.Error as e:
                util.log("metadata failed", app.ref, e.message)
        if meta is not None:
            app.permissions = parse_permissions(bytes(meta.get_data()).decode("utf-8", "replace"))

    # ------------------------------------------------------------------ transactions
    def _run(self, app, progress, add):
        inst = self._installation(app)
        try:
            t = Flatpak.Transaction.new_for_installation(inst, None)
        except GLib.Error as e:
            raise StoreError(e.message) from e
        state = {"n": 1, "done": 0, "error": ""}

        def ready(tr):
            state["n"] = max(1, len(tr.get_operations()))
            return True

        def new_op(_tr, op, prog):
            prog.set_update_frequency(150)
            kind = op.get_operation_type()
            label = {Flatpak.TransactionOperationType.INSTALL: "Installing",
                     Flatpak.TransactionOperationType.UPDATE: "Updating",
                     Flatpak.TransactionOperationType.UNINSTALL: "Uninstalling"}.get(kind, "Preparing")

            def changed(p):
                frac = (state["done"] + p.get_progress() / 100.0) / state["n"]
                text = "Downloading" if p.get_status() and "ownload" in (p.get_status() or "") else label
                progress(min(frac, 0.99), text)
            prog.connect("changed", changed)

        def op_done(_tr, _op, _commit, _result):
            state["done"] += 1
            progress(min(state["done"] / state["n"], 0.99), "Installing")

        def op_error(_tr, _op, error, _details):
            state["error"] = error.message
            return False  # stop on the first error

        t.connect("ready", ready)
        t.connect("new-operation", new_op)
        t.connect("operation-done", op_done)
        t.connect("operation-error", op_error)
        t.connect("add-new-remote", lambda *_a: False)          # never add remotes behind the user's back
        t.connect("choose-remote-for-ref", lambda *_a: 0)
        try:
            add(t)
            progress(None, "Preparing")
            t.run(None)
        except GLib.Error as e:
            raise StoreError(state["error"] or e.message) from e
        progress(1.0, "")

    def install(self, app, progress):
        self._run(app, progress, lambda t: t.add_install(app.origin, app.ref, None))

    def remove(self, app, progress):
        self._run(app, progress, lambda t: t.add_uninstall(app.ref))

    def update(self, app, progress):
        self._run(app, progress, lambda t: t.add_update(app.ref, None, None))

    def refresh_updates(self, apps):
        found = {}
        for inst in self.installations:
            iid = inst.get_id()
            try:
                for remote in inst.list_remotes(None):
                    if not remote.get_disabled():
                        try:
                            inst.update_appstream_sync(remote.get_name(), self.arch, None)
                        except GLib.Error as e:
                            util.log("appstream refresh failed", remote.get_name(), e.message)
                refs = list(inst.list_installed_refs_for_update(None))
            except GLib.Error as e:
                util.log("update list failed", iid, e.message)
                continue
            for ir in refs:
                if ir.get_kind() != Flatpak.RefKind.APP:
                    continue  # runtimes are updated together with the apps that need them
                a = self._apps_by_ref.get((iid, ir.get_origin(), ir.format_ref()))
                if a is not None:
                    found[a.uid] = a.version if a.version and a.version != ir.get_appdata_version() else "*"
        return found

    def launch(self, app):
        if Backend.launch(self, app):
            return True
        ref = Flatpak.Ref.parse(app.ref)
        try:
            return self._installation(app).launch(ref.get_name(), ref.get_arch(), ref.get_branch(), None, None)
        except GLib.Error:
            return False

    # ------------------------------------------------------------------ remotes
    def sources(self):
        out = []
        for inst in self.installations:
            try:
                remotes = list(inst.list_remotes(None))
            except GLib.Error:
                continue
            where = "" if not inst.get_is_user() else " (user)"
            for r in remotes:
                if r.get_noenumerate():
                    continue
                out.append(Source(f"{inst.get_id()}:{r.get_name()}", self.id, _source_kind(r),
                                  (r.get_title() or r.get_name()) + where, r.get_url() or "",
                                  not r.get_disabled(), True))
        return out

    def has_flathub(self):
        return any(s.kind == "flathub" for s in self.sources())

    def set_source_enabled(self, source, enabled):
        iid, name = source.id.split(":", 1)
        inst = self._inst[iid]
        try:
            remote = inst.get_remote_by_name(name, None)
            remote.set_disabled(not enabled)
            inst.modify_remote(remote, None)    # system installation: polkit via flatpak-system-helper
        except GLib.Error as e:
            raise StoreError(e.message) from e

    def add_flathub(self):
        """Add the Flathub remote to the system installation (downloads its .flatpakrepo)."""
        path = util.fetch_cached(FLATHUB_REPO)
        if not path:
            raise StoreError("Could not download the Flathub repository file")
        with open(path, "rb") as f:
            data = GLib.Bytes.new(f.read())
        inst = next((i for i in self.installations if not i.get_is_user()), self.installations[0])
        try:
            remote = Flatpak.Remote.new_from_file("flathub", data)
            inst.add_remote(remote, True, None)
        except GLib.Error as e:
            raise StoreError(e.message) from e

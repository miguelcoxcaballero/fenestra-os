"""Linux-only backends for the "Fenestra" section: shell extensions, online accounts,
sharing (gnome-remote-desktop / gnome-user-share), search providers, printers, tablets."""
from __future__ import annotations

import configparser
import glob
import os

from gi.repository import Gio, GLib

from .. import util

EXT = ("org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions", "org.gnome.Shell.Extensions")
GOA = "org.gnome.OnlineAccounts"


def later(cb, *a):
    GLib.idle_add(lambda: (cb(*a), False)[1])


# ------------------------------------------------------------------ shell extensions
class Extension:
    def __init__(self, uuid, info):
        self.uuid = uuid
        self.name = info.get("name", uuid)
        self.description = info.get("description", "")
        self.enabled = info.get("enabled", info.get("state") == 1)
        self.state = info.get("state", 0)
        self.has_prefs = bool(info.get("hasPrefs", False))
        self.system = info.get("type") == 1  # 1 = system, 2 = per-user


def extensions(callback):
    if util.DEMO:
        demo = [("dash-to-panel@jderose9.github.com", "Dash to Panel", True, True),
                ("arcmenu@arcmenu.com", "ArcMenu", True, True),
                ("ding@rastersoft.com", "Desktop Icons NG (DING)", True, True),
                ("blur-my-shell@aunetx", "Blur my Shell", True, True),
                ("tiling-assistant@leleat-on-github", "Tiling Assistant", True, True),
                ("places-menu@gnome-shell-extensions.gcampax.github.com", "Places Status Indicator", False, False)]
        later(callback, [Extension(u, {"name": n, "enabled": e, "state": 1 if e else 2, "hasPrefs": p, "type": 2})
                         for u, n, e, p in demo])
        return

    def done(ok, res):
        if not ok or not res:
            callback(None)
            return
        exts = [Extension(u, i) for u, i in res[0].items()]
        exts.sort(key=lambda e: e.name.lower())
        callback(exts)
    util.dbus_call(Gio.BusType.SESSION, *EXT, "ListExtensions", None, done, mutating=False, interactive=False,
                   reply_type=GLib.VariantType("(a{sa{sv}})"))


def set_extension_enabled(uuid, on, callback=None):
    util.dbus_call(Gio.BusType.SESSION, *EXT, "EnableExtension" if on else "DisableExtension",
                   GLib.Variant("(s)", (uuid,)), callback)


def open_extension_prefs(uuid, callback=None):
    util.dbus_call(Gio.BusType.SESSION, *EXT, "OpenExtensionPrefs", GLib.Variant("(ssa{sv})", (uuid, "", {})),
                   callback)


# ------------------------------------------------------------------ online accounts
class OnlineAccount:
    def __init__(self, path, props):
        self.path = path
        self.provider = props.get("ProviderName", "")
        self.identity = props.get("PresentationIdentity", "") or props.get("Identity", "")
        self.icon = props.get("ProviderIcon", "")
        self.attention = bool(props.get("AttentionNeeded", False))


def online_accounts(callback):
    if util.DEMO:
        later(callback, [OnlineAccount("/demo/1", {"ProviderName": "Nextcloud",
                                                   "PresentationIdentity": "alex@cloud.example.com"})])
        return
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error:
        later(callback, None)
        return

    def done(conn, res):
        try:
            objs = conn.call_finish(res).unpack()[0]
        except GLib.Error:
            callback(None)
            return
        accts = [OnlineAccount(p, i[GOA + ".Account"]) for p, i in objs.items() if GOA + ".Account" in i]
        accts.sort(key=lambda a: (a.provider, a.identity))
        callback(accts)
    bus.call(GOA, "/org/gnome/OnlineAccounts", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
             None, None, Gio.DBusCallFlags.NONE, 5000, None, done)


def remove_online_account(acct, callback=None):
    util.dbus_call(Gio.BusType.SESSION, GOA, acct.path, GOA + ".Account", "Remove", None, callback)


# ------------------------------------------------------------------ sharing
def remote_desktop_status(callback):
    """callback(dict(available, rdp_enabled, unit_active, port))"""
    if util.DEMO:
        later(callback, {"available": True, "rdp_enabled": False, "unit_active": False, "port": "3389"})
        return
    if not util.have("grdctl"):
        later(callback, {"available": False})
        return

    def done(ok, out, err):
        st = {"available": True, "rdp_enabled": False, "unit_active": False, "port": "3389"}
        section = None
        for line in (out + "\n" + err).splitlines():
            s = line.strip()
            if s.endswith(":") and not line.startswith("\t"):
                section = s[:-1]
                continue
            if ":" in s:
                k, v = (x.strip() for x in s.split(":", 1))
                if section == "RDP" and k == "Status":
                    st["rdp_enabled"] = v == "enabled"
                elif section == "RDP" and k == "Port":
                    st["port"] = v
                elif section == "Overall" and k == "Unit status":
                    st["unit_active"] = v == "active"
        callback(st)
    util.run_async(["grdctl", "status"], done)


def set_remote_desktop(on, callback=None):
    """User session remote desktop: grdctl rdp enable/disable + the user service."""
    def svc(ok, *_):
        util.run_async(["systemctl", "--user", "enable" if on else "disable", "--now",
                        "gnome-remote-desktop.service"], callback, mutating=True)
    util.run_async(["grdctl", "rdp", "enable" if on else "disable"], svc, mutating=True)


USER_SHARE = "gnome-user-share-webdav.service"


def file_sharing_status(callback):
    if util.DEMO:
        later(callback, {"available": True, "active": False})
        return
    if not os.path.exists("/usr/lib/systemd/user/" + USER_SHARE) and \
            not os.path.exists("/usr/libexec/gnome-user-share-webdav"):
        later(callback, {"available": False})
        return
    util.run_async(["systemctl", "--user", "is-active", USER_SHARE],
                   lambda ok, out, _e: callback({"available": True, "active": out.strip() == "active"}))


def set_file_sharing(on, callback=None):
    util.run_async(["systemctl", "--user", "start" if on else "stop", USER_SHARE], callback, mutating=True)


# ------------------------------------------------------------------ search providers
class SearchProvider:
    def __init__(self, desktop_id, name, icon):
        self.desktop_id, self.name, self.icon = desktop_id, name, icon


def search_providers():
    out = {}
    dirs = [os.path.join(d, "gnome-shell", "search-providers") for d in
            [GLib.get_user_data_dir()] + list(GLib.get_system_data_dirs())]
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.ini"))):
            cp = configparser.ConfigParser(interpolation=None)
            try:
                cp.read(f)
                did = cp.get("Shell Search Provider", "DesktopId")
            except (configparser.Error, OSError):
                continue
            if did in out:
                continue
            try:
                info = Gio.DesktopAppInfo.new(did)
            except TypeError:
                info = None
            if info is None:
                continue
            if util.DEMO and not (info.get_filename() or "").startswith("/usr/share/applications/"):
                continue
            out[did] = SearchProvider(did, info.get_display_name(), info.get_icon())
    return list(out.values())


# ------------------------------------------------------------------ hardware info
def printers(callback):
    if util.DEMO:
        later(callback, [("Office Printer", "idle")])
        return
    if not util.have("lpstat"):
        later(callback, None)
        return

    def done(ok, out, _e):
        res = []
        for line in out.splitlines():
            if line.startswith("printer "):
                parts = line.split()
                state = "idle" if " is idle" in line else "disabled" if "disabled" in line else "busy"
                res.append((parts[1].replace("-", " ").replace("_", " "), state))
        callback(res)
    util.run_async(["lpstat", "-p"], done)


def tablets(callback):
    if util.DEMO:
        later(callback, [])
        return
    if not util.have("libwacom-list-local-devices"):
        later(callback, None)
        return

    def done(ok, out, _e):
        names = []
        for line in out.splitlines():
            s = line.strip()
            if s.lower().startswith("name:") or s.startswith("name="):
                names.append(s.split(":", 1)[-1].split("=", 1)[-1].strip().strip('"'))
        callback(names)
    util.run_async(["libwacom-list-local-devices"], done)


def color_devices(callback):
    if util.DEMO:
        later(callback, [("Built-in display", "Default")])
        return
    if not util.have("colormgr"):
        later(callback, None)
        return

    def done(ok, out, _e):
        res, model = [], None
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("Model:"):
                model = s.split(":", 1)[1].strip()
            elif s.startswith("Kind:") and model:
                res.append((model, s.split(":", 1)[1].strip()))
                model = None
        callback(res)
    util.run_async(["colormgr", "get-devices"], done)

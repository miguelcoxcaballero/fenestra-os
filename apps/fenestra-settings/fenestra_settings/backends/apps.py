"""Installed applications, default handlers and autostart entries."""
from __future__ import annotations

import os

from gi.repository import Gio, GLib

from .. import util


class App:
    def __init__(self, info: Gio.DesktopAppInfo):
        self.info = info
        self.id = info.get_id() or ""
        self.name = info.get_display_name() or info.get_name() or self.id
        self.icon = info.get_icon()
        self.filename = info.get_filename() or ""
        self.flatpak = info.get_string("X-Flatpak") or (
            "/flatpak/" in self.filename and self.id.removesuffix(".desktop"))
        self.size = None
        self.date = None
        self.publisher = ""
        self.package = None

    @property
    def source(self):
        if self.flatpak:
            return "flatpak"
        if self.filename.startswith(os.path.expanduser("~")):
            return "user"
        return "rpm"


def installed():
    apps = []
    for info in Gio.AppInfo.get_all():
        if not isinstance(info, Gio.DesktopAppInfo) or not info.should_show():
            continue
        if util.DEMO and not (info.get_filename() or "").startswith("/usr/share/applications/"):
            continue  # demo: only stock system apps, nothing user-specific
        apps.append(App(info))
    apps.sort(key=lambda a: a.name.lower())
    return apps


def enrich(apps, callback):
    """Fill size/date/publisher via one rpm query and one flatpak list (async)."""
    rpm_apps = [a for a in apps if a.source == "rpm"]
    fp_apps = {a.flatpak: a for a in apps if a.source == "flatpak"}
    pending = [2]

    def finish():
        pending[0] -= 1
        if pending[0] == 0:
            callback()

    def rpm_done(ok, out, _e):
        lines = out.splitlines()
        # rpm prints one line per argument, in order (or an error line)
        for a, line in zip(rpm_apps, lines):
            p = line.split("\t")
            if len(p) == 5:
                a.package = p[0]
                try:
                    a.size = int(p[1])
                    a.date = int(p[2])
                except ValueError:
                    pass
                a.publisher = p[3] if p[3] != "(none)" else p[4]
        finish()

    def fp_done(ok, out, _e):
        for line in out.splitlines():
            p = line.split("\t")
            if len(p) >= 3 and p[0] in fp_apps:
                a = fp_apps[p[0]]
                a.size = _parse_size(p[1])
                a.publisher = p[2] or "Flathub"
                a.package = p[0]
        finish()

    if rpm_apps and util.have("rpm"):
        util.run_async(["rpm", "-qf", "--qf", "%{NAME}\t%{SIZE}\t%{INSTALLTIME}\t%{VENDOR}\t%{PACKAGER}\n"]
                       + [a.filename for a in rpm_apps], rpm_done)
    else:
        GLib.idle_add(lambda: (finish(), False)[1])
    if fp_apps and util.have("flatpak"):
        util.run_async(["flatpak", "list", "--app", "--columns=application,size,origin"], fp_done)
    else:
        GLib.idle_add(lambda: (finish(), False)[1])


def _parse_size(s):
    s = s.replace("\xa0", " ").strip()
    try:
        num, unit = s.split()
        mult = {"bytes": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}.get(unit, 1)
        return int(float(num.replace(",", ".")) * mult)
    except ValueError:
        return None


def uninstall(app: App, callback):
    if app.source == "flatpak":
        argv = ["flatpak", "uninstall", "-y", "--noninteractive", app.package or app.flatpak]
    elif app.source == "rpm" and app.package:
        argv = ["pkcon", "remove", "-y", "--plain", app.package]
    else:
        callback(False, "Unknown package")
        return
    util.run_async(argv, lambda ok, o, e: callback(ok, (e or o).strip()), mutating=True)


def launch_app(app: App):
    if util.READ_ONLY:
        return
    try:
        app.info.launch([], None)
    except GLib.Error:
        pass


# ---------------------------------------------------------------- defaults
DEFAULT_TYPES = [
    ("web", "Web browser", "x-scheme-handler/https", ["x-scheme-handler/http", "text/html"]),
    ("mail", "Email", "x-scheme-handler/mailto", []),
    ("music", "Music player", "audio/mpeg", ["audio/flac", "audio/ogg", "audio/x-wav"]),
    ("video", "Video player", "video/mp4", ["video/x-matroska", "video/webm"]),
    ("photos", "Photo viewer", "image/jpeg", ["image/png", "image/gif", "image/webp"]),
    ("pdf", "PDF viewer", "application/pdf", []),
    ("text", "Text editor", "text/plain", []),
    ("files", "File manager", "inode/directory", []),
    ("calendar", "Calendar", "text/calendar", []),
]


def default_for(mime):
    return Gio.AppInfo.get_default_for_type(mime, False)


def candidates_for(mime):
    return Gio.AppInfo.get_all_for_type(mime) or []


def set_default(info: Gio.AppInfo, mimes):
    if util.READ_ONLY:
        return False
    ok = True
    for m in mimes:
        try:
            info.set_as_default_for_type(m)
        except GLib.Error:
            ok = False
    return ok


# ---------------------------------------------------------------- autostart
def autostart_dir():
    return os.path.join(GLib.get_user_config_dir(), "autostart")


class StartupEntry:
    def __init__(self, fname, path, kf: GLib.KeyFile, user_override: GLib.KeyFile | None):
        self.fname = fname
        self.path = path
        k = user_override or kf

        def get(key, default=""):
            try:
                return k.get_locale_string("Desktop Entry", key, None)
            except GLib.Error:
                try:
                    return kf.get_locale_string("Desktop Entry", key, None)
                except GLib.Error:
                    return default

        def getb(kfile, key, default):
            try:
                return kfile.get_boolean("Desktop Entry", key)
            except GLib.Error:
                return default
        self.name = get("Name", fname)
        self.comment = get("Comment", "")
        self.icon = get("Icon", "")
        self.enabled = not getb(k, "Hidden", False) and getb(k, "X-GNOME-Autostart-enabled", True)
        self.only_show_in = get("OnlyShowIn", "")
        self.not_show_in = get("NotShowIn", "")
        self.nodisplay = getb(kf, "NoDisplay", False)


def startup_entries():
    entries = {}
    user_dir = autostart_dir()
    dirs = [d for d in GLib.get_system_config_dirs()] + [user_dir]
    system = {}
    for d in GLib.get_system_config_dirs():
        ad = os.path.join(d, "autostart")
        if os.path.isdir(ad):
            for f in sorted(os.listdir(ad)):
                if f.endswith(".desktop") and f not in system:
                    system[f] = os.path.join(ad, f)
    user = {}
    if os.path.isdir(user_dir):
        for f in sorted(os.listdir(user_dir)):
            if f.endswith(".desktop"):
                user[f] = os.path.join(user_dir, f)
    if util.DEMO:
        user = {}
    for f in sorted(set(system) | set(user)):
        base = GLib.KeyFile()
        path = system.get(f) or user.get(f)
        try:
            base.load_from_file(path, GLib.KeyFileFlags.NONE)
        except GLib.Error:
            continue
        over = None
        if f in user and f in system:
            over = GLib.KeyFile()
            try:
                over.load_from_file(user[f], GLib.KeyFileFlags.NONE)
            except GLib.Error:
                over = None
        e = StartupEntry(f, path, base, over)
        desk = os.environ.get("XDG_CURRENT_DESKTOP", "GNOME").split(":")
        if e.only_show_in and not any(d in e.only_show_in.split(";") for d in desk):
            continue
        if e.not_show_in and any(d in e.not_show_in.split(";") for d in desk):
            continue
        entries[f] = e
    del dirs
    return sorted(entries.values(), key=lambda e: e.name.lower())


def set_startup_enabled(entry: StartupEntry, enabled: bool) -> bool:
    if util.READ_ONLY:
        return False
    os.makedirs(autostart_dir(), exist_ok=True)
    dest = os.path.join(autostart_dir(), entry.fname)
    kf = GLib.KeyFile()
    try:
        kf.load_from_file(dest if os.path.exists(dest) else entry.path,
                          GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    except GLib.Error:
        return False
    kf.set_boolean("Desktop Entry", "X-GNOME-Autostart-enabled", enabled)
    if enabled:
        try:
            kf.remove_key("Desktop Entry", "Hidden")
        except GLib.Error:
            pass
    try:
        kf.save_to_file(dest)
        return True
    except GLib.Error:
        return False

"""Shared helpers: read-only guard, async subprocesses, GSettings and D-Bus access."""
from __future__ import annotations

import os
import shutil
import sys

from gi.repository import Gio, GLib

# When True (screenshot / test mode) nothing may change system state.
READ_ONLY = False
# When True every backend returns neutral sample data (see backends/demo.py).
DEMO = False

APP_ID = "org.fenestra.Settings"
PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    """Location of data/ (source tree or installed share dir)."""
    cands = [
        os.environ.get("FENESTRA_SETTINGS_DATA", ""),
        os.path.join(os.path.dirname(PKG_DIR), "data"),
        os.path.join(sys.prefix, "share", "fenestra-settings", "data"),
        "/usr/share/fenestra-settings/data",
    ]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "style.css")):
            return c
    return cands[1]


def log(*args):
    if os.environ.get("FENESTRA_SETTINGS_DEBUG"):
        print("[fenestra-settings]", *args, file=sys.stderr)


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


# --------------------------------------------------------------------------- subprocess

def run_async(argv, callback=None, mutating=False, stdin_text=None):
    """Run argv asynchronously; callback(ok, stdout, stderr).

    mutating commands are refused in READ_ONLY mode.
    """
    if mutating and READ_ONLY:
        log("read-only: refused", argv)
        if callback:
            GLib.idle_add(lambda: (callback(False, "", "read-only mode"), False)[1])
        return None
    if not have(argv[0]):
        if callback:
            GLib.idle_add(lambda: (callback(False, "", f"{argv[0]} not found"), False)[1])
        return None
    flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
    if stdin_text is not None:
        flags |= Gio.SubprocessFlags.STDIN_PIPE
    try:
        launcher = Gio.SubprocessLauncher.new(flags)
        launcher.setenv("LC_ALL", "C", True)
        proc = launcher.spawnv(argv)
    except GLib.Error as e:
        if callback:
            GLib.idle_add(lambda: (callback(False, "", str(e)), False)[1])
        return None

    def done(p, res):
        try:
            _ok, out, err = p.communicate_utf8_finish(res)
            ok = p.get_successful()
        except GLib.Error as e:
            ok, out, err = False, "", str(e)
        if callback:
            callback(ok, out or "", err or "")

    proc.communicate_utf8_async(stdin_text, None, done)
    return proc


def run_sync(argv, timeout_ok=True) -> str:
    """Small, fast read-only commands only (used for cheap probes)."""
    if not have(argv[0]):
        return ""
    try:
        launcher = Gio.SubprocessLauncher.new(
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
        launcher.setenv("LC_ALL", "C", True)
        proc = launcher.spawnv(argv)
        _ok, out, _err = proc.communicate_utf8(None, None)
        return out or ""
    except GLib.Error:
        return ""


def launch(argv):
    """Launch an external program detached (allowed even in read-only? no)."""
    if READ_ONLY:
        log("read-only: not launching", argv)
        return False
    if not have(argv[0]):
        return False
    try:
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
        return True
    except GLib.Error:
        return False


def open_control_center(panel: str):
    return launch(["gnome-control-center", panel])


def open_uri(uri: str):
    if READ_ONLY:
        return
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error:
        pass


# --------------------------------------------------------------------------- gsettings

_settings_cache: dict[str, Gio.Settings | None] = {}


def settings(schema_id: str) -> Gio.Settings | None:
    if schema_id in _settings_cache:
        return _settings_cache[schema_id]
    src = Gio.SettingsSchemaSource.get_default()
    s = None
    if src and src.lookup(schema_id, True):
        s = Gio.Settings.new(schema_id)
    _settings_cache[schema_id] = s
    return s


def has_key(schema_id: str, key: str) -> bool:
    s = settings(schema_id)
    return bool(s and s.props.settings_schema.has_key(key))


def gget(schema_id: str, key: str, default=None):
    s = settings(schema_id)
    if not s or not s.props.settings_schema.has_key(key):
        return default
    return s.get_value(key).unpack()


def gset(schema_id: str, key: str, value) -> bool:
    if READ_ONLY:
        log("read-only: gset", schema_id, key, value)
        return False
    s = settings(schema_id)
    if not s or not s.props.settings_schema.has_key(key):
        return False
    vt = s.get_value(key).get_type_string()
    try:
        s.set_value(key, GLib.Variant(vt, value))
        return True
    except (TypeError, GLib.Error):
        return False


def gconnect(schema_id: str, key: str, cb):
    s = settings(schema_id)
    if s and s.props.settings_schema.has_key(key):
        return s.connect(f"changed::{key}", lambda *_: cb())
    return None


# --------------------------------------------------------------------------- D-Bus

def dbus_proxy(bus_type, name, path, iface, callback):
    """Asynchronously create a proxy; callback(proxy or None)."""
    def done(_src, res):
        try:
            p = Gio.DBusProxy.new_for_bus_finish(res)
        except GLib.Error:
            p = None
        callback(p)
    Gio.DBusProxy.new_for_bus(bus_type, Gio.DBusProxyFlags.NONE, None, name, path,
                              iface, None, done)


def dbus_proxy_sync(bus_type, name, path, iface):
    try:
        return Gio.DBusProxy.new_for_bus_sync(bus_type, Gio.DBusProxyFlags.NONE, None,
                                              name, path, iface, None)
    except GLib.Error:
        return None


def prop(proxy, name, default=None):
    if proxy is None:
        return default
    v = proxy.get_cached_property(name)
    return v.unpack() if v is not None else default


def dbus_call(bus_type, name, path, iface, method, args: GLib.Variant | None,
              callback=None, mutating=True, interactive=True, reply_type=None):
    if mutating and READ_ONLY:
        log("read-only: dbus", method)
        if callback:
            GLib.idle_add(lambda: (callback(False, None), False)[1])
        return
    try:
        bus = Gio.bus_get_sync(bus_type, None)
    except GLib.Error:
        if callback:
            callback(False, None)
        return
    flags = Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION if interactive else Gio.DBusCallFlags.NONE

    def done(conn, res):
        try:
            r = conn.call_finish(res)
            if callback:
                callback(True, r.unpack() if r is not None else None)
        except GLib.Error as e:
            log("dbus error", method, e.message)
            if callback:
                callback(False, e.message)

    bus.call(name, path, iface, method, args, reply_type, flags, 120000, None, done)


def dbus_set_prop(bus_type, name, path, iface, propname, variant, callback=None):
    dbus_call(bus_type, name, path, "org.freedesktop.DBus.Properties", "Set",
              GLib.Variant("(ssv)", (iface, propname, variant)), callback)


def human_size(n: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    if i == 0:
        return f"{int(n)} {units[i]}"
    return f"{n:.1f} {units[i]}" if n < 100 else f"{n:.0f} {units[i]}"


def read_file(path: str, default: str = "") -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default

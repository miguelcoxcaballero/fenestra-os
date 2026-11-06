"""Shared helpers: paths, persisted options, GSettings access, formatting."""
from __future__ import annotations

import json
import os
import sys

from gi.repository import Gio, GLib

from .i18n import _

APP_ID = "org.fenestra.Paint"
PROJECT_URL = "https://github.com/fenestra-os/fenestra-os"
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
# Set by --screenshot / the smoke test: never read or write the user's configuration.
EPHEMERAL = bool(os.environ.get("FENESTRA_PAINT_EPHEMERAL"))


def data_dir() -> str:
    cands = [
        os.environ.get("FENESTRA_PAINT_DATA", ""),
        os.path.join(os.path.dirname(PKG_DIR), "data"),
        os.path.join(sys.prefix, "share", "fenestra-paint", "data"),
        "/usr/share/fenestra-paint/data",
    ]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "style.css")):
            return c
    return cands[1]


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "fenestra-paint")


DEFAULTS = {
    "theme": "system",            # system | light | dark
    "custom_colors": [],          # "#rrggbb" strings, newest first (max 10)
    "recent": [],                 # recently opened/saved paths, newest first
    "rulers": False,
    "gridlines": False,
    "statusbar": True,
    "autohide_toolbar": False,
    "thumbnail": False,
}


class Options(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        self.path = os.path.join(config_dir(), "settings.json")
        if EPHEMERAL:
            self["custom_colors"] = []
            self["recent"] = []
            return
        try:
            with open(self.path) as f:
                data = json.load(f)
            for k, v in data.items():
                if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
                    self[k] = v
        except (OSError, ValueError):
            pass

    def set(self, key, value):
        self[key] = value
        if EPHEMERAL:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(dict(self), f, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def add_recent(self, path):
        lst = [p for p in self["recent"] if p != path]
        lst.insert(0, path)
        self.set("recent", lst[:10])


_opts: Options | None = None


def opts() -> Options:
    global _opts
    if _opts is None:
        _opts = Options()
    return _opts


# --------------------------------------------------------------------------- GSettings

_settings: dict[str, Gio.Settings | None] = {}


def settings(schema_id: str):
    if schema_id not in _settings:
        src = Gio.SettingsSchemaSource.get_default()
        s = None
        if src is not None and src.lookup(schema_id, True) is not None:
            s = Gio.Settings.new(schema_id)
        _settings[schema_id] = s
    return _settings[schema_id]


def gget(schema_id: str, key: str, default=None):
    s = settings(schema_id)
    if not s or not s.props.settings_schema.has_key(key):
        return default
    return s.get_value(key).unpack()


def gset(schema_id: str, key: str, value) -> bool:
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
        return s.connect(f"changed::{key}", lambda *_a: cb())
    return None


# --------------------------------------------------------------------------- formatting

def fmt_num(v: float, digits=1) -> str:
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{int(round(v))}"
    return s.replace(".", _("decimal_sep")) if _("decimal_sep") != "decimal_sep" else s


def fmt_size(n: int) -> str:
    if n < 1024:
        return _("%d bytes") % n
    if n < 1024 * 1024:
        return _("%s KB") % fmt_num(n / 1024)
    return _("%s MB") % fmt_num(n / 1024 / 1024)


def display_name(path: str | None) -> str:
    return os.path.basename(path) if path else _("Untitled")

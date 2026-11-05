"""Locate data files both in a source checkout and when installed."""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

_CANDIDATES = [
    os.environ.get("FENESTRA_OOBE_DATADIR", ""),
    os.path.dirname(_HERE),  # installed: package lives inside PKGDATADIR
    os.path.join(os.path.dirname(_HERE), "data"),  # source checkout
    "/usr/share/fenestra-oobe",
    "/usr/local/share/fenestra-oobe",
]


def data_dir() -> str:
    for cand in _CANDIDATES:
        if cand and os.path.isfile(os.path.join(cand, "style.css")):
            return cand
    return os.path.join(os.path.dirname(_HERE), "data")


def data_file(*parts: str) -> str:
    return os.path.join(data_dir(), *parts)


def illustration(name: str) -> str:
    return data_file("illustrations", f"{name}.svg")


def user_config_dir() -> str:
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def done_file() -> str:
    return os.path.join(user_config_dir(), "gnome-initial-setup-done")


def fenestra_state_file() -> str:
    return os.path.join(user_config_dir(), "fenestra", "oobe.json")


# File written by system mode in the gnome-initial-setup home so the first
# login of the new user can pick up the region/keyboard choices.
HANDOFF_RELPATH = os.path.join(".config", "fenestra", "oobe-system.json")

IMPORT_HELPER = "/usr/bin/fenestra-import-windows-assets"
_IMPORTER_CANDIDATES = [
    os.environ.get("FENESTRA_IMPORTER", ""),
    IMPORT_HELPER,
    "/usr/libexec/fenestra-import-windows-assets",
    # source checkout: apps/fenestra-oobe/../../tools/
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "tools",
                 "fenestra-import-windows-assets"),
]


def importer() -> str | None:
    """Path of fenestra-import-windows-assets (installed or in the repo)."""
    for cand in _IMPORTER_CANDIDATES:
        if cand and os.path.isfile(cand):
            return cand
    return None


def downloads_dir() -> str:
    from gi.repository import GLib
    d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    return d or os.path.join(os.path.expanduser("~"), "Downloads")

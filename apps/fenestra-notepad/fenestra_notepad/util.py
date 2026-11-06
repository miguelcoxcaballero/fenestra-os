"""Shared helpers: paths and persisted settings (JSON in ~/.config/fenestra-notepad)."""
from __future__ import annotations

import json
import os
import sys

APP_ID = "org.fenestra.Notepad"
PROJECT_URL = "https://github.com/miguelcoxcaballero/fenestra-os"
DEMO = False          # screenshots: never read or write the user's config/state
PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    cands = [
        os.environ.get("FENESTRA_NOTEPAD_DATA", ""),
        os.path.join(os.path.dirname(PKG_DIR), "data"),
        os.path.join(sys.prefix, "share", "fenestra-notepad", "data"),
        "/usr/share/fenestra-notepad/data",
    ]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "style.css")):
            return c
    return cands[1]


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "fenestra-notepad")


def state_dir() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "fenestra-notepad")


DEFAULT_FONT = "Consolas"
FONT_FALLBACKS = "'Cascadia Mono', 'Liberation Mono', 'DejaVu Sans Mono', 'Noto Sans Mono', monospace"

DEFAULTS = {
    "theme": "system",            # system | light | dark
    "font_family": DEFAULT_FONT,
    "font_style": "regular",      # regular | italic | bold | bold-italic
    "font_size": 11,              # points
    "word_wrap": True,
    "formatting": True,           # Markdown formatting (toolbar, styled Markdown tabs)
    "open_in": "tab",             # tab | window
    "startup": "continue",        # continue | new
    "recent_enabled": True,
    "status_bar": True,
    "recent": [],                 # most recent first
    "match_case": False,
    "whole_word": False,
    "wrap_around": True,
    "window_w": 1000,
    "window_h": 640,
    "window_max": False,
}

RECENT_MAX = 10


class Settings(dict):
    """Persisted options; listeners get (key) after a change."""

    def __init__(self):
        super().__init__({k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()})
        self.path = os.path.join(config_dir(), "settings.json")
        self.listeners = []
        if not DEMO:
            try:
                with open(self.path) as f:
                    data = json.load(f)
                for k, v in data.items():
                    if k in DEFAULTS and (type(v) is type(DEFAULTS[k])
                                          or (isinstance(DEFAULTS[k], (int, float)) and isinstance(v, (int, float))
                                              and not isinstance(v, bool))):
                        self[k] = v
            except (OSError, ValueError):
                pass

    def set(self, key, value, notify=True):
        if self.get(key) == value:
            return
        self[key] = value
        self.save()
        if notify:
            for cb in list(self.listeners):
                cb(key)

    def save(self):
        if DEMO:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self, f, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def add_recent(self, path):
        if not self["recent_enabled"] or not path:
            return
        lst = [p for p in self["recent"] if p != path]
        lst.insert(0, path)
        self.set("recent", lst[:RECENT_MAX])


_settings: Settings | None = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def display_path(path: str) -> str:
    home = os.path.expanduser("~")
    if path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path

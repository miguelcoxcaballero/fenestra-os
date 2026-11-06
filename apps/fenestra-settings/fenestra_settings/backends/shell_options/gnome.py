# SPDX-License-Identifier: GPL-3.0-or-later
"""Taskbar and Start options in the GNOME session: Dash to Panel (taskbar), ArcMenu (Start)
and org.fenestra.desktop (taskbar search box, weather widget, read by fenestra-tray)."""
from __future__ import annotations

import copy
import json

from ... import util

DTP = "org.gnome.shell.extensions.dash-to-panel"
ARCMENU = "org.gnome.shell.extensions.arcmenu"
FENESTRA = "org.fenestra.desktop"
SHELL = "org.gnome.shell"


def supports(option: str) -> bool:
    if option in ("alignment", "taskbar-position", "taskbar-size", "taskbar-autohide", "taskbar-combine",
                  "taskbar-show-desktop", "taskbar-transparency"):
        return util.settings(DTP) is not None
    if option == "search-mode":
        return util.has_key(FENESTRA, "taskbar-search")
    if option == "weather":
        return util.has_key(FENESTRA, "taskbar-widgets")
    if option in ("start-pins", "start-layout"):
        return util.settings(ARCMENU) is not None
    if option == "taskbar-pins":
        return util.has_key(SHELL, "favorite-apps")
    return True


# ---- Dash to Panel per-monitor JSON keys ---------------------------------------------------

def dtp_json(key):
    try:
        return json.loads(util.gget(DTP, key, "{}") or "{}")
    except ValueError:
        return {}


def dtp_set_all(key, value):
    """Per-monitor JSON keys: apply the value to every known monitor."""
    d = dtp_json(key) or {"0": value}
    for mon in d:
        d[mon] = value
    return util.gset(DTP, key, json.dumps(d))


def dtp_first(key, default):
    d = dtp_json(key)
    return next(iter(d.values()), default) if d else default


DTP_DEFAULT_ELEMENTS = [
    {"element": "showAppsButton", "visible": False, "position": "stackedTL"},
    {"element": "activitiesButton", "visible": False, "position": "stackedTL"},
    {"element": "leftBox", "visible": True, "position": "stackedTL"},
    {"element": "taskbar", "visible": True, "position": "stackedTL"},
    {"element": "centerBox", "visible": True, "position": "stackedBR"},
    {"element": "rightBox", "visible": True, "position": "stackedBR"},
    {"element": "dateMenu", "visible": True, "position": "stackedBR"},
    {"element": "systemMenu", "visible": True, "position": "stackedBR"},
    {"element": "desktopButton", "visible": True, "position": "stackedBR"},
]


def dtp_elements():
    """Per-monitor element layout; synthesised from Dash to Panel's defaults when unset."""
    d = dtp_json("panel-element-positions")
    if not d:
        mons = list(dtp_json("panel-positions")) or ["0"]
        d = {m: copy.deepcopy(DTP_DEFAULT_ELEMENTS) for m in mons}
    return d


def dtp_element(name):
    for mon in dtp_elements().values():
        for e in mon:
            if e.get("element") == name:
                return e
    return None


def dtp_update_element(names, **changes):
    names = [names] if isinstance(names, str) else names
    d = dtp_elements()
    if not d:
        return False
    for mon in d.values():
        for e in mon:
            if e.get("element") in names:
                e.update(changes)
    return util.gset(DTP, "panel-element-positions", json.dumps(d))


# ---- taskbar --------------------------------------------------------------------------------

def alignment() -> str:
    """'center' or 'left'."""
    tb = dtp_element("taskbar") or {}
    return "center" if tb.get("position", "centerMonitor").startswith("center") else "left"


def set_alignment(value: str) -> bool:
    pos = "centerMonitor" if value == "center" else "stackedTL"
    return dtp_update_element(["taskbar", "leftBox"], position=pos)


def search_mode() -> str:
    """'hide', 'icon', 'icon-label' or 'box'."""
    return util.gget(FENESTRA, "taskbar-search", "box") or "box"


def set_search_mode(value: str) -> bool:
    return util.gset(FENESTRA, "taskbar-search", value)


def weather() -> bool:
    return bool(util.gget(FENESTRA, "taskbar-widgets", True))


def set_weather(on: bool) -> bool:
    return util.gset(FENESTRA, "taskbar-widgets", bool(on))


def taskbar_pins() -> list[str]:
    """Desktop file ids pinned to the taskbar (GNOME favourites, shown by Dash to Panel)."""
    return list(util.gget(SHELL, "favorite-apps", []) or [])


def set_taskbar_pins(ids) -> bool:
    return util.gset(SHELL, "favorite-apps", list(ids))


# ---- Start ----------------------------------------------------------------------------------

def start_pins() -> list[str]:
    out = []
    for p in util.gget(ARCMENU, "pinned-apps", []) or []:
        if isinstance(p, dict):
            p = p.get("id") or p.get("name") or ""
        if p:
            out.append(str(p))
    return out


def set_start_pins(ids) -> bool:
    s = util.settings(ARCMENU)
    if s is None or s.get_value("pinned-apps").get_type_string() != "as":
        return False  # newer ArcMenu stores dictionaries; only reset is offered there
    return util.gset(ARCMENU, "pinned-apps", list(ids))


def reset_start_pins() -> bool:
    return util.greset(ARCMENU, "pinned-apps")


def pinned_count() -> int:
    return len(util.gget(ARCMENU, "pinned-apps", []) or [])

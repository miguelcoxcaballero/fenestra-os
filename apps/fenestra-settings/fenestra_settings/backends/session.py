# SPDX-License-Identifier: GPL-3.0-or-later
"""Which desktop session Settings runs in, and what that session can do.

Fenestra has two sessions:

* GNOME (GNOME Shell + Mutter + gnome-settings-daemon, the Dash to Panel / ArcMenu / DING
  extensions): everything Settings offers works; nothing here hides anything.
* Fenestra (``XDG_CURRENT_DESKTOP=Fenestra``: KWin + Fenestra Shell). GNOME Shell, Mutter and
  gsd-* do not run, so every control that only drives one of them would save a value that
  nobody reads. Those pages and rows are hidden here, in one place, and the page registry
  (``pages/base.py``), the search index (``search.py``) and the page resolver (``app.py``) all
  ask this module. See docs/fenestra-shell/APPS.md, sections 1.4 and 9.

Features that get a Fenestra backend later (displays, brightness, power policy, screen lock,
input devices, night light, keyboard layouts, shortcuts, window management, ...) stay
unsupported here until that backend exists, so their rows are hidden instead of dead.
"""
from __future__ import annotations

import os
import shutil

FENESTRA = "Fenestra"
GNOME = "GNOME"


def desktop() -> str:
    """The raw ``XDG_CURRENT_DESKTOP`` value ('' when unset)."""
    return os.environ.get("XDG_CURRENT_DESKTOP", "")


def _names() -> list[str]:
    return [p.strip() for p in desktop().split(":") if p.strip()]


def is_fenestra() -> bool:
    """True in the Fenestra session (KWin + Fenestra Shell)."""
    return any(n.lower() == FENESTRA.lower() for n in _names())


def is_gnome() -> bool:
    """True in the GNOME Shell session (and anywhere that is not the Fenestra session, so an
    unknown or empty desktop keeps the historical behaviour)."""
    return not is_fenestra()


# --------------------------------------------------------------------------- features

# Only work under GNOME Shell / Mutter / gsd-* (or one of the GNOME Shell extensions).
GNOME_ONLY = frozenset({
    # window manager / workspaces (P1: backends/windowing)
    "dynamic-workspaces", "workspaces-only-on-primary", "attach-modal-dialogs", "hot-corner",
    "edge-tiling", "workspaces", "alt-tab-scope", "focus-mode", "auto-raise", "titlebar-actions",
    "center-new-windows", "resize-with-right-button", "move-modifier",
    # displays, brightness, night light, power policy, screen lock (P0 2/3/7/8, P1 11)
    "displays", "hdr", "brightness", "night-light", "power-button",
    "battery-saver", "battery-percentage", "screen-lock", "lock-screen-picture",
    "lock-screen-notifications",
    # input (P1 10, 12, 13) and accessibility (P1 15)
    "pointer-devices", "keyboard-layouts", "shortcuts", "locate-pointer", "magnifier",
    "screen-reader-toggle", "on-screen-keyboard", "sticky-keys", "slow-keys", "toggle-keys",
    "visual-bell",
    # notifications (per-app list was filled by GNOME Shell)
    "notification-apps",
    # GNOME Shell extensions: Dash to Panel, ArcMenu, DING, extension management
    "shell-extensions", "desktop-icons", "start-layout", "start-frequent-apps",
    "start-recently-installed", "start-avatar", "taskbar-position", "taskbar-size",
    "taskbar-autohide", "taskbar-combine", "taskbar-show-desktop", "taskbar-transparency",
    "clock-weekday", "clock-date", "clock-seconds", "clock-format-panel", "full-name-in-bar",
    "clipboard-history",
    # smaller areas (P2)
    "search-providers", "remote-desktop", "housekeeping", "automatic-timezone", "week-numbers",
    "autoplay", "location", "proxy", "over-amplification", "wallpaper-fit",
    # external GNOME tools that need GNOME Shell / Mutter / gsd
    "gnome-control-center", "gnome-tweaks", "extension-manager",
    # GNOME lockdown keys nothing reads here (no microphone portal, no problem reporter)
    "microphone-lockdown", "problem-reports",
})

# Only exist in the Fenestra session (Fenestra Shell options without a GNOME counterpart).
FENESTRA_ONLY = frozenset({
    "wallpaper-spotlight",
    # Fenestra Shell drives it (KWin Night light pipeline); also needs a colour light sensor.
    "adaptive-color",
})

# Features that also need hardware: shown only where the check passes.
def _has_colour_sensor() -> bool:
    from . import adaptive_color
    return adaptive_color.supported()


HARDWARE = {
    "adaptive-color": _has_colour_sensor,
}


def supports(feature: str) -> bool:
    """Whether ``feature`` works in this session. Unknown names are supported (shared code)."""
    if feature in HARDWARE and not HARDWARE[feature]():
        return False
    if is_fenestra():
        return feature not in GNOME_ONLY
    return feature not in FENESTRA_ONLY


# --------------------------------------------------------------------------- pages and rows

# page id -> feature it entirely depends on. Child pages of a hidden page are hidden too.
PAGE_FEATURES = {
    "fx-extensions": "shell-extensions",
    "fx-desktop-icons": "desktop-icons",
    "fx-shortcuts": "shortcuts",
    "fx-workspaces": "workspaces",
    "fx-search": "search-providers",
    "multitasking": "workspaces",
    "autoplay": "autoplay",
    "mouse": "pointer-devices",
    "touchpad": "pointer-devices",
    "magnifier": "magnifier",
    "narrator": "screen-reader-toggle",
    "a11y-audio": "visual-bell",
    "a11y-keyboard": "on-screen-keyboard",
    "typing": "keyboard-layouts",
    "screenlock": "screen-lock",
    "lockscreen": "lock-screen-picture",
    "location": "location",
    "proxy": "proxy",
}

# page id -> {row key: feature}. Row keys are the SettingRow/ExpanderRow/Group ``key`` (and the
# search index key of the same row).
ROW_FEATURES = {
    "display": {"brightness": "brightness", "adaptive-color": "adaptive-color", "night-light": "night-light", "hdr": "hdr",
                "scale": "displays", "resolution": "displays", "orientation": "displays",
                "refresh": "displays", "multiple": "displays", "advanced-open": "displays"},
    "microphone": {"mic-access": "microphone-lockdown"},
    "diagnostics": {"tech-reports": "problem-reports"},
    "power": {"lid": "power-button", "battery-percentage": "battery-percentage",
              "battery-saver": "battery-saver"},
    "notifications": {"lock": "lock-screen-notifications", "apps": "notification-apps"},
    "clipboard": {"history": "clipboard-history"},
    "general": {"trash-auto": "housekeeping", "temp-auto": "housekeeping", "names": "full-name-in-bar"},
    "storage": {"sense": "housekeeping", "old-files-age": "housekeeping"},
    "datetime": {"auto-tz": "automatic-timezone", "week-numbers": "week-numbers"},
    "sound": {"overamplify": "over-amplification"},
    "pointer": {"locate": "locate-pointer"},
    "narrator": {"screen-reader": "screen-reader-toggle"},  # (the page is hidden too: a11y P1)
    "a11y-audio": {"visual-bell": "visual-bell"},
    "background": {"fit": "wallpaper-fit"},
    "start": {"start-layout": "start-layout", "start-frequent": "start-frequent-apps",
              "start-recent-installed": "start-recently-installed", "start-avatar": "start-avatar"},
    "taskbar": {"tb-position": "taskbar-position", "tb-size": "taskbar-size", "tb-autohide": "taskbar-autohide",
                "tb-combine": "taskbar-combine", "tb-show-desktop": "taskbar-show-desktop",
                "tb-transparency": "taskbar-transparency", "tb-opacity": "taskbar-transparency",
                "weekday": "clock-weekday", "date": "clock-date", "seconds": "clock-seconds",
                "tb-clock-format": "clock-format-panel"},
    "fx-windows": {"focus-mode": "focus-mode", "auto-raise": "auto-raise",
                   "titlebar-double": "titlebar-actions", "titlebar-middle": "titlebar-actions",
                   "titlebar-right": "titlebar-actions", "center-new": "center-new-windows",
                   "attach-modal": "attach-modal-dialogs", "resize-right": "resize-with-right-button",
                   "move-modifier": "move-modifier"},
    "fx-sharing": {"remote-desktop": "remote-desktop"},
    "fx-online-accounts": {"add-account": "gnome-control-center"},
    "signin": {"password": "gnome-control-center"},
}


def hidden_pages() -> set[str]:
    """Page ids that must not be registered in this session (their children follow)."""
    return {pid for pid, feat in PAGE_FEATURES.items() if not supports(feat)}


def hidden_rows(page_id: str) -> set[str]:
    """Row keys of ``page_id`` that must be hidden in this session."""
    return {key for key, feat in ROW_FEATURES.get(page_id, {}).items() if not supports(feat)}


# --------------------------------------------------------------------------- external tools

# Tools that only make sense with GNOME Shell running.
GNOME_TOOLS = {"gnome-control-center": "gnome-control-center", "gnome-tweaks": "gnome-tweaks",
               "extension-manager": "extension-manager", "gnome-extensions-app": "extension-manager",
               "gnome-extensions": "extension-manager"}

# gnome-control-center panel -> what replaces it in the Fenestra session:
# ("page", page id) opens a Fenestra Settings page, ("argv", [...]) a standalone tool (used only
# when installed). Panels not listed have no working counterpart under KWin.
FENESTRA_PANELS = {
    "bluetooth": ("page", "bt-devices"),
    "sharing": ("page", "fx-sharing"),
    "keyboard": ("page", "typing"),
    "network": ("argv", ["nm-connection-editor"]),
    "wifi": ("argv", ["nm-connection-editor"]),
    "printers": ("argv", ["system-config-printer"]),
    "sound": ("argv", ["pavucontrol"]),
}


def panel_target(name: str | None):
    """What opens GNOME Settings panel ``name`` here: ("gcc", argv), ("page", id), ("argv", argv)
    or None when nothing in this session can show it."""
    if is_gnome():
        return ("gcc", ["gnome-control-center"] + ([name] if name else []))
    t = FENESTRA_PANELS.get(name or "")
    if t is None:
        return None
    if t[0] == "page":
        from ..pages.base import PAGES
        return t if t[1] in PAGES else None
    return t if shutil.which(t[1][0]) else None


def launch_target(argv):
    """Like panel_target() for an ext_row() command line. Returns ("argv", argv),
    ("page", id) or None (the row must be hidden)."""
    argv = list(argv)
    if not argv:
        return None
    tool = os.path.basename(argv[0])
    if tool == "gnome-control-center":
        t = panel_target(argv[1] if len(argv) > 1 else None)
        if t is None:
            return None
        return ("argv", argv) if t[0] == "gcc" else t
    if tool in GNOME_TOOLS and not supports(GNOME_TOOLS[tool]):
        return None
    return ("argv", argv)


def panel_available(name: str | None) -> bool:
    return panel_target(name) is not None


def open_panel(name: str | None, window=None) -> bool:
    """Open GNOME Settings panel ``name`` or its Fenestra counterpart (replaces
    util.open_control_center). Returns False when there is none: callers hide such rows,
    see panel_available()."""
    from .. import util
    t = panel_target(name)
    if t is None:
        return False
    if t[0] == "page":
        if window is None:
            return False
        window.navigate(t[1])
        return True
    return util.launch(t[1])

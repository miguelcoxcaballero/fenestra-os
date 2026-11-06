# SPDX-License-Identifier: GPL-3.0-or-later
"""Taskbar and Start options in the Fenestra session: Fenestra Shell's shell.conf
([Taskbar] Alignment, SearchMode, Weather, Pinned; [Start] Pinned), applied live by the shell
(shell/src/core/shellsettings.cpp, shell/src/services/startservices.cpp). Options the shell
does not have report supports() == False and their rows are hidden."""
from __future__ import annotations

from .. import shellconf

# Settings value (GNOME org.fenestra.desktop taskbar-search) <-> shell.conf SearchMode.
SEARCH_TO_SHELL = {"hide": "hidden", "icon": "icon", "icon-label": "iconLabel", "box": "box"}
SEARCH_FROM_SHELL = {v: k for k, v in SEARCH_TO_SHELL.items()}

# Shell defaults when a key is missing (shellsettings.cpp kDefaultPinned, startservices.cpp
# kDefaultStartPins).
DEFAULT_TASKBAR_PINS = ["org.mozilla.firefox.desktop", "org.gnome.Nautilus.desktop"]
DEFAULT_START_PINS = [
    "org.gnome.Nautilus.desktop", "org.mozilla.firefox.desktop", "fenestra-settings.desktop",
    "org.gnome.Software.desktop", "org.fenestra.Notepad.desktop", "org.fenestra.Paint.desktop",
    "org.gnome.Calculator.desktop", "org.gnome.Calendar.desktop", "org.gnome.clocks.desktop",
    "org.gnome.Snapshot.desktop", "org.gnome.Loupe.desktop", "org.gnome.Contacts.desktop",
    "org.gnome.Weather.desktop", "org.gnome.Maps.desktop", "libreoffice-writer.desktop"]

SUPPORTED = {"alignment", "search-mode", "weather", "taskbar-pins", "start-pins"}


def supports(option: str) -> bool:
    return option in SUPPORTED


def alignment() -> str:
    v = shellconf.get("Taskbar/Alignment")
    return v if v in ("center", "left") else "center"


def set_alignment(value: str) -> bool:
    return shellconf.set("Taskbar/Alignment", "left" if value == "left" else "center")


def search_mode() -> str:
    return SEARCH_FROM_SHELL.get(shellconf.get("Taskbar/SearchMode"), "box")


def set_search_mode(value: str) -> bool:
    return shellconf.set("Taskbar/SearchMode", SEARCH_TO_SHELL.get(value, "box"))


def weather() -> bool:
    return shellconf.get_bool("Taskbar/Weather", True)


def set_weather(on: bool) -> bool:
    return shellconf.set("Taskbar/Weather", bool(on))


def taskbar_pins() -> list[str]:
    return shellconf.get_list("Taskbar/Pinned", list(DEFAULT_TASKBAR_PINS))


def set_taskbar_pins(ids) -> bool:
    return shellconf.set("Taskbar/Pinned", [str(i) for i in ids])


def start_pins() -> list[str]:
    v = shellconf.get_list("Start/Pinned")
    # an empty list reads back as an invalid value in the shell, which then uses its defaults
    return v if v else list(DEFAULT_START_PINS)


def set_start_pins(ids) -> bool:
    return shellconf.set("Start/Pinned", [str(i) for i in ids])


def reset_start_pins() -> bool:
    return shellconf.remove("Start/Pinned")


def pinned_count() -> int:
    return len(start_pins())

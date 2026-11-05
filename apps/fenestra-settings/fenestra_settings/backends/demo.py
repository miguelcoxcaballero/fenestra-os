"""Neutral sample data used with --demo-data (implied by --screenshot).

Nothing here reads the real system's personal information: user names, avatars,
hostnames, network names, device names, serials and file paths are all fictional,
so screenshots can be published safely.
"""
from __future__ import annotations

import os
import time

from gi.repository import GLib

USER_NAME = "Alex Morgan"
USER_LOGIN = "alex"
HOSTNAME = "FENESTRA-PC"
MODEL = "Fenestra Laptop 14"
CPU = "Intel(R) Core(TM) Ultra 7 155H   4.80 GHz"
RAM = "16 GB (15.6 GB usable)"
GPU = ["Intel Arc Graphics"]
DEVICE_ID = "3F2A9C10-7B4E-4D21-9A6F-0C1D2E3F4A5B"
TIMEZONE = "America/New_York"
LOCALE = "en_US.UTF-8"

GB = 1024 ** 3


def later(cb, *args):
    GLib.idle_add(lambda: (cb(*args), False)[1])


def wallpaper(dark: bool) -> str | None:
    """A stock wallpaper shipped by the distribution (never a user file)."""
    names = ["blobs-d.svg", "blobs-l.svg"] if dark else ["blobs-l.svg", "blobs-d.svg"]
    for n in names:
        p = os.path.join("/usr/share/backgrounds/gnome", n)
        if os.path.isfile(p):
            return p
    for root, _d, files in os.walk("/usr/share/backgrounds"):
        for f in sorted(files):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".webp")):
                return os.path.join(root, f)
    return None


def os_info():
    return {
        "product": "Fenestra",
        "edition": "Fenestra Workstation",
        "version": "1.0",
        "base": "Fedora Linux 43 (Workstation Edition)",
        "build": "43.20261101",
        "kernel": "6.17.1-300.fc43.x86_64",
        "home_url": "",
        "support_url": "",
        "installed": GLib.DateTime.new_local(2026, 11, 1, 10, 0, 0).format("%x"),
    }


def battery():
    return {"present": True, "percent": 76.0, "state": 2, "time_to_empty": 3 * 3600 + 20 * 60,
            "time_to_full": 0, "on_battery": True, "icon": "battery-good-symbolic"}


def last_checked():
    return time.time() - 2 * 3600


def update_history():
    return [("2026-11-04 09:12:31", "dnf upgrade --refresh", "37"),
            ("2026-10-28 18:40:02", "dnf install gamemode", "2"),
            ("2026-10-21 08:55:47", "dnf upgrade --refresh", "112")]


def users():
    return [("jamie", "Jamie Lee", 1001)]


def volumes():
    from .storage import Volume
    return [Volume("/", "/dev/nvme0n1p3", "btrfs", 476 * GB, 182 * GB, 294 * GB)]


def categories():
    return {"temp": int(1.3 * GB), "documents": int(4.2 * GB), "pictures": int(12.8 * GB),
            "videos": int(23.5 * GB), "music": int(6.1 * GB), "downloads": int(3.4 * GB),
            "apps_system": int(9.7 * GB), "apps_user": 0}


def audio():
    from .audio import Node
    sinks = [Node(40, "Built-in Audio Speakers", 0.6, True),
             Node(41, "Built-in Audio HDMI / DisplayPort 1 Output", 1.0, False),
             Node(42, "Headphones", 0.45, False)]
    sources = [Node(50, "Built-in Audio Microphone", 0.8, True),
               Node(51, "Headphones Headset", 1.0, False)]
    return sinks, sources


def network_status():
    from .network import Device
    return {"wifi_enabled": True,
            "devices": [Device("wlan0", "wifi", "connected", "HomeNetwork"),
                        Device("eth0", "ethernet", "unavailable", "")]}


def wifi_list():
    from .network import AccessPoint
    return [AccessPoint(True, "HomeNetwork", 82, "WPA2"),
            AccessPoint(False, "Office-5G", 64, "WPA2 WPA3"),
            AccessPoint(False, "Cafe-Guest", 48, "")]


def known_networks():
    return {"HomeNetwork", "Office-5G"}


def device_details():
    return {"IP4.ADDRESS": "192.168.1.23/24", "IP4.GATEWAY": "192.168.1.1", "IP4.DNS": "192.168.1.1",
            "GENERAL.HWADDR": "00:11:22:33:44:55", "CAPABILITIES.SPEED": "1000 Mb/s",
            "GENERAL.DRIVER": "e1000e"}


def bluetooth():
    from .bluetooth import BtDevice
    devs = [BtDevice("/org/bluez/hci0/dev_00_00_00_00_00_01",
                     {"Address": "00:00:00:00:00:01", "Alias": "Headphones", "Paired": True,
                      "Connected": True, "Icon": "audio-headphones"}),
            BtDevice("/org/bluez/hci0/dev_00_00_00_00_00_02",
                     {"Address": "00:00:00:00:00:02", "Alias": "Mouse", "Paired": True,
                      "Connected": True, "Icon": "input-mouse"}),
            BtDevice("/org/bluez/hci0/dev_00_00_00_00_00_03",
                     {"Address": "00:00:00:00:00:03", "Alias": "Keyboard", "Paired": True,
                      "Connected": False, "Icon": "input-keyboard"})]
    devs[0].battery = 80
    return "/org/bluez/hci0", True, devs


THEMES = {"gtk-theme": ["Fenestra", "Fenestra-Dark"], "icon-theme": ["Fenestra"],
          "cursor-theme": ["Fenestra"]}
INPUT_SOURCES = [("xkb", "us"), ("xkb", "es")]
FONT_FAMILIES = ["Cantarell", "DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono", "Inter", "Liberation Sans",
                 "Liberation Serif", "Liberation Mono", "Noto Sans", "Noto Serif", "Noto Sans Mono",
                 "Source Code Pro", "Adwaita Sans", "Adwaita Mono"]

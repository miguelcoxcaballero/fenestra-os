"""NetworkManager status/Ethernet via nmcli, airplane mode via gsd-rfkill.

Wi-Fi (list, connect, known networks) lives in backends/wifi.py (libnm)."""
from __future__ import annotations

import re

from gi.repository import Gio, GLib

from .. import util
from . import demo


def available() -> bool:
    if util.DEMO:
        return True
    return util.have("nmcli")


def _split(line: str):
    """Split nmcli terse output honoring '\\:' escapes."""
    parts, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


class Device:
    def __init__(self, name, dtype, state, conn):
        self.name, self.type, self.state, self.connection = name, dtype, state, conn

    @property
    def connected(self):
        return self.state.startswith("connected")


def status(callback):
    """callback(dict(wifi_enabled, networking, devices=[Device]))"""
    if util.DEMO:
        demo.later(callback, demo.network_status())
        return
    result = {"wifi_enabled": None, "devices": []}
    pending = [2]

    def finish():
        pending[0] -= 1
        if pending[0] == 0:
            callback(result)

    def radio(ok, out, _e):
        if ok:
            vals = _split(out.strip())
            result["wifi_enabled"] = vals[0] == "enabled" if vals else None
        finish()

    def devs(ok, out, _e):
        if ok:
            for line in out.strip().splitlines():
                p = _split(line)
                if len(p) >= 4 and p[1] in ("wifi", "ethernet", "gsm", "wireguard", "vpn", "tun"):
                    result["devices"].append(Device(p[0], p[1], p[2], p[3]))
        finish()
    if not available():
        GLib.idle_add(lambda: (callback(result), False)[1])
        return
    util.run_async(["nmcli", "-t", "-f", "WIFI", "radio"], radio)
    util.run_async(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], devs)


def device_details(dev, callback):
    if util.DEMO:
        demo.later(callback, demo.device_details())
        return
    def done(ok, out, _e):
        info = {}
        if ok:
            for line in out.strip().splitlines():
                p = _split(line)
                if len(p) >= 2:
                    k = re.sub(r"\[\d+\]$", "", p[0])
                    info.setdefault(k, ":".join(p[1:]))
        callback(info)
    util.run_async(["nmcli", "-t", "-f", "GENERAL.HWADDR,GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY,"
                    "IP4.DNS,IP6.ADDRESS,CAPABILITIES.SPEED,GENERAL.DRIVER", "device", "show", dev], done)


def set_wifi(enabled: bool, callback=None):
    util.run_async(["nmcli", "radio", "wifi", "on" if enabled else "off"], callback, mutating=True)


# --------------------------------------------------------------------- airplane mode
RFKILL = ("org.gnome.SettingsDaemon.Rfkill", "/org/gnome/SettingsDaemon/Rfkill",
          "org.gnome.SettingsDaemon.Rfkill")


def rfkill_proxy():
    return util.dbus_proxy_sync(Gio.BusType.SESSION, *RFKILL)


def _rfkill_states():
    """Soft-block state of every radio (Wi-Fi, Bluetooth, WWAN) from sysfs; [] without radios."""
    import glob
    out = []
    for d in glob.glob("/sys/class/rfkill/rfkill*"):
        try:
            with open(d + "/soft") as f:
                out.append(f.read().strip() == "1")
        except OSError:
            pass
    return out


def airplane_mode():
    """Every radio switched off. gsd-rfkill where it runs (GNOME), else the kernel's rfkill."""
    if util.DEMO:
        return False
    v = util.prop(rfkill_proxy(), "AirplaneMode")
    if v is not None:
        return v
    states = _rfkill_states()
    return bool(states) and all(states)


def set_airplane_mode(on: bool, callback=None):
    if util.prop(rfkill_proxy(), "AirplaneMode") is None:
        # /dev/rfkill is the seat user's (uaccess): Wi-Fi, Bluetooth and WWAN in one go.
        if util.have("rfkill"):
            util.run_async(["rfkill", "block" if on else "unblock", "all"], callback, mutating=True)
        else:
            util.run_async(["nmcli", "radio", "all", "off" if on else "on"], callback, mutating=True)
        return
    util.dbus_set_prop(Gio.BusType.SESSION, RFKILL[0], RFKILL[1], RFKILL[2], "AirplaneMode",
                       GLib.Variant("b", on), callback)

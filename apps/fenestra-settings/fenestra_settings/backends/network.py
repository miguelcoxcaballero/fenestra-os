"""NetworkManager via nmcli, airplane mode via gsd-rfkill."""
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


class AccessPoint:
    def __init__(self, in_use, ssid, signal, security):
        self.in_use, self.ssid, self.signal, self.security = in_use, ssid, signal, security

    @property
    def secured(self):
        return bool(self.security and self.security not in ("--", ""))


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


def wifi_list(callback, rescan=False):
    if util.DEMO:
        demo.later(callback, demo.wifi_list())
        return
    def done(ok, out, _e):
        aps = {}
        if ok:
            for line in out.strip().splitlines():
                p = _split(line)
                if len(p) < 4 or not p[1]:
                    continue
                ap = AccessPoint(p[0] == "*", p[1], int(p[2] or 0), p[3])
                old = aps.get(ap.ssid)
                if old is None or ap.in_use or (ap.signal > old.signal and not old.in_use):
                    aps[ap.ssid] = ap
        lst = sorted(aps.values(), key=lambda a: (not a.in_use, -a.signal))
        callback(lst)
    util.run_async(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                    "--rescan", "yes" if rescan else "no"], done)


def known_connections(callback):
    if util.DEMO:
        demo.later(callback, demo.known_networks())
        return
    def done(ok, out, _e):
        names = set()
        if ok:
            for line in out.strip().splitlines():
                p = _split(line)
                if len(p) >= 2 and p[1] == "802-11-wireless":
                    names.add(p[0])
        callback(names)
    util.run_async(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], done)


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


def connect(ssid, password=None, callback=None):
    argv = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        argv += ["password", password]
    util.run_async(argv, callback, mutating=True)


def connect_known(ssid, callback=None):
    util.run_async(["nmcli", "connection", "up", "id", ssid], callback, mutating=True)


def disconnect(dev, callback=None):
    util.run_async(["nmcli", "device", "disconnect", dev], callback, mutating=True)


def forget(ssid, callback=None):
    util.run_async(["nmcli", "connection", "delete", "id", ssid], callback, mutating=True)


# --------------------------------------------------------------------- airplane mode
RFKILL = ("org.gnome.SettingsDaemon.Rfkill", "/org/gnome/SettingsDaemon/Rfkill",
          "org.gnome.SettingsDaemon.Rfkill")


def rfkill_proxy():
    return util.dbus_proxy_sync(Gio.BusType.SESSION, *RFKILL)


def airplane_mode():
    if util.DEMO:
        return False
    p = rfkill_proxy()
    v = util.prop(p, "AirplaneMode")
    return v


def set_airplane_mode(on: bool, callback=None):
    if airplane_mode() is None:
        util.run_async(["nmcli", "radio", "all", "off" if on else "on"], callback, mutating=True)
        return
    util.dbus_set_prop(Gio.BusType.SESSION, RFKILL[0], RFKILL[1], RFKILL[2], "AirplaneMode",
                       GLib.Variant("b", on), callback)


def signal_icon(signal: int) -> str:
    return "fs-wifi-1-symbolic"

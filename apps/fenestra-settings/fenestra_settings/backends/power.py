"""Battery (UPower), power profiles, screen brightness (gsd-power)."""
from __future__ import annotations

from gi.repository import Gio, GLib

from .. import util

UPOWER = "org.freedesktop.UPower"
STATES = {0: "Unknown", 1: "Charging", 2: "Discharging", 3: "Empty", 4: "Fully charged",
          5: "Pending charge", 6: "Pending discharge"}


def battery():
    """dict(present, percent, state, time_to_empty, time_to_full, on_ac) or None."""
    if util.DEMO:
        from . import demo
        return demo.battery()
    p = util.dbus_proxy_sync(Gio.BusType.SYSTEM, UPOWER, "/org/freedesktop/UPower/devices/DisplayDevice",
                             UPOWER + ".Device")
    if p is None or util.prop(p, "Type") is None:
        return None
    present = util.prop(p, "IsPresent", False) and util.prop(p, "Type", 0) == 2
    up = util.dbus_proxy_sync(Gio.BusType.SYSTEM, UPOWER, "/org/freedesktop/UPower", UPOWER)
    return {
        "present": bool(present),
        "percent": float(util.prop(p, "Percentage", 0.0)),
        "state": int(util.prop(p, "State", 0)),
        "time_to_empty": int(util.prop(p, "TimeToEmpty", 0)),
        "time_to_full": int(util.prop(p, "TimeToFull", 0)),
        "on_battery": bool(util.prop(up, "OnBattery", False)),
        "icon": util.prop(p, "IconName", ""),
    }


def fmt_duration(secs: int) -> str:
    h, rem = divmod(int(secs), 3600)
    m = rem // 60
    if h:
        return f"{h} h {m} min"
    return f"{m} min"


# ------------------------------------------------------------------ profiles
_PROFILE_SERVICES = [
    ("org.freedesktop.UPower.PowerProfiles", "/org/freedesktop/UPower/PowerProfiles"),
    ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles"),
]


def _ppd():
    for name, path in _PROFILE_SERVICES:
        p = util.dbus_proxy_sync(Gio.BusType.SYSTEM, name, path, name)
        if p is not None and p.get_name_owner():
            return name, path, p
    return None, None, None


def profiles():
    """(active, [names]) or (None, [])."""
    if util.DEMO:
        return "balanced", ["power-saver", "balanced", "performance"]
    _n, _p, proxy = _ppd()
    if proxy is None:
        return None, []
    act = util.prop(proxy, "ActiveProfile")
    profs = [d.get("Profile") for d in (util.prop(proxy, "Profiles") or []) if d.get("Profile")]
    return act, profs


def set_profile(name, callback=None):
    bus_name, path, proxy = _ppd()
    if proxy is None:
        if callback:
            callback(False, None)
        return
    util.dbus_set_prop(Gio.BusType.SYSTEM, bus_name, path, bus_name, "ActiveProfile",
                       GLib.Variant("s", name), callback)


# ------------------------------------------------------------------ brightness
GSD_POWER = ("org.gnome.SettingsDaemon.Power", "/org/gnome/SettingsDaemon/Power",
             "org.gnome.SettingsDaemon.Power.Screen")


def screen_proxy():
    p = util.dbus_proxy_sync(Gio.BusType.SESSION, *GSD_POWER)
    if p is None or p.get_name_owner() is None:
        return None
    return p


MUTTER_DC = ("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
             "org.gnome.Mutter.DisplayConfig")


def _mutter_backlight():
    """(serial, connector, min, max, value) from mutter's Backlight property (GNOME 48+)."""
    p = util.dbus_proxy_sync(Gio.BusType.SESSION, *MUTTER_DC)
    v = util.prop(p, "Backlight")
    if not v:
        return None
    serial, monitors = v
    for m in monitors:
        if m.get("active", True) and "value" in m:
            return serial, m.get("connector", ""), int(m.get("min", 0)), int(m.get("max", 100)), \
                int(m.get("value", 0))
    return None


def brightness():
    """0..100 or None when no backlight is controllable."""
    if util.DEMO:
        return 70
    v = util.prop(screen_proxy(), "Brightness")
    if v is not None and v >= 0:
        return int(v)
    bl = _mutter_backlight()
    if bl:
        _s, _c, lo, hi, val = bl
        if hi > lo:
            return round((val - lo) * 100 / (hi - lo))
    return None


def set_brightness(value, callback=None):
    v = util.prop(screen_proxy(), "Brightness")
    if v is not None and v >= 0:
        util.dbus_set_prop(Gio.BusType.SESSION, GSD_POWER[0], GSD_POWER[1], GSD_POWER[2], "Brightness",
                           GLib.Variant("i", int(value)), callback)
        return
    bl = _mutter_backlight()
    if not bl:
        if callback:
            callback(False, None)
        return
    serial, conn, lo, hi, _val = bl
    raw = int(round(lo + (hi - lo) * max(1, min(100, value)) / 100))
    util.dbus_call(Gio.BusType.SESSION, *MUTTER_DC, "SetBacklight",
                   GLib.Variant("(usi)", (serial, conn, raw)), callback)

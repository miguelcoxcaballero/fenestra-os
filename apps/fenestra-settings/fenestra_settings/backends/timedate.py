"""timedated / localed helpers."""
from __future__ import annotations

import os

from gi.repository import Gio, GLib

from .. import util

TIMEDATED = ("org.freedesktop.timedate1", "/org/freedesktop/timedate1", "org.freedesktop.timedate1")
LOCALED = ("org.freedesktop.locale1", "/org/freedesktop/locale1", "org.freedesktop.locale1")


def time_proxy():
    return util.dbus_proxy_sync(Gio.BusType.SYSTEM, *TIMEDATED)


def info():
    if util.DEMO:
        from . import demo
        return {"timezone": demo.TIMEZONE, "ntp": True, "can_ntp": True, "local_rtc": False, "available": True}
    p = time_proxy()
    tz = util.prop(p, "Timezone") or os.environ.get("TZ") or GLib.TimeZone.new_local().get_identifier()
    return {
        "timezone": tz,
        "ntp": util.prop(p, "NTP"),
        "can_ntp": util.prop(p, "CanNTP", False),
        "local_rtc": util.prop(p, "LocalRTC", False),
        "available": p is not None and p.get_name_owner() is not None or util.prop(p, "Timezone") is not None,
    }


def set_ntp(on, callback=None):
    util.dbus_call(Gio.BusType.SYSTEM, *TIMEDATED, "SetNTP", GLib.Variant("(bb)", (on, True)), callback)


def set_timezone(tz, callback=None):
    util.dbus_call(Gio.BusType.SYSTEM, *TIMEDATED, "SetTimezone", GLib.Variant("(sb)", (tz, True)),
                   callback)


def timezones(callback):
    def done(ok, out, _e):
        zones = [z for z in out.split() if "/" in z or z == "UTC"] if ok else []
        if not zones:
            zones = _zones_from_tzdata()
        callback(zones)
    util.run_async(["timedatectl", "list-timezones"], done)


def _zones_from_tzdata():
    zones = []
    path = "/usr/share/zoneinfo/tzdata.zi"
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("Z "):
                    zones.append(line.split()[1])
    except OSError:
        pass
    return sorted(zones) or ["UTC"]


def tz_label(tz: str) -> str:
    try:
        z = GLib.TimeZone.new_identifier(tz)
        now = GLib.DateTime.new_now(z)
        off = now.get_utc_offset() // 1_000_000
        sign = "+" if off >= 0 else "-"
        off = abs(off)
        return f"(UTC{sign}{off // 3600:02d}:{off % 3600 // 60:02d}) {tz.replace('_', ' ')}"
    except (TypeError, GLib.Error):
        return tz


def locale_info():
    if util.DEMO:
        from . import demo
        return {"LANG": demo.LOCALE, "_x11_layout": "us"}
    p = util.dbus_proxy_sync(Gio.BusType.SYSTEM, *LOCALED)
    loc = util.prop(p, "Locale") or []
    d = {}
    for item in loc:
        if "=" in item:
            k, v = item.split("=", 1)
            d[k] = v
    if "LANG" not in d:
        d["LANG"] = os.environ.get("LANG", "en_US.UTF-8")
    d["_x11_layout"] = util.prop(p, "X11Layout", "")
    return d


def locales(callback):
    def done(ok, out, _e):
        items = [x for x in out.split() if x] if ok else []
        callback(items or [os.environ.get("LANG", "en_US.UTF-8")])
    util.run_async(["localectl", "list-locales"], done)


def set_system_locale(lang, callback=None):
    util.dbus_call(Gio.BusType.SYSTEM, *LOCALED, "SetLocale",
                   GLib.Variant("(asb)", ([f"LANG={lang}"], True)), callback)


LANG_NAMES = {
    "en": "English", "es": "Español", "fr": "Français", "de": "Deutsch", "it": "Italiano",
    "pt": "Português", "nl": "Nederlands", "pl": "Polski", "ru": "Русский", "ja": "日本語",
    "zh": "中文", "ko": "한국어", "ca": "Català", "eu": "Euskara", "gl": "Galego", "sv": "Svenska",
    "da": "Dansk", "fi": "Suomi", "nb": "Norsk bokmål", "cs": "Čeština", "tr": "Türkçe",
    "uk": "Українська", "ar": "العربية", "he": "עברית", "el": "Ελληνικά", "hu": "Magyar",
    "ro": "Română",
}
REGION_NAMES = {
    "US": "United States", "GB": "United Kingdom", "ES": "Spain", "MX": "Mexico", "AR": "Argentina",
    "FR": "France", "DE": "Germany", "IT": "Italy", "PT": "Portugal", "BR": "Brazil", "CA": "Canada",
    "AU": "Australia", "NL": "Netherlands", "JP": "Japan", "CN": "China", "CO": "Colombia",
    "CL": "Chile", "PE": "Peru", "IE": "Ireland", "IN": "India", "RU": "Russia",
}


def locale_label(loc: str) -> str:
    base = loc.split(".")[0]
    lang, _, region = base.partition("_")
    name = LANG_NAMES.get(lang, lang)
    if region:
        name += f" ({REGION_NAMES.get(region, region)})"
    return name

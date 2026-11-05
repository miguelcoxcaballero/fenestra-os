"""Region, keyboard, locale and time zone data plus localed/timedated calls."""

import gettext
import json
import os
import subprocess
import time
import unicodedata
from dataclasses import dataclass

from gi.repository import GLib

from . import dbus, log

LOCALED = "org.freedesktop.locale1"
LOCALED_PATH = "/org/freedesktop/locale1"
TIMEDATED = "org.freedesktop.timedate1"
TIMEDATED_PATH = "/org/freedesktop/timedate1"

ISO_3166 = "/usr/share/iso-codes/json/iso_3166-1.json"
ZONE_TAB = "/usr/share/zoneinfo/zone.tab"
XKB_RULES = ["/usr/share/X11/xkb/rules/evdev.lst", "/usr/share/X11/xkb/rules/base.lst"]

# Main language of a country when the UI language isn't spoken there.
COUNTRY_LANGUAGE = {
    "AD": "ca", "AE": "ar", "AR": "es", "AT": "de", "AU": "en", "BE": "nl", "BG": "bg", "BO": "es",
    "BR": "pt", "BY": "be", "CA": "en", "CH": "de", "CL": "es", "CN": "zh", "CO": "es", "CR": "es",
    "CU": "es", "CY": "el", "CZ": "cs", "DE": "de", "DK": "da", "DO": "es", "DZ": "ar", "EC": "es",
    "EE": "et", "EG": "ar", "ES": "es", "FI": "fi", "FR": "fr", "GB": "en", "GR": "el", "GT": "es",
    "HK": "zh", "HN": "es", "HR": "hr", "HU": "hu", "ID": "id", "IE": "en", "IL": "he", "IN": "en",
    "IR": "fa", "IS": "is", "IT": "it", "JP": "ja", "KR": "ko", "KZ": "kk", "LT": "lt", "LU": "fr",
    "LV": "lv", "MA": "ar", "MX": "es", "MY": "ms", "NG": "en", "NI": "es", "NL": "nl", "NO": "nb",
    "NZ": "en", "PA": "es", "PE": "es", "PH": "en", "PK": "ur", "PL": "pl", "PR": "es", "PT": "pt",
    "PY": "es", "RO": "ro", "RS": "sr", "RU": "ru", "SA": "ar", "SE": "sv", "SG": "en", "SI": "sl",
    "SK": "sk", "SV": "es", "TH": "th", "TR": "tr", "TW": "zh", "UA": "uk", "US": "en", "UY": "es",
    "VE": "es", "VN": "vi", "ZA": "en",
}

# Default keyboard (layout, variant) per country.
COUNTRY_KEYBOARD = {
    "US": ("us", ""), "GB": ("gb", ""), "IE": ("ie", ""), "CA": ("us", ""), "AU": ("us", ""),
    "NZ": ("us", ""), "IN": ("us", ""), "ZA": ("us", ""), "PH": ("us", ""), "SG": ("us", ""),
    "ES": ("es", ""), "MX": ("latam", ""), "AR": ("latam", ""), "CO": ("latam", ""),
    "CL": ("latam", ""), "PE": ("latam", ""), "VE": ("latam", ""), "EC": ("latam", ""),
    "UY": ("latam", ""), "PY": ("latam", ""), "BO": ("latam", ""), "CR": ("latam", ""),
    "GT": ("latam", ""), "HN": ("latam", ""), "NI": ("latam", ""), "PA": ("latam", ""),
    "SV": ("latam", ""), "DO": ("latam", ""), "CU": ("latam", ""), "PR": ("latam", ""),
    "BR": ("br", ""), "PT": ("pt", ""), "FR": ("fr", ""), "BE": ("be", ""), "LU": ("ch", "fr"),
    "CH": ("ch", ""), "DE": ("de", ""), "AT": ("at", ""), "IT": ("it", ""), "NL": ("us", "intl"),
    "DK": ("dk", ""), "NO": ("no", ""), "SE": ("se", ""), "FI": ("fi", ""), "IS": ("is", ""),
    "PL": ("pl", ""), "CZ": ("cz", ""), "SK": ("sk", ""), "HU": ("hu", ""), "RO": ("ro", ""),
    "BG": ("bg", ""), "GR": ("gr", ""), "TR": ("tr", ""), "RU": ("ru", ""), "UA": ("ua", ""),
    "JP": ("jp", ""), "KR": ("kr", ""), "CN": ("cn", ""), "TW": ("tw", ""), "IL": ("il", ""),
    "AD": ("es", ""),
}

# Representative zone for countries with several time zones.
COUNTRY_TIMEZONE = {
    "US": "America/New_York", "CA": "America/Toronto", "BR": "America/Sao_Paulo",
    "RU": "Europe/Moscow", "AU": "Australia/Sydney", "MX": "America/Mexico_City",
    "AR": "America/Argentina/Buenos_Aires", "CN": "Asia/Shanghai", "ID": "Asia/Jakarta",
    "KZ": "Asia/Almaty", "CL": "America/Santiago", "ES": "Europe/Madrid", "PT": "Europe/Lisbon",
    "DE": "Europe/Berlin", "EC": "America/Guayaquil", "NZ": "Pacific/Auckland",
    "UA": "Europe/Kyiv", "MN": "Asia/Ulaanbaatar", "CD": "Africa/Kinshasa",
    "FM": "Pacific/Pohnpei", "KI": "Pacific/Tarawa", "MY": "Asia/Kuala_Lumpur",
    "PF": "Pacific/Tahiti", "GL": "America/Nuuk", "UZ": "Asia/Tashkent",
}


@dataclass(frozen=True)
class Country:
    code: str
    name: str        # English name
    label: str       # localized display name


@dataclass(frozen=True)
class Layout:
    layout: str
    variant: str
    description: str  # English
    label: str        # localized

    @property
    def id(self) -> str:
        return f"{self.layout}+{self.variant}" if self.variant else self.layout


def _sort_key(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c)).casefold()


def _translator(domain: str, lang: str):
    return gettext.translation(domain, languages=[lang], fallback=True)


def load_countries(lang: str = "en") -> list[Country]:
    try:
        with open(ISO_3166, encoding="utf-8") as fh:
            entries = json.load(fh)["3166-1"]
    except (OSError, ValueError, KeyError):
        entries = [{"alpha_2": c, "name": c} for c in sorted(COUNTRY_LANGUAGE)]
    tr = _translator("iso_3166-1", lang)
    out = []
    for e in entries:
        english = e.get("common_name") or e["name"]
        label = tr.gettext(e.get("common_name") or e["name"])
        if label == english and "common_name" in e:
            label = tr.gettext(e["name"]) if lang != "en" else english
        out.append(Country(e["alpha_2"], english, label))
    out.sort(key=lambda c: _sort_key(c.label))
    return out


def load_layouts(lang: str = "en", include_variants: bool = True) -> list[Layout]:
    path = next((p for p in XKB_RULES if os.path.exists(p)), None)
    if path is None:
        return [Layout("us", "", "English (US)", "English (US)")]
    tr = _translator("xkeyboard-config", lang)
    section = None
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("! "):
                section = line[2:].strip()
                continue
            if not line.strip():
                continue
            name, _, desc = line.strip().partition(" ")
            desc = desc.strip()
            if section == "layout":
                out.append(Layout(name, "", desc, tr.gettext(desc)))
            elif section == "variant" and include_variants:
                parent, _, vdesc = desc.partition(":")
                vdesc = vdesc.strip()
                out.append(Layout(parent.strip(), name, vdesc, tr.gettext(vdesc)))
    out.sort(key=lambda l: _sort_key(l.label))
    return out


def available_locales() -> set[str]:
    """Return available UTF-8 locales normalized as ``ll_CC.UTF-8``."""
    try:
        res = subprocess.run(["locale", "-a"], capture_output=True, text=True, timeout=5)
        names = res.stdout.split()
    except (OSError, subprocess.SubprocessError):
        names = []
    out = set()
    for name in names:
        base, _, enc = name.partition(".")
        if enc.lower().replace("-", "") == "utf8" and "_" in base:
            out.add(f"{base}.UTF-8")
    return out


def zone_table() -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    try:
        with open(ZONE_TAB, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    table.setdefault(parts[0], []).append(parts[2].strip())
    except OSError:
        pass
    return table


def current_timezone() -> str:
    try:
        tz = dbus.get_property(TIMEDATED, TIMEDATED_PATH, TIMEDATED, "Timezone")
        if tz:
            return tz
    except GLib.Error:
        pass
    try:
        target = os.readlink("/etc/localtime")
        if "zoneinfo/" in target:
            return target.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return "UTC"


def current_locale() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if val and val not in ("C", "POSIX", "C.UTF-8"):
            return val
    return "en_US.UTF-8"


def language_of(locale_name: str) -> str:
    return locale_name.split("_")[0].split(".")[0].split("@")[0] or "en"


def territory_of(locale_name: str) -> str:
    base = locale_name.split(".")[0].split("@")[0]
    return base.split("_")[1].upper() if "_" in base else ""


def guess_country(locale_name: str | None = None, tz: str | None = None) -> str:
    """Guess the user's country from the time zone, then the locale."""
    tz = tz or current_timezone()
    for cc, zones in zone_table().items():
        if tz in zones and tz != "UTC":
            return cc
    terr = territory_of(locale_name or current_locale())
    return terr or "US"


def timezone_for_country(cc: str, current: str | None = None) -> str:
    zones = zone_table().get(cc, [])
    current = current or current_timezone()
    if current in zones:
        return current
    if cc in COUNTRY_TIMEZONE:
        return COUNTRY_TIMEZONE[cc]
    return zones[0] if zones else current


def formats_for_country(cc: str, ui_lang: str, locales: set[str] | None = None) -> str:
    locales = locales if locales is not None else available_locales()
    cand = f"{ui_lang}_{cc}.UTF-8"
    if cand in locales or not locales:
        return cand
    main = COUNTRY_LANGUAGE.get(cc)
    if main and f"{main}_{cc}.UTF-8" in locales:
        return f"{main}_{cc}.UTF-8"
    for loc in sorted(locales):
        if loc.split(".")[0].endswith(f"_{cc}"):
            return loc
    return current_locale()


def keyboard_for_country(cc: str, layouts: list[Layout] | None = None) -> tuple[str, str]:
    if cc in COUNTRY_KEYBOARD:
        return COUNTRY_KEYBOARD[cc]
    if layouts:
        ids = {l.layout for l in layouts if not l.variant}
        if cc.lower() in ids:
            return (cc.lower(), "")
    return ("us", "")


class LocaleBackend:
    def __init__(self, demo: bool):
        self.demo = demo

    def apply(self, lang_locale: str, formats: str, layouts: list[tuple[str, str]], timezone: str):
        """Apply system locale, keyboard and time zone.  Blocking."""
        settings = [f"LANG={lang_locale}"]
        if formats and formats != lang_locale:
            for cat in ("LC_NUMERIC", "LC_TIME", "LC_MONETARY", "LC_PAPER", "LC_MEASUREMENT"):
                settings.append(f"{cat}={formats}")
        layout = ",".join(l for l, _ in layouts) or "us"
        variant = ",".join(v for _, v in layouts) if any(v for _, v in layouts) else ""
        options = "grp:win_space_toggle" if len(layouts) > 1 else ""
        if self.demo:
            time.sleep(0.6)
            log.info("[demo] would set locale %s, keyboard %s/%s, timezone %s",
                     settings, layout, variant, timezone)
            return
        errors = []
        try:
            dbus.call(LOCALED, LOCALED_PATH, LOCALED, "SetLocale",
                      GLib.Variant("(asb)", (settings, True)))
        except GLib.Error as exc:
            errors.append(f"locale: {exc.message}")
        try:
            dbus.call(LOCALED, LOCALED_PATH, LOCALED, "SetX11Keyboard",
                      GLib.Variant("(ssssbb)", (layout, "", variant, options, True, True)))
        except GLib.Error as exc:
            errors.append(f"keyboard: {exc.message}")
        try:
            dbus.call(TIMEDATED, TIMEDATED_PATH, TIMEDATED, "SetTimezone",
                      GLib.Variant("(sb)", (timezone, True)))
            dbus.call(TIMEDATED, TIMEDATED_PATH, TIMEDATED, "SetNTP", GLib.Variant("(bb)", (True, True)))
        except GLib.Error as exc:
            errors.append(f"time: {exc.message}")
        for err in errors:
            log.warning("apply settings: %s", err)

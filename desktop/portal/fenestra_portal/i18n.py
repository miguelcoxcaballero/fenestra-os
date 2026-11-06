# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny gettext-style translation layer (English source strings, Spanish catalog).

Same language rules as the other Fenestra apps: FENESTRA_PORTAL_LANG, then LANGUAGE,
LC_ALL, LC_MESSAGES, LANG. The portal runs as a long-lived user service, so the
language is read once at start-up.
"""
import importlib
import locale
import os

_catalog: dict[str, str] = {}
LANG = "en"


def _detect() -> str:
    for var in ("FENESTRA_PORTAL_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            v = v.split(":")[0]
            if v in ("C", "POSIX") or v.startswith("C."):
                return "en"
            return v.split(".")[0].split("_")[0].lower()
    try:
        return (locale.getlocale()[0] or "en").split("_")[0]
    except ValueError:
        return "en"


def init(lang: str | None = None):
    global _catalog, LANG
    LANG = (lang or _detect()) or "en"
    _catalog = {}
    if LANG != "en":
        try:
            mod = importlib.import_module(f"fenestra_portal.locale.{LANG}")
            _catalog = dict(mod.STRINGS)
        except (ImportError, AttributeError):
            LANG = "en"


def _(s: str) -> str:
    return _catalog.get(s, s)





init()

"""Tiny gettext-style translation layer (English source strings)."""
import importlib
import locale
import os

_catalog: dict[str, str] = {}
LANG = "en"


def _detect() -> str:
    for var in ("FENESTRA_SETTINGS_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
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
            mod = importlib.import_module(f"fenestra_settings.locale.{LANG}")
            _catalog = dict(mod.STRINGS)
        except (ImportError, AttributeError):
            LANG = "en"


def _(s: str) -> str:
    return _catalog.get(s, s)


def N_(s: str) -> str:
    """Mark for extraction without translating now."""
    return s


init()

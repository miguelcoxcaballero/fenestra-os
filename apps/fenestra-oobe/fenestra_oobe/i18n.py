"""Very small message catalog: English source strings, Spanish translation.

Kept as Python dictionaries so the OOBE needs no build step; more languages
can be added by dropping a ``translations/<lang>.py`` module exposing
``MESSAGES``.
"""

import importlib
import os

_lang = "en"
_messages: dict[str, str] = {}

SUPPORTED = ("en", "es")


def detect_language() -> str:
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if val:
            code = val.split(":")[0].split("_")[0].split(".")[0]
            if code in ("C", "POSIX"):
                continue
            return code
    return "en"


def set_language(lang: str):
    global _lang, _messages
    _lang = lang if lang in SUPPORTED else "en"
    _messages = {}
    if _lang != "en":
        try:
            mod = importlib.import_module(f"fenestra_oobe.translations.{_lang}")
            _messages = dict(mod.MESSAGES)
        except ImportError:
            _messages = {}


def language() -> str:
    return _lang


def _(text: str) -> str:
    return _messages.get(text, text)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _(singular) if n == 1 else _(plural)

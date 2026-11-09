"""Keyboard layouts of the KWin session: kxkbrc, which is what KWin reads."""
from __future__ import annotations

import shutil
import subprocess

EURO_ON_5 = "eurosign:5"


def _kwrite(key, value):
    # --notify: KWin watches kxkbrc through KConfig and reloads the keymap.
    subprocess.run(["kwriteconfig6", "--notify", "--file", "kxkbrc", "--group", "Layout", "--key", key, value],
                   check=False, timeout=5)


def options_for(layouts, current):
    """Windows' Spanish layout has the euro on AltGr+E and on AltGr+5; XKB's only on E. The option
    acts on the first layout only, and elsewhere AltGr+5 is taken (French: "[")."""
    kept = [o for o in current if o and o != EURO_ON_5]
    if layouts and layouts[0] == "es":
        kept.append(EURO_ON_5)
    return kept


def _read_options():
    out = subprocess.run(["kreadconfig6", "--file", "kxkbrc", "--group", "Layout", "--key", "Options"],
                         capture_output=True, text=True, check=False, timeout=5).stdout.strip()
    return out.split(",") if out else []


def apply(sources, per_window=False):
    """sources: [("xkb", "es"), ("xkb", "us+intl"), ...]. False when this session can't apply them."""
    if not shutil.which("kwriteconfig6"):
        return False
    pairs = [ident.split("+", 1) + [""] for kind, ident in sources if kind == "xkb"]
    if not pairs:
        return False
    layouts = [p[0] for p in pairs]
    _kwrite("Use", "true")
    _kwrite("LayoutList", ",".join(layouts))
    _kwrite("VariantList", ",".join(p[1] for p in pairs))
    _kwrite("ResetOldOptions", "true")
    _kwrite("Options", ",".join(options_for(layouts, _read_options())))
    _kwrite("SwitchMode", "WinClass" if per_window else "Global")
    return True

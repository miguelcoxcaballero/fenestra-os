#!/usr/bin/env python3
"""List English UI strings that have no Spanish translation (exit 1 if any).

Scans every _("...") / N_("...") call in fenestra_notepad/ plus the status-bar encoding
labels, and also reports catalog entries that are no longer used."""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fenestra_notepad.locale.es import STRINGS  # noqa: E402
from fenestra_notepad import textio  # noqa: E402

# Literal labels that are deliberately identical in every language
UNTRANSLATED_OK = {"CRLF", "LF", "CR", "Markdown", "UTF-8", "UTF-16 LE",
                   "UTF-16 BE", "ISO-8859-1", "OK", "Zoom", "F3", "F5", "Ctrl", "Alt"}


def strings():
    out = []

    def add(s):
        if isinstance(s, str) and s.strip() and s not in out:
            out.append(s)
    pkg = os.path.join(ROOT, "fenestra_notepad")
    for dp, _d, fs in os.walk(pkg):
        if "locale" in dp:
            continue
        for f in sorted(fs):
            if not f.endswith(".py"):
                continue
            t = ast.parse(open(os.path.join(dp, f)).read())
            for n in ast.walk(t):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("_", "N_") \
                        and n.args and isinstance(n.args[0], ast.Constant):
                    add(n.args[0].value)
    for v in textio.ENCODINGS.values():
        add(v)
    return out


def main():
    used = strings()
    missing = [s for s in used if s not in STRINGS and s not in UNTRANSLATED_OK]
    unused = [s for s in STRINGS if s not in used]
    for s in missing:
        print("missing:", repr(s))
    for s in unused:
        print("unused: ", repr(s))
    print(f"{len(used)} strings, {len(missing)} missing, {len(unused)} unused")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

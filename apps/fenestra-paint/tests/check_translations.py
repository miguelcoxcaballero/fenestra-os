#!/usr/bin/env python3
"""List English UI strings that have no translation (exit 1 if any).

Every string passed to _() or N_() in fenestra_paint/ must be in each catalog of
fenestra_paint/locale/ (currently: es).  Also flags catalog entries that are no longer
used, and translations that lose or add printf placeholders."""
import ast
import importlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
LANGS = ["es"]
EXTRA = {"decimal_sep"}  # looked up indirectly


def strings():
    out = []
    for dp, _d, fs in os.walk(os.path.join(ROOT, "fenestra_paint")):
        if "locale" in dp:
            continue
        for f in sorted(fs):
            if not f.endswith(".py"):
                continue
            t = ast.parse(open(os.path.join(dp, f)).read())
            for n in ast.walk(t):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("_", "N_") \
                        and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    s = n.args[0].value
                    if s.strip() and s not in out:
                        out.append(s)
    return out


def placeholders(s):
    return sorted(re.findall(r"%[sd]", s))


def main():
    used = strings()
    bad = 0
    for lang in LANGS:
        cat = importlib.import_module(f"fenestra_paint.locale.{lang}").STRINGS
        missing = [s for s in used if s not in cat]
        for s in missing:
            print(f"[{lang}] missing: {s!r}")
        for s in used:
            if s in cat and placeholders(s) != placeholders(cat[s]):
                print(f"[{lang}] placeholder mismatch: {s!r} -> {cat[s]!r}")
                bad += 1
        unused = [s for s in cat if s not in used and s not in EXTRA]
        for s in unused:
            print(f"[{lang}] unused: {s!r}")
        bad += len(missing)
    print(f"{len(used)} strings, {bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

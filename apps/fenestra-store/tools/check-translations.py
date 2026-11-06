#!/usr/bin/env python3
"""Every string passed to _() / N_() (and the window's message tables) must have a Spanish
translation with the same %-placeholders. Pure Python, no GTK needed.
    python3 tools/check-translations.py   # exit 0 when complete
"""
import ast
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fenestra_store")
sys.path.insert(0, os.path.dirname(ROOT))
from fenestra_store.locale.es import STRINGS  # noqa: E402

EXTRA = ["Home", "Apps", "Games", "Library", "Sources", "Queued", "Preparing", "Downloading", "Installing",
         "Uninstalling", "Updating", "Waiting", "Waiting for authorisation", "Checking", "Finishing"]


def strings():
    found = set(EXTRA)
    for dirpath, _d, files in os.walk(ROOT):
        if "locale" in dirpath:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            tree = ast.parse(open(os.path.join(dirpath, f), encoding="utf-8").read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("_", "N_") and node.args \
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    found.add(node.args[0].value)
                # message tables: OK_TEXT / FAIL_TEXT dicts in window.py
                if isinstance(node, ast.Assign) and any(getattr(t, "id", "").endswith("_TEXT") for t in node.targets):
                    for v in node.value.values:
                        found.add(v.value)
    return found


missing, bad = [], []
for s in sorted(strings()):
    if s not in STRINGS:
        missing.append(s)
    elif sorted(re.findall(r"%[sd]", s)) != sorted(re.findall(r"%[sd]", STRINGS[s])):
        bad.append(s)
for s in missing:
    print("missing:", repr(s))
for s in bad:
    print("placeholders differ:", repr(s))
print("TRANSLATIONS", "OK" if not (missing or bad) else "FAILED", f"missing={len(missing)} bad={len(bad)}")
sys.exit(1 if missing or bad else 0)

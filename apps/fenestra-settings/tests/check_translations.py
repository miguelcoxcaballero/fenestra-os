#!/usr/bin/env python3
"""List English UI strings that have no Spanish translation (exit 1 if any)."""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fenestra_settings.locale.es import STRINGS  # noqa: E402


def strings():
    out = []

    def add(s):
        if isinstance(s, str) and s.strip() and s not in out:
            out.append(s)
    for dp, _d, fs in os.walk(os.path.join(ROOT, "fenestra_settings")):
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
                if isinstance(n, ast.ClassDef):
                    for b in n.body:
                        if isinstance(b, ast.Assign) and isinstance(b.targets[0], ast.Name):
                            nm = b.targets[0].id
                            if nm in ("title", "keywords") and isinstance(b.value, ast.Constant):
                                add(b.value.value)
                            if nm == "index":
                                for e in b.value.elts:
                                    add(e.elts[1].value)
                                    add(e.elts[2].value)
    return out


missing = [s for s in strings() if s not in STRINGS]
for s in missing:
    print(repr(s))
sys.exit(1 if missing else 0)

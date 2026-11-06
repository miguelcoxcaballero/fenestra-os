#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Merges design/reference/measurements.json (reference measurements, tests/visual/measure.py)
into design/tokens.json: for every key with reliable=true at scale 1 (dark theme preferred), the
measured value replaces the placeholder. Prints what changed. --dry-run only prints."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tokens_path = ROOT / "design/tokens.json"
meas_path = ROOT / "design/reference/measurements.json"


def main():
    dry = "--dry-run" in sys.argv
    tokens = json.loads(tokens_path.read_text())
    measured = json.loads(meas_path.read_text()) if meas_path.exists() else []
    if isinstance(measured, dict):
        # measure.py writes {"entries": [...], ...}; other top-level sections (dialogs) carry no token keys
        measured = measured.get("entries", [])
    best = {}
    for m in measured:
        if not m.get("reliable") or float(m.get("scale", 1)) != 1.0:
            continue
        key = m["key"]
        if key not in best or (m.get("theme") == "dark" and best[key].get("theme") != "dark"):
            best[key] = m
    changed = 0
    for key, m in sorted(best.items()):
        if key not in tokens:
            continue    # panel geometry, elements, colours: reference data, not tokens
        if tokens[key] != m["value"]:
            print(f"{key}: {tokens[key]} -> {m['value']}  ({m.get('source')} {m.get('at')})")
            tokens[key] = m["value"]
            changed += 1
    if changed and not dry:
        tokens_path.write_text(json.dumps(tokens, indent=2, ensure_ascii=False) + "\n")
    print(f"{changed} value(s) {'would change' if dry else 'changed'}")


if __name__ == "__main__":
    main()

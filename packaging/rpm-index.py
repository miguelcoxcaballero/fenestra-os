#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Index of the fenestra-shell builds on the rolling release «fenestra-shell-latest».

  rpm-index.py INDEX_IN OUT_DIR RPM --commit SHA --date ISO --fedora N [--keep K]

Reads INDEX_IN (the index.json now on the release; a missing file is an empty index), adds RPM
(replacing an older entry of the same commit, Fedora version and arch), keeps the newest K
builds per Fedora version and arch, and writes OUT_DIR/index.json, OUT_DIR/SHA256SUMS (every
kept RPM) and OUT_DIR/pruned (RPM file names no longer listed, to delete from the release).
fenestra-migrate (migrator/) reads index.json and SHA256SUMS; .github/workflows/shell-rpm.yml
publishes them.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("index_in")
    ap.add_argument("out_dir")
    ap.add_argument("rpm")
    ap.add_argument("--commit", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--fedora", required=True)
    ap.add_argument("--keep", type=int, default=10)
    a = ap.parse_args()

    name = os.path.basename(a.rpm)
    m = re.match(r"^(fenestra-shell)-([^-]+)-([^-]+)\.([A-Za-z0-9_]+)\.rpm$", name)
    if not m:
        sys.exit(f"not a fenestra-shell binary RPM file name: {name}")
    if not re.match(r"^[0-9a-f]{40}$", a.commit):
        sys.exit("--commit must be a full commit id")
    h = hashlib.sha256()
    with open(a.rpm, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    # UTC, so the dates sort as text (here and in fenestra-migrate).
    date = datetime.datetime.fromisoformat(a.date.replace("Z", "+00:00")).astimezone(datetime.timezone.utc)
    entry = {"commit": a.commit, "date": date.strftime("%Y-%m-%dT%H:%M:%SZ"), "fedora": str(a.fedora), "arch": m.group(4),
             "version": m.group(2), "release": m.group(3), "rpm": name,
             "sha256": h.hexdigest(), "size": os.path.getsize(a.rpm)}

    try:
        with open(a.index_in) as f:
            old = json.load(f).get("builds", [])
    except (OSError, ValueError, AttributeError):
        old = []
    old = [b for b in old if isinstance(b, dict) and b.get("rpm") and b.get("sha256")]
    same = lambda b: (b.get("fedora"), b.get("arch")) == (entry["fedora"], entry["arch"])  # noqa: E731
    builds = [b for b in old if not (same(b) and b.get("commit") == a.commit) and b.get("rpm") != name] + [entry]
    mine = sorted((b for b in builds if same(b)), key=lambda b: str(b.get("date", "")), reverse=True)
    drop = {id(b) for b in mine[a.keep:]}
    kept = sorted((b for b in builds if id(b) not in drop), key=lambda b: str(b.get("date", "")), reverse=True)
    kept_names = {b["rpm"] for b in kept}
    pruned = sorted({b["rpm"] for b in old} - kept_names)

    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "index.json"), "w") as f:
        json.dump({"format": 1, "latest": entry["commit"], "builds": kept}, f, indent=1)
        f.write("\n")
    with open(os.path.join(a.out_dir, "SHA256SUMS"), "w") as f:
        for b in kept:
            f.write(f"{b['sha256']}  {b['rpm']}\n")
    with open(os.path.join(a.out_dir, "pruned"), "w") as f:
        f.write("".join(n + "\n" for n in pruned))
    print(json.dumps(entry, indent=1))


if __name__ == "__main__":
    main()

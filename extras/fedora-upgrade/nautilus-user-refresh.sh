#!/usr/bin/env bash
# Rebuild the per-user Fenestra Explorer layer after Nautilus changes (e.g. Fedora 45).
# No sudo. Until an overlay for the installed Nautilus major version exists in the repo
# (desktop/nautilus/overlay/<major>/, not *-wip), Files keeps running as stock Nautilus.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
L="$HOME/.local/share/nautilus-sidebar-win11"
ver=$(rpm -q --qf '%{version}' nautilus); major=${ver%%.*}
src="$REPO/desktop/nautilus/overlay/$major"
if [ ! -d "$src" ]; then
    echo "No finished Explorer overlay for Nautilus $major yet ($src): Files runs as stock Nautilus."
    exit 0
fi
mkdir -p "$L"
python3 "$REPO/desktop/libexec/fenestra-patch-nautilus" --src /usr/bin/nautilus --dest "$L" --force
rm -rf "$L/overlay.new"; cp -a "$src" "$L/overlay.new"; rm -rf "$L/overlay"; mv "$L/overlay.new" "$L/overlay"
sha256sum /usr/bin/nautilus | cut -d' ' -f1 > "$L/source.sha256"
cp -f "$REPO/desktop/nautilus/python/"*.py "$HOME/.local/share/nautilus-python/extensions/"
echo "Explorer layer rebuilt for Nautilus $ver. Close all Files windows (nautilus -q) and open Files again."

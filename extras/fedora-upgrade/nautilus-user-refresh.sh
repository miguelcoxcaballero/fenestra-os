#!/usr/bin/env bash
# Rebuild the per-user Fenestra Explorer layer after Nautilus changes (e.g. a Fedora upgrade).
# No sudo. Until an overlay for the installed Nautilus major version exists
# (overlay/<major>/, not *-wip), Files keeps running as stock Nautilus.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." 2>/dev/null && pwd || true)
L="$HOME/.local/share/nautilus-sidebar-win11"
ver=$(rpm -q --qf '%{version}' nautilus); major=${ver%%.*}
src=""; patcher=""; py=""
for base in "$REPO/desktop/nautilus/overlay" /usr/share/fenestra/nautilus/overlay; do
    [ -d "$base/$major" ] && { src="$base/$major"; break; }
done
for p in "$REPO/desktop/libexec/fenestra-patch-nautilus" /usr/libexec/fenestra/fenestra-patch-nautilus; do
    [ -f "$p" ] && { patcher="$p"; break; }
done
for d in "$REPO/desktop/nautilus/python" /usr/share/nautilus-python/extensions; do
    [ -d "$d" ] && { py="$d"; break; }
done
if [ -z "$src" ] || [ -z "$patcher" ]; then
    echo "No finished Explorer overlay for Nautilus $major yet: Files runs as stock Nautilus."
    exit 0
fi
mkdir -p "$L"
python3 "$patcher" --src /usr/bin/nautilus --dest "$L" --force
rm -rf "$L/overlay.new"; cp -a "$src" "$L/overlay.new"; rm -rf "$L/overlay"; mv "$L/overlay.new" "$L/overlay"
sha256sum /usr/bin/nautilus | cut -d' ' -f1 > "$L/source.sha256"
if [ -n "$py" ] && [ "$py" != /usr/share/nautilus-python/extensions ]; then
    mkdir -p "$HOME/.local/share/nautilus-python/extensions"
    cp -f "$py"/*.py "$HOME/.local/share/nautilus-python/extensions/"
fi
echo "Explorer layer rebuilt for Nautilus $ver."

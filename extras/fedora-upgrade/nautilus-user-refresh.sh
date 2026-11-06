#!/usr/bin/env bash
# Rebuild the per-user Fenestra Explorer layer after Nautilus changes (e.g. a Fedora upgrade).
# No sudo. Until an overlay for the installed Nautilus major version exists
# (overlay/<major>/), Files keeps running as stock Nautilus.
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
# GTK 4.24 (Fedora 45) fixes for an existing ~/.config/gtk-4.0/gtk.css (new accounts get
# them from /etc/skel): plain tab-close and eject glyphs, no sort arrow in Details.
css="$HOME/.config/gtk-4.0/gtk.css"
if [ -f "$css" ] && ! grep -q 'fenestra-gtk-4.24' "$css"; then
    cat >> "$css" <<'CSS'
/* fenestra-gtk-4.24 */
.win11-explorer .win11-tabs .tab-close-button image { -gtk-icon-style: symbolic; -gtk-icon-size: 10px; }
.win11-explorer placessidebar row button image { -gtk-icon-style: symbolic; }
.win11-explorer columnview > header > button sort-indicator,
.win11-explorer columnview > header > button sort-indicator.ascending,
.win11-explorer columnview > header > button sort-indicator.descending { -gtk-icon-source: none; min-width: 0; min-height: 0; }
CSS
fi
# GTK 4.24's SVG renderer skips namespace-prefixed elements (<ns0:path>): window-control
# icons converted with ElementTree came out blank (no maximize/close buttons).
grep -rlZ --include='*.svg' '<ns0:' "$HOME/.local/share/icons" 2>/dev/null |
    xargs -0 -r sed -i -E 's#<ns0:([a-z]+) xmlns:ns0="http://www.w3.org/2000/svg"#<\1#g; s#<(/?)ns0:#<\1#g'
echo "Explorer layer rebuilt for Nautilus $ver."

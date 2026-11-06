#!/bin/sh
# Regenerate screenshots/ on a headless compositor (never on the real desktop):
#   WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland tools/screenshots.sh
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/screenshots"
mkdir -p "$OUT"
shot() {  # name args...
    n=$1; shift
    python3 "$HERE/bin/fenestra-notepad" --screenshot "$OUT/$n.png" "$@" 2>&1 | grep -v -e MESA -e baseline -e '^$' || true
}
for theme in light dark; do
    shot main-$theme --$theme
    shot menu-file-$theme --$theme --shot menu-file
    shot menu-edit-$theme --$theme --shot menu-edit
    shot menu-view-$theme --$theme --shot menu-zoom
    shot context-$theme --$theme --shot context
    shot find-$theme --$theme --shot find
    shot replace-$theme --$theme --shot replace
    shot settings-$theme --$theme --shot settings
    shot markdown-$theme --$theme --shot markdown
done
shot settings-font-light --light --shot settings-font
shot menu-recent-light --light --shot menu-recent
shot tabs-light --light --shot tabs
shot save-changes-light --light --shot save
shot goto-light --light --shot goto
shot main-es-light --light --lang es --shot menu-file
shot settings-es-dark --dark --lang es --shot settings

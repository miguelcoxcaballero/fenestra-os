#!/bin/sh
# Regenerate screenshots/ on the headless test compositor (never the real desktop):
#   ~/.local/bin/fenestra-test-run mutter --headless --wayland --no-x11 \
#       --virtual-monitor 1920x1080 --wayland-display=fenestra-test &
#   tools/screenshots.sh
set -u
cd "$(dirname "$0")/.."
OUT=screenshots
mkdir -p "$OUT"
CFG=$(mktemp -d)
shot() {
    name=$1; shift
    env -u DISPLAY WAYLAND_DISPLAY=${WAYLAND_DISPLAY_TEST:-fenestra-test} GDK_BACKEND=wayland \
        GSETTINGS_BACKEND=memory XDG_CONFIG_HOME="$CFG" \
        ${RUNNER:-$HOME/.local/bin/fenestra-test-run} python3 bin/fenestra-paint \
        --screenshot "$OUT/$name.png" --size 1920x1032 --maximized "$@" 2>&1 | grep -v MESA
}
shot main-light --light
shot main-dark --dark
shot demo-light --light --demo
shot demo-dark --dark --demo
shot menu-file --light --menu file
shot menu-file-saveas-dark --dark --menu file-saveas
shot menu-edit --light --menu edit
shot menu-view --light --menu view-zoom
shot menu-brushes --light --menu brushes
shot menu-selection --light --menu selection
shot menu-rotate --light --menu rotate
shot menu-shape-fill-dark --dark --menu fill
shot layers-light --light --demo --layers
shot layers-dark --dark --demo --layers
shot settings-light --light --settings
shot settings-dark --dark --settings
shot dialog-resize --light --dialog resize
shot dialog-properties-dark --dark --dialog properties
shot dialog-unsaved --light --demo --dialog unsaved
shot text-tool --light --text
shot selection-move --light --demo --select
# Dark mode of the same menus and dialogs.
shot menu-file-dark --dark --menu file
shot menu-edit-dark --dark --menu edit
shot menu-view-dark --dark --menu view-zoom
shot menu-brushes-dark --dark --menu brushes
shot menu-selection-dark --dark --menu selection
shot menu-rotate-dark --dark --menu rotate
shot dialog-resize-dark --dark --dialog resize
shot dialog-unsaved-dark --dark --demo --dialog unsaved
shot text-tool-dark --dark --text
shot selection-move-dark --dark --demo --select
shot spanish --light --lang es --menu file
rm -rf "$CFG"
[ -e "/run/user/$(id -u)/gnome-shell-disable-extensions" ] && rm -f "/run/user/$(id -u)/gnome-shell-disable-extensions"
true

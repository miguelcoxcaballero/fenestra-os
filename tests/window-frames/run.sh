#!/bin/bash
# tests/window-frames/run.sh CFG OUT: window frames and caption buttons (and, with SHELL_BUILD,
# the desktop icon labels) at a fractional scale, in the KWin lab image (tests/shell-kwin) with the
# host's render node: OpenGL compositing like the real session, captured with KWin's ScreenShot2.
#   CFG  configuration under test: aurorae/ (themes), gtk-3.0/, gtk-4.0/ (user CSS), themes/ (GTK
#        themes), optional icons/<theme>/... (files mounted over ~/.local/share/icons)
#   OUT  shot.png (whole screen, device pixels) and the clients' logs
# env: SCALE (1.6) W H (2880 1800 device px)  BS (Aurorae border size: Tiny = the theme's own)
#      CAPFONT (kdeglobals [WM] activeFont)  ACTIVE (caption of the focused window)
#      STATE (--hover=close|minimize|maximize, --pressed=..., --dump: clients.py)
#      SHELL_BUILD (a tests/shell-kwin build dir: the shell's desktop instead of the windows)
#      KEEP=1 NAME=... (keep the session; act-shot.sh focuses a window and captures)
# Measurements: measure.py (frames), desk_boxes.py (desktop labels).
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
CFG=$(realpath "$1"); OUT=$(realpath -m "$2"); mkdir -p "$OUT"
FONTS=(); for f in "$HOME/.local/share/fonts:/root/.local/share/fonts" /usr/local/share/fonts:/usr/local/share/fonts \
    /usr/share/fonts/selawik:/usr/share/fonts/selawik /etc/fonts/conf.d/60-fenestra.conf:/etc/fonts/conf.d/60-fenestra.conf; do
    [ -e "${f%%:*}" ] && FONTS+=(-v "$f:ro"); done
# kde-gtk-config's GTK 3 modules (gtk-modules= in settings.ini), as on the real system.
for m in /usr/lib64/qt6/plugins/org.kde.kdecoration3/org.kde.breeze.so /usr/lib64/gtk-3.0/modules/libwindow-decorations-gtk-module.so /usr/lib64/gtk-3.0/modules/libcolorreload-gtk-module.so; do
    [ -e "$m" ] && FONTS+=(-v "$m:$m:ro"); done
# Icon files under test (CFG/icons/<theme>/...) are mounted over the user's icon themes.
if [ -d "$CFG/icons" ]; then
    while IFS= read -r f; do FONTS+=(-v "$f:/root/.local/share/icons/${f#$CFG/icons/}:ro"); done < <(find "$CFG/icons" -type f)
fi
exec podman run --rm --security-opt label=disable --device /dev/dri/renderD128 --cap-add SYS_NICE \
    -e SCALE="${SCALE:-1.6}" -e W="${W:-2880}" -e H="${H:-1800}" -e STATE="${STATE:-}" -e DECO="${DECO:-Fenestra-Dark}" -e LIB="${LIB:-}" -e BS="${BS:-}" -e ACTIVE="${ACTIVE:-Qt SSD}" -e CAPFONT="${CAPFONT:-}" -e SHELL_BUILD="${SHELL_BUILD:+1}" -e DESK_BG="${DESK_BG:-}" -e SHELL_LANG="${SHELL_LANG:-}" -e WAIT="${WAIT:-6}" -e HOSTUSER="$USER" -e KEEP="${KEEP:-}" ${NAME:+--name $NAME} \
    -v "$REPO:/src:ro" -v "$CFG:/cfg:ro" ${SHELL_BUILD:+-v "$SHELL_BUILD:/build"} -v "$OUT:/out" "${FONTS[@]}" \
    -v /usr/share/icons/Fenestra:/usr/share/icons/Fenestra:ro -v "$HOME/.local/share/icons:/root/.local/share/icons:ro" \
    localhost/fenestra-kwinlab:latest bash /src/tests/window-frames/session.sh

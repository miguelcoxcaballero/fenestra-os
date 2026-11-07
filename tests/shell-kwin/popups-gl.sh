#!/bin/bash
# tests/shell-kwin/popups-gl.sh BUILD OUT: Fenestra Shell's popups with KWin's OpenGL compositing and
# blur effect (the host's render node, as tests/window-frames), at the user's geometry, against the
# Windows 11 captures (reference-shots/user-win11). The container stays up (name fenestra-popups);
# drive it with tests/shell-kwin/popups-ctl.sh:
#   popups-ctl.sh eval 'screensView.objectAt(0).start.open()'
#   popups-ctl.sh shot OUT/start.png                       (KWin ScreenShot2, device pixels)
#   podman rm -f fenestra-popups                          (stop)
# BUILD is a tests/shell-kwin build dir (build.sh). env: SCALE (1.5) W H (2880 1800), WALLPAPER
# (default: the user's from ~/.config/fenestra/shell.conf), SHELL_LANG (en_GB.UTF-8), TRANSPARENCY,
# NAME (container, fenestra-popups; popups-ctl.sh reads CONTAINER), IMAGE (fenestra-kwinlab).
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=$(realpath "$1"); OUT=$(realpath -m "$2"); mkdir -p "$OUT"
WP=${WALLPAPER:-$(sed -n 's/^Wallpaper=//p' "$HOME/.config/fenestra/shell.conf" 2>/dev/null | head -1)}
[ -f "$WP" ] && cp "$WP" "$OUT/wallpaper.${WP##*.}"
M=()
for f in "$HOME/.local/share/fonts:/root/.local/share/fonts" /usr/local/share/fonts:/usr/local/share/fonts \
    /etc/fonts/conf.d/60-fenestra.conf:/etc/fonts/conf.d/60-fenestra.conf \
    /usr/share/icons/Fenestra:/usr/share/icons/Fenestra "$HOME/.local/share/icons:/root/.local/share/icons" \
    "$HOME/.local/share/fenestra:/root/.local/share/fenestra"; do
    [ -e "${f%%:*}" ] && M+=(-v "$f:ro"); done
NAME=${NAME:-fenestra-popups}
podman rm -f "$NAME" >/dev/null 2>&1
exec podman run -d --name "$NAME" --security-opt label=disable --device /dev/dri/renderD128 --cap-add SYS_NICE \
    -e SCALE="${SCALE:-1.5}" -e W="${W:-2880}" -e H="${H:-1800}" -e HOSTUSER="$USER" -e SHELL_LANG="${SHELL_LANG:-en_GB.UTF-8}" \
    -e TRANSPARENCY="${TRANSPARENCY:-}" -e FADINGPOPUPS="${FADINGPOPUPS:-true}" -e WPEXT="${WP##*.}" \
    -v "$REPO:/src:ro" -v "$BUILD:/build" -v "$OUT:/out" "${M[@]}" \
    "${IMAGE:-localhost/fenestra-kwinlab:latest}" bash /src/tests/shell-kwin/popups-gl-session.sh

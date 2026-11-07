#!/bin/bash
# tests/lockscreen/greeter-gl.sh OUT: the real lock screen (kscreenlocker_greet --testing with
# shells/org.fenestra.desktop) in a nested KWin (--virtual, OpenGL on the host's render node) at
# 2880 x 1800, scale 1.5, with real PAM (root's password "Fenestra1"), stand-ins for Howdy and
# fprintd (pam_exec), the user's fonts and icon pack. The container stays up (fenestra-lockbench);
# drive it with tests/lockscreen/ctl.sh. Never touches the user's session.
#   env: BG (picture; default today's Spotlight), HELLO (atlas dir), SCALE W H, LANGUAGE (es_ES.UTF-8)
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(realpath -m "$1"); mkdir -p "$OUT"
BG=${BG:-$(python3 -c 'import json;print(json.load(open("/var/lib/windows-spotlight/current.json"))["image"])' 2>/dev/null)}
[ -f "${BG:-}" ] && cp "$BG" "$OUT/bg.jpg"
M=()
[ -d "$HOME/.local/share/fonts" ] && M+=(-v "$HOME/.local/share/fonts:/root/.local/share/fonts:ro")
[ -d "$HOME/.local/share/fenestra/packs" ] && M+=(-v "$HOME/.local/share/fenestra/packs:/root/.local/share/fenestra/packs:ro")
[ -n "${HELLO:-}" ] && M+=(-v "$(realpath "$HELLO"):/root/.local/share/fenestra/assets/hello-windows:ro")
podman rm -f fenestra-lockbench >/dev/null 2>&1
exec podman run -d --name fenestra-lockbench --security-opt label=disable --device /dev/dri/renderD128 --cap-add SYS_NICE \
    -e SCALE="${SCALE:-1.5}" -e W="${W:-2880}" -e H="${H:-1800}" -e LOCKLANG="${LANGUAGE:-es_ES.UTF-8}" \
    -v "$REPO:/src:ro" -v "$OUT:/out" "${M[@]}" localhost/fenestra-kwinlab:latest bash /src/tests/lockscreen/greeter-session.sh

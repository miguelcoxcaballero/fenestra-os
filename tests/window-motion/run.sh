#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# tests/window-motion/run.sh OUT [EFFECT]: records app windows opening, minimizing, restoring,
# maximizing, restoring and closing in the KWin lab image (tests/shell-kwin/Containerfile) with the
# host's render node (real OpenGL compositing) at SCALE (1.5), frames from KWin's ScreenShot2.
#   EFFECT  fenestra (kwin/effects/fenestra-window-motion, default) or stock (KWin's scale, squash
#           and maximize effects, what Fenestra had before)
#   OUT     <client>-<action>/fNNN.png + times.json, then analyse.py / compare.py on the host
# env: SCALE (1.5) W H (2880 1800 device px) CLIENTS ("qt gtk3-x11"; also x11-csd)
#      CORNERS (a built fenestra-corners.so, needed by X11 windows that draw their own frame)
#      SHELL_BUILD (a tests/shell-kwin build dir: Fenestra Shell runs, windows minimize to its taskbar)
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(realpath -m "$1"); mkdir -p "$OUT"
exec podman run --rm --security-opt label=disable --device /dev/dri/renderD128 --cap-add SYS_NICE \
    -e SCALE="${SCALE:-1.5}" -e W="${W:-2880}" -e H="${H:-1800}" -e EFFECT="${2:-fenestra}" -e CLIENTS="${CLIENTS:-qt gtk3-x11}" \
    -e SHELL_BUILD="${SHELL_BUILD:+1}" ${SHELL_BUILD:+-v "$SHELL_BUILD:/build"} ${CORNERS:+-v "$(realpath "$CORNERS"):/usr/lib64/qt6/plugins/kwin/effects/plugins/fenestra-corners.so:ro"} -v "$REPO:/src:ro" -v "$OUT:/out" localhost/fenestra-kwinlab:latest bash /src/tests/window-motion/session.sh

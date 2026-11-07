#!/bin/bash
# tests/shell-kwin/popups-ctl.sh: drives the popups-gl.sh container.
#   eval EXPR         the shell's test probe (QML expression on Main.qml's root)
#   shot OUT.png      whole screen through KWin ScreenShot2 (device px); OUT under popups-gl.sh's OUT dir
#   frames DIR N      N captures back to back (motion checks)
#   sh CMD            any command in the session's environment
set -u
C=${CONTAINER:-fenestra-popups}
case "$1" in
eval) podman exec $C bash -c '. /tmp/env; gdbus call --session -d org.fenestra.Shell -o /org/fenestra/Shell/Test -m org.fenestra.Shell.Test.Eval "$1"' _ "$2" ;;
shot) podman exec $C bash -c '. /tmp/env; python3 /src/tests/window-frames/shot.py "/out/$1"' _ "$(basename "$2")" ;;
sh) shift; podman exec $C bash -c '. /tmp/env; '"$*" ;;
esac

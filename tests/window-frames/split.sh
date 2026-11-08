#!/bin/bash
# Inside a KEEP=1 bench container: split.sh OUTDIR N "CAPTION=slot" ...
# Quick-tiles each window (slot: left right top-left top-right bottom-left bottom-right maximize
# restore) like Meta+arrows / dragging to a screen edge, then captures the screen N times in a
# row (frames 0..N-1) to catch anything that changes between frames (the split-screen corner
# flicker). The windows' frames, states and KWin's view of them go to OUTDIR/state.txt.
set -a; . /tmp/env; set +a
out=$1; n=$2; shift 2
mkdir -p "$out"
run() {  # run a KWin script given as text
    printf '%s\n' "$1" > /tmp/split-$$.js
    local id; id=$(gdbus call --session -d org.kde.KWin -o /Scripting -m org.kde.kwin.Scripting.loadScript /tmp/split-$$.js split$RANDOM | grep -o '[0-9]\+')
    gdbus call --session -d org.kde.KWin -o /Scripting/Script$id -m org.kde.kwin.Script.run >/dev/null
}
for a in "$@"; do
    cap=${a%=*}; slot=${a##*=}
    case $slot in
        left) f=Left;; right) f=Right;; top) f=Top;; bottom) f=Bottom;;
        top-left) f=TopLeft;; top-right) f=TopRight;; bottom-left) f=BottomLeft;; bottom-right) f=BottomRight;;
        *) f=;;
    esac
    if [ -n "$f" ]; then
        run "workspace.windowList().forEach(w => { if (w.caption === \"$cap\") { workspace.activeWindow = w; workspace.slotWindowQuickTile$f(); } });"
    elif [ "$slot" = maximize ]; then
        run "workspace.windowList().forEach(w => { if (w.caption === \"$cap\") w.setMaximize(true, true); });"
    else
        run "workspace.windowList().forEach(w => { if (w.caption === \"$cap\") w.setMaximize(false, false); });"
    fi
    sleep 1
done
sleep 2
run 'workspace.windowList().forEach(w => { if (w.normalWindow) console.warn("SPLITSTATE", JSON.stringify({c: w.caption, g: w.frameGeometry, b: w.bufferGeometry, max: w.maximizeMode, deco: !!w.decoration, tile: w.tile ? JSON.stringify(w.tile.absoluteGeometry) : null, active: w.active})); });'
sleep 0.5
grep SPLITSTATE /out/kwin.log | tail -12 > "$out/state.txt"
geo=$(python3 -c "print(round(${W:-2880}/${SCALE:-1.6}), round(${H:-1800}/${SCALE:-1.6}))")
for i in $(seq -w 0 $((n - 1))); do
    timeout 30 python3 /src/tests/window-frames/shot.py "$out/f$i.png" 0 0 $geo >/dev/null 2>&1
done
echo done "$out"

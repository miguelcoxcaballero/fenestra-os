#!/bin/bash
# Inside a KEEP=1 bench container: act-shot.sh CAPTION OUT.png — focus that window, capture.
set -a; . /tmp/env; set +a
printf 'workspace.windowList().forEach(w => { if (w.caption === "%s") workspace.activeWindow = w; });\n' "$1" > /tmp/act.js
n=act$RANDOM
id=$(gdbus call --session -d org.kde.KWin -o /Scripting -m org.kde.kwin.Scripting.loadScript /tmp/act.js $n | grep -o '[0-9]\+')
gdbus call --session -d org.kde.KWin -o /Scripting/Script$id -m org.kde.kwin.Script.run >/dev/null; sleep 1
for try in 1 2 3; do timeout 30 python3 /src/tests/window-frames/shot.py "$2" 0 0 $(python3 -c "print(round(${W:-2880}/${SCALE:-1.6}), round(${H:-1800}/${SCALE:-1.6}))") && break; done

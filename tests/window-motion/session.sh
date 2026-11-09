#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Inside the KWin lab image: KWin --virtual (OpenGL) at SCALE with the Fenestra decoration, the
# window motion effect under test (EFFECT=fenestra|stock), a still backdrop, then record.py.
set -u
export XDG_RUNTIME_DIR=/tmp/xdg LANG=C.UTF-8 QT_FORCE_STDERR_LOGGING=1 XDG_SESSION_TYPE=wayland NO_AT_BRIDGE=1
mkdir -p -m700 $XDG_RUNTIME_DIR ~/.config ~/.local/share/aurorae/themes ~/.local/share/kwin/effects
cp -r /src/kwin/aurorae/* ~/.local/share/aurorae/themes/
cp -r /src/kwin/effects/fenestra-window-motion ~/.local/share/kwin/effects/
# What the shell writes: the preview shown while dragging to a screen edge.
OUTLINE=${OUTLINE:-dark}
mkdir -p ~/.local/share/kwin/outline; cp -r /src/kwin/outline/fenestra ~/.local/share/kwin/outline/
if [ "${EFFECT:-fenestra}" = fenestra ]; then
    # What the shell writes (shell/src/services/kwinintegration.cpp).
    PLUGINS='fenestra-window-motionEnabled=true
scaleEnabled=false
squashEnabled=false
maximizeEnabled=false
glideEnabled=false
fadeEnabled=false
magiclampEnabled=false'
else
    PLUGINS=''
fi
cat > ~/.config/kwinrc <<RC
[org.kde.kdecoration2]
ButtonsOnLeft=
ButtonsOnRight=IAX
library=org.kde.kwin.aurorae
theme=__aurorae__svg__Fenestra-Dark
BorderSize=Tiny
BorderSizeAuto=false
[Compositing]
Backend=OpenGL
[Plugins]
blurEnabled=false
$PLUGINS
[Effect-fenestra-window-motion]
Debug=true
[Xwayland]
Scale=1
[Outline]
QmlPath=kwin/outline/fenestra/$OUTLINE.qml
RC
PY=$(readlink -f /usr/bin/python3)
cat > /usr/share/applications/fenestra-motion-shot.desktop <<DE
[Desktop Entry]
Type=Application
Name=Window motion bench
Exec=$PY
NoDisplay=true
X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2
DE
kbuildsycoca6 --noincremental >/dev/null 2>&1
exec dbus-run-session -- bash -s <<'INNER'
set -u
kwin_wayland --virtual --xwayland --socket wl-m --width ${W:-2880} --height ${H:-1800} > /out/kwin.log 2>&1 &
for i in $(seq 60); do [ -S $XDG_RUNTIME_DIR/wl-m ] && break; sleep 0.25; done
export WAYLAND_DISPLAY=wl-m
sleep 2
kscreen-doctor output.Virtual-0.scale.${SCALE:-1.5} >/dev/null 2>&1; sleep 1
DISPLAY=$(grep -o 'DISPLAY=:[0-9]*' /out/kwin.log | head -1 | cut -d= -f2); export DISPLAY=${DISPLAY:-:0}
gdbus call --session -d org.kde.KWin -o /Effects -m org.freedesktop.DBus.Properties.Get org.kde.kwin.Effects loadedEffects > /out/effects.txt
id=$(gdbus call --session -d org.kde.KWin -o /Scripting -m org.kde.kwin.Scripting.loadScript /src/tests/window-frames/place.js place | grep -o "[0-9]\+" | tail -1)
gdbus call --session -d org.kde.KWin -o /Scripting/Script$id -m org.kde.kwin.Script.run >/dev/null
QT_QPA_PLATFORM=wayland /usr/lib64/qt6/bin/qml /src/tests/window-frames/backdrop.qml >/out/backdrop.log 2>&1 &
sleep 2
if [ -n "${SHELL_BUILD:-}" ]; then
    # Fenestra Shell: its taskbar sends each button's place (set_minimized_geometry).
    cmake --install /build --prefix /usr >/dev/null
    QT_QPA_PLATFORM=wayland fenestra-shell > /out/shell.log 2>&1 &
    for i in $(seq 60); do grep -q FENESTRA_SHELL_READY /out/shell.log && break; sleep 0.5; done
    sleep 5
fi
python3 /src/tests/window-motion/record.py /out ${CLIENTS:-qt gtk3-x11} > /out/record.log 2>&1
cat /out/record.log
INNER

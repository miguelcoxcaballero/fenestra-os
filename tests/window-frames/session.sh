#!/bin/bash
# Inside the KWin lab image (tests/shell-kwin/Containerfile), GPU render node passed in:
# KWin --virtual with OpenGL compositing at SCALE, the Aurorae theme from /cfg/aurorae, the GTK
# configuration from /cfg/gtk-3.0 and /cfg/gtk-4.0, and one window of each kind (clients.py).
#   /src repo (ro)  /cfg configuration under test  /out screenshots   env: SCALE W H STATE
set -u
export XDG_RUNTIME_DIR=/tmp/xdg LANG=C.UTF-8 QT_FORCE_STDERR_LOGGING=1 XDG_CURRENT_DESKTOP=Fenestra XDG_SESSION_TYPE=wayland
export GSETTINGS_BACKEND=keyfile NO_AT_BRIDGE=1 GDK_DEBUG=portals
mkdir -p -m700 $XDG_RUNTIME_DIR /out ~/.config ~/.local/share/aurorae
# The user's CSS imports absolute paths under their home.
[ -e /home/${HOSTUSER:-x} ] || { mkdir -p /home; ln -s /root /home/${HOSTUSER:-x}; }
rm -rf ~/.local/share/aurorae/themes; cp -r /cfg/aurorae ~/.local/share/aurorae/themes
for v in 3 4; do rm -rf ~/.config/gtk-$v.0; cp -r /cfg/gtk-$v.0 ~/.config/gtk-$v.0; done
rm -rf ~/.local/share/themes; cp -r /cfg/themes ~/.local/share/themes
THEME=$(sed -n 's/^gtk-theme-name=//p' /cfg/gtk-theme 2>/dev/null); THEME=${THEME:-Windows11-Miguel-Dark-AccentA}
cat > ~/.config/kwinrc <<RC
[org.kde.kdecoration2]
ButtonsOnLeft=
ButtonsOnRight=IAX
library=${LIB:-org.kde.kwin.aurorae}
theme=__aurorae__svg__${DECO:-Fenestra-Dark}
BorderSize=${BS:-Normal}
BorderSizeAuto=false
[Compositing]
Backend=OpenGL
[Plugins]
blurEnabled=false
[Xwayland]
Scale=1
RC
printf '[General]\nColorScheme=BreezeDark\n[WM]\nactiveFont=%s\n' "${CAPFONT:-Segoe UI Variable,10,-1,5,50,0,0,0,0,0}" > ~/.config/kdeglobals
# Dark mode reaches GTK 4 / libadwaita through the Settings portal, as in the real session.
mkdir -p ~/.config/xdg-desktop-portal; printf '[preferred]\ndefault=gtk\n' > ~/.config/xdg-desktop-portal/portals.conf
PY=$(readlink -f /usr/bin/python3)
cat > /usr/share/applications/fenestra-frame-shot.desktop <<DE
[Desktop Entry]
Type=Application
Name=Frame bench shot
Exec=$PY
NoDisplay=true
X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2
DE
kbuildsycoca6 --noincremental >/dev/null 2>&1

exec dbus-run-session -- bash -s <<'INNER'
set -u
gs() { gsettings set org.gnome.desktop.interface "$@"; }
gs gtk-theme "${THEME:-Windows11-Miguel-Dark-AccentA}"; gs icon-theme Fenestra-Windows; gs color-scheme prefer-dark
gs font-name 'Segoe UI Variable 10'; gs enable-animations false; gs cursor-size 24
gsettings set org.gnome.desktop.wm.preferences button-layout 'icon:minimize,maximize,close'
kwin_wayland --virtual --xwayland --socket wl-f --width ${W:-2880} --height ${H:-1800} > /out/kwin.log 2>&1 &
for i in $(seq 60); do [ -S $XDG_RUNTIME_DIR/wl-f ] && break; sleep 0.25; done
export WAYLAND_DISPLAY=wl-f
sleep 2
# --scale multiplies the mode; the output scale is set like the user's display settings do.
kscreen-doctor output.Virtual-0.scale.${SCALE:-1.6} >/dev/null 2>&1; sleep 1
DISPLAY=$(grep -o 'DISPLAY=:[0-9]*' /out/kwin.log | head -1 | cut -d= -f2); export DISPLAY=${DISPLAY:-:0}
# D-Bus activated services (the GTK portal backend) need the display.
dbus-update-activation-environment WAYLAND_DISPLAY DISPLAY XDG_CURRENT_DESKTOP GSETTINGS_BACKEND XDG_RUNTIME_DIR
pkill -f xdg-desktop-portal; sleep 0.5
gdbus call --session -d org.freedesktop.portal.Desktop -o /org/freedesktop/portal/desktop -m org.freedesktop.portal.Settings.ReadOne org.freedesktop.appearance color-scheme > /out/portal.log 2>&1
id=$(gdbus call --session -d org.kde.KWin -o /Scripting -m org.kde.kwin.Scripting.loadScript /src/tests/window-frames/place.js place | grep -o '[0-9]\+')
gdbus call --session -d org.kde.KWin -o /Scripting/Script$id -m org.kde.kwin.Script.run >/dev/null
C=/src/tests/window-frames/clients.py
S=${STATE:-}
if [ -n "${SHELL_BUILD:-}" ]; then
    # Fenestra Shell from /build (tests/shell-kwin builds it): the desktop and its icon labels on
    # a solid #1f1f1f wallpaper like the reference shots (solid/*-01-taskbar), in Spanish.
    cmake --install /build --prefix /usr >/dev/null
    install -Dm644 -t /usr/share/backgrounds/fenestra /src/assets/generated/wallpapers/*.jpg
    for d in branding search menu-icons status battery folders power osd security consent privacy; do
        install -Dm644 -t /usr/share/fenestra/assets/$d /src/assets/generated/$d/*.* 2>/dev/null
    done
    python3 -c "from PIL import Image; Image.new('RGB', (64, 64), '${DESK_BG:-#1f1f1f}').save('/tmp/solid.png')"
    mkdir -p ~/.config/fenestra ~/Desktop
    printf '[Appearance]\nWallpaper=/tmp/solid.png\nAccent=#647C64\n' > ~/.config/fenestra/shell.conf
    printf '[Desktop Entry]\nType=Application\nName=Microsoft Edge\nIcon=web-browser\nExec=true\n' > ~/Desktop/microsoft-edge.desktop
    LANG=${SHELL_LANG:-es_ES.UTF-8} QT_QPA_PLATFORM=wayland fenestra-shell > /out/shell.log 2>&1 &
    for i in $(seq 60); do grep -q FENESTRA_SHELL_READY /out/shell.log && break; sleep 0.5; done
    sleep 15  # wallpaper and icons load after READY
    env | grep -E '^(DBUS_SESSION_BUS_ADDRESS|WAYLAND_DISPLAY|DISPLAY)=' > /tmp/env
    [ -n "${KEEP:-}" ] && { echo READY > /out/ready; exec sleep infinity; }
    for try in 1 2 3; do timeout 30 python3 /src/tests/window-frames/shot.py /out/shot.png 0 0 $(python3 -c "print(round(${W:-2880}/${SCALE:-1.6}), round(${H:-1800}/${SCALE:-1.6}))") > /out/shot.log 2>&1 && break; done
    cat /out/shot.log
    exit 0
fi
QT_QPA_PLATFORM=wayland /usr/lib64/qt6/bin/qml /src/tests/window-frames/backdrop.qml >/out/backdrop.log 2>&1 &
sleep 1
QT_QPA_PLATFORM=wayland /usr/lib64/qt6/bin/qml /src/tests/window-frames/qt-ssd.qml >/out/qt.log 2>&1 &
python3 $C gtk3-ssd "GTK3 SSD" >/out/gtk3ssd.log 2>&1 &
GDK_BACKEND=x11 python3 $C gtk3-ssd "X11 SSD" >/out/x11.log 2>&1 &
python3 $C gtk4-adw "GTK4 Adw" $S >/out/adw.log 2>&1 &
python3 $C gtk4 "GTK4 HeaderBar" $S >/out/gtk4.log 2>&1 &
python3 $C gtk3-csd "GTK3 CSD" $S >/out/gtk3csd.log 2>&1 &
sleep ${WAIT:-6}
# The window under test gets the focus (ACTIVE=caption), the rest are inactive.
printf 'workspace.windowList().forEach(w => { if (w.caption === "%s") workspace.activeWindow = w; });\n' "${ACTIVE:-Qt SSD}" > /tmp/activate.js
id=$(gdbus call --session -d org.kde.KWin -o /Scripting -m org.kde.kwin.Scripting.loadScript /tmp/activate.js activate | grep -o '[0-9]\+')
gdbus call --session -d org.kde.KWin -o /Scripting/Script$id -m org.kde.kwin.Script.run >/dev/null; sleep 1
# activate one known window so the rest are inactive: GTK4 HeaderBar
env | grep -E '^(DBUS_SESSION_BUS_ADDRESS|WAYLAND_DISPLAY|DISPLAY)=' > /tmp/env
[ -n "${KEEP:-}" ] && { echo READY > /out/ready; exec sleep infinity; }
for try in 1 2 3; do timeout 30 python3 /src/tests/window-frames/shot.py /out/shot.png 0 0 $(python3 -c "print(round(${W:-2880}/${SCALE:-1.6}), round(${H:-1800}/${SCALE:-1.6}))") > /out/shot.log 2>&1 && break; done
cat /out/shot.log
INNER

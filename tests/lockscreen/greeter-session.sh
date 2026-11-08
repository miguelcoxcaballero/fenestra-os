#!/bin/bash
# Inside the KWin lab image (greeter-gl.sh): nested KWin with OpenGL, the Fenestra lock screen
# package, PAM stand-ins, then waits; ctl.sh starts the greeter, takes screenshots, sends input.
set -u
export XDG_RUNTIME_DIR=/tmp/xdg LANG=C.UTF-8 QT_FORCE_STDERR_LOGGING=1 XDG_CURRENT_DESKTOP=Fenestra XDG_SESSION_TYPE=wayland
mkdir -p -m700 $XDG_RUNTIME_DIR /out ~/.config
cat > ~/.config/kwinrc <<RC
[Compositing]
Backend=OpenGL
[Xwayland]
Scale=1
RC
printf '[Daemon]\nAutolock=false\nLockOnResume=false\nTimeout=0\n' > ~/.config/kscreenlockerrc
# The lock screen package as packaging/ installs it, Fenestra's open Hello frames and glyphs.
mkdir -p /usr/share/plasma/shells /usr/share/fenestra/assets
cp -r /src/shells/org.fenestra.desktop /usr/share/plasma/shells/
for d in hello security status battery; do mkdir -p /usr/share/fenestra/assets/$d; cp /src/assets/generated/$d/* /usr/share/fenestra/assets/$d/ 2>/dev/null; done
printf '[Shell]\nShellPackage=org.fenestra.desktop\n' > ~/.config/plasmashellrc
BG=/out/bg.jpg; [ -f $BG ] || BG=/src/assets/generated/wallpapers/fenestra-bloom-dark.jpg
printf '[Greeter][LnF][General]\nBackground=%s\nAccent=#0078D4\nSigninBlur=%s\n' "$BG" "${BLUR:-true}" >> ~/.config/kscreenlockerrc
fc-cache -f >/dev/null 2>&1
# PAM as packaging/lockscreen/fenestra-lock-hello sets it up: "kde" stock (pam_unix: root's
# "Fenestra1"), "kde-fingerprint" = pam_fenestra_hello.so with stand-ins for Howdy's compare.py and
# fprintd-verify. /tmp/face and /tmp/finger say what they do next: success | fail | wait | hang
# (hang = a camera that never delivers a frame / an fprintd that never answers); /tmp/face-delay:
# seconds the face takes.
echo 'root:Fenestra1' | chpasswd 2>/dev/null
usermod -c "Usuario Demo" root
printf 'auth substack password-auth\naccount include password-auth\npassword include password-auth\nsession include password-auth\n' > /etc/pam.d/kde
gcc -O2 -shared -fPIC -o /usr/lib64/security/pam_fenestra_hello.so /src/packaging/lockscreen/pam_fenestra_hello.c /usr/lib64/libpam.so.0
cat > /usr/local/bin/fake-compare <<'SH'
#!/bin/sh
m=$(cat /tmp/face 2>/dev/null); echo "face start $m $(date +%s.%N)" >> /out/pam.log
[ "$m" = hang ] && exec sleep infinity
d=$(cat /tmp/face-delay 2>/dev/null || echo 2)
for i in $(seq 1 $((d * 10))); do [ "$(cat /tmp/face)" = success ] && break; sleep 0.1; done
m=$(cat /tmp/face 2>/dev/null); echo "face end $m" >> /out/pam.log
[ "$m" = success ] && exit 0 || exit 11
SH
cat > /usr/local/bin/fake-fprintd-verify <<'SH'
#!/bin/sh
echo "finger start $(cat /tmp/finger) $(date +%s.%N)" >> /out/pam.log
[ "$(cat /tmp/finger 2>/dev/null)" = hang ] && exec sleep infinity
for i in $(seq 1 600); do
    s=$(cat /tmp/finger 2>/dev/null)
    [ "$s" = success ] && { echo finger success >> /out/pam.log; echo wait > /tmp/finger; exit 0; }
    [ "$s" = fail ] && { echo finger fail >> /out/pam.log; echo wait > /tmp/finger; exit 1; }
    [ "$s" = hang ] && exec sleep infinity
    sleep 0.1
done
exit 1
SH
chmod +x /usr/local/bin/fake-compare /usr/local/bin/fake-fprintd-verify
printf 'auth [success=done default=die] pam_fenestra_hello.so face_timeout=7 finger_timeout=25 face_tries=2 howdy=/usr/local/bin/fake-compare fprintd=/usr/local/bin/fake-fprintd-verify\naccount required pam_permit.so\n' > /etc/pam.d/kde-fingerprint
echo wait > /tmp/face; echo wait > /tmp/finger
# Input tool and the screenshot permission.
gcc -O2 -o /usr/local/bin/fakeinput /src/tests/lockscreen/fakeinput.c -I/tmp/fi $(mkdir -p /tmp/fi; \
    wayland-scanner client-header /usr/share/plasma-wayland-protocols/fake-input.xml /tmp/fi/fake-input-client-protocol.h; \
    wayland-scanner private-code /usr/share/plasma-wayland-protocols/fake-input.xml /tmp/fi/fake-input.c; echo /tmp/fi/fake-input.c) -lwayland-client -lm
PY=$(readlink -f /usr/bin/python3)
printf '[Desktop Entry]\nType=Application\nName=Bench shot\nExec=%s\nNoDisplay=true\nX-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2\n' "$PY" > /usr/share/applications/bench-shot.desktop
printf '[Desktop Entry]\nType=Application\nName=Bench input\nExec=/usr/local/bin/fakeinput\nNoDisplay=true\nX-KDE-Wayland-Interfaces=org_kde_kwin_fake_input\n' > /usr/share/applications/bench-input.desktop
exec dbus-run-session -- bash -s <<'INNER'
set -u
mkdir -p /run/dbus; rm -f /run/dbus/system_bus_socket; dbus-daemon --system --fork 2>/dev/null
# LOCKED=1: KWin starts the session locked, as fenestra-session does after GDM's autologin
# (packaging/lockscreen/fenestra-sign-in): KWin's own screen locker runs the greeter (no --testing).
export QML_IMPORT_PATH=/src/tests/lockscreen/mock-qml QT_FORCE_STDERR_LOGGING=1
kwin_wayland --virtual --socket wl-f --width ${W:-2880} --height ${H:-1800} ${LOCKED:+--lockscreen} > /out/kwin.log 2>&1 &
for i in $(seq 60); do [ -S $XDG_RUNTIME_DIR/wl-f ] && break; sleep 0.25; done
export WAYLAND_DISPLAY=wl-f
sleep 2
kscreen-doctor output.Virtual-0.scale.${SCALE:-1.5} >/dev/null 2>&1; sleep 1
env | grep -E '^(DBUS_SESSION_BUS_ADDRESS|WAYLAND_DISPLAY|XDG_RUNTIME_DIR)=' | sed 's/^/export /' > /tmp/env
echo "export LANG=${LOCKLANG:-es_ES.UTF-8} LANGUAGE=${LOCKLANG%%.*}" >> /tmp/env
echo READY > /out/ready
exec sleep infinity
INNER

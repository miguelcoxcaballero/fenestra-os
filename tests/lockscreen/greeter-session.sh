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
# Real PAM for the password (pam_unix, root's shadow entry); face and fingerprint stand-ins that
# talk like Howdy and fprintd (pam_exec stdout = PAM_TEXT_INFO). /tmp/face, /tmp/finger: what
# they answer next (success | fail | wait); /tmp/face-delay: seconds Howdy looks.
echo 'root:Fenestra1' | chpasswd 2>/dev/null
# The "kde" service as packaging/pam/kde-howdy makes it: Howdy first (here a stand-in), then the
# password (pam_unix: root's "Fenestra1").
printf 'auth sufficient pam_fakehowdy.so\nauth substack password-auth\naccount include password-auth\npassword include password-auth\nsession include password-auth\n' > /etc/pam.d/kde
usermod -c "Usuario Demo" root
gcc -O2 -shared -fPIC -o /usr/lib64/security/pam_fakehowdy.so /src/tests/lockscreen/pam_fakehowdy.c /usr/lib64/libpam.so.0
cat > /usr/local/bin/fake-fprint <<'SH'
#!/bin/sh
echo "Place your finger on the fingerprint reader"
for i in $(seq 1 600); do
    s=$(cat /tmp/finger 2>/dev/null)
    [ "$s" = success ] && { echo finger success >> /out/pam.log; rm -f /tmp/finger; exit 0; }
    [ "$s" = fail ] && { echo finger fail >> /out/pam.log; rm -f /tmp/finger; exit 1; }
    sleep 0.1
done
exit 1
SH
chmod +x /usr/local/bin/fake-fprint
for k in fingerprint:fake-fprint; do
    printf 'auth required pam_exec.so stdout quiet /usr/local/bin/%s\naccount required pam_permit.so\n' "${k#*:}" > /etc/pam.d/kde-${k%%:*}
done
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
kwin_wayland --virtual --socket wl-f --width ${W:-2880} --height ${H:-1800} > /out/kwin.log 2>&1 &
for i in $(seq 60); do [ -S $XDG_RUNTIME_DIR/wl-f ] && break; sleep 0.25; done
export WAYLAND_DISPLAY=wl-f
sleep 2
kscreen-doctor output.Virtual-0.scale.${SCALE:-1.5} >/dev/null 2>&1; sleep 1
env | grep -E '^(DBUS_SESSION_BUS_ADDRESS|WAYLAND_DISPLAY|XDG_RUNTIME_DIR)=' | sed 's/^/export /' > /tmp/env
echo "export LANG=${LOCKLANG:-es_ES.UTF-8} LANGUAGE=${LOCKLANG%%.*}" >> /tmp/env
echo READY > /out/ready
exec sleep infinity
INNER

#!/bin/bash
cp -a /stage/home/. /home/alex/; chown -R alex:alex /home/alex
mkdir -p /run/dbus; dbus-daemon --system --fork; sleep 0.5; python3 /stage/fakelogind.py & sleep 1
U=$(id -u alex); install -d -m700 -o alex /run/user/$U
runuser -u alex -- env XDG_RUNTIME_DIR=/run/user/$U HOME=/home/alex XDG_SESSION_ID=c1 dbus-run-session -- bash -c '
dconf load /org/gnome/shell/ < /stage/shell.ini; dconf load /org/gnome/desktop/interface/ < /stage/iface.ini
dconf load /org/gnome/desktop/background/ < /stage/bg.ini; dconf load /org/fenestra/ < /stage/fen.ini
dconf write /org/gnome/shell/enabled-extensions "$(cat /stage/en.txt)"
dconf write /org/gnome/shell/disable-user-extensions false
dconf write /org/gnome/shell/disable-extension-version-validation '${VALID:-true}'
timeout 85 gnome-shell --headless --virtual-monitor=1920x1080 --wayland --wayland-display=f45qa 2>&1' > /out/shell.log 2>&1
grep -aE "QA_|JS ERROR|JS WARNING|TypeError|ReferenceError|SyntaxError|Extension " /out/shell.log | cut -c1-300 | head -80

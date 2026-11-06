#!/bin/bash
# User session + lock screen on headless GNOME Shell with Fenestra's lock extensions.
set -u
mkdir -p /home/gdmtest/.local/share/gnome-shell/extensions /var/lib/windows-spotlight/images
cp -a /exts/. /home/gdmtest/.local/share/gnome-shell/extensions/
cp -a /t/lockqa@local /home/gdmtest/.local/share/gnome-shell/extensions/
[ -d /assets ] && mkdir -p /home/gdmtest/.local/share/fenestra && cp -a /assets /home/gdmtest/.local/share/fenestra/assets
chown -R gdmtest /home/gdmtest
H=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
python3 -c "from PIL import Image; Image.new('RGB',(1920,1080),(30,90,140)).save('/var/lib/windows-spotlight/images/$H.jpg')"
echo "{\"image\": \"/var/lib/windows-spotlight/images/$H.jpg\"}" > /var/lib/windows-spotlight/current.json
mkdir -p /run/dbus; dbus-daemon --system --fork; sleep 0.5
python3 /t/fakelogind.py & sleep 1
/usr/libexec/accounts-daemon >/dev/null 2>&1 & sleep 1
U=gdmtest; uid=$(id -u $U); install -d -m700 -o $U /run/user/$uid; chmod 777 /out
runuser -u $U -- env XDG_RUNTIME_DIR=/run/user/$uid HOME=/home/$U XDG_SESSION_ID=c1 dbus-run-session -- bash -c "
dconf write /org/gnome/shell/enabled-extensions \"[${EXTS}, 'lockqa@local']\"
dconf write /org/gnome/shell/disable-user-extensions false
timeout 50 gnome-shell --headless --virtual-monitor=1920x1080 --wayland --wayland-display=lockqa" > /out/shell.log 2>&1
grep -aE 'QA_|JS ERROR|TypeError|SyntaxError|ReferenceError|Extension [a-z-]+@' /out/shell.log | grep -v "lockqa@local state=1" | cut -c1-300

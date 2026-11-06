#!/bin/bash
# Headless GNOME Shell greeter (gdm session mode) with Fenestra's login extensions.
# Inside the fenestra-greeterlab container:  bash /t/run.sh SCENARIO
#   SCENARIO=ok        Spotlight background present
#   SCENARIO=nobg      background metadata missing (exercises the fail-safe)
set -u
SC=${1:-ok}
cp -a /exts/. /usr/share/gnome-shell/extensions/
cp -a /t/gdmqa@local /usr/share/gnome-shell/extensions/
chmod -R a+rX /usr/share/gnome-shell/extensions
mkdir -p /var/lib/windows-spotlight/images /var/lib/fenestra-spotlight/images
H=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
python3 -c "from PIL import Image; Image.new('RGB',(1920,1080),(30,90,140)).save('/var/lib/windows-spotlight/images/$H.jpg')"
cp /var/lib/windows-spotlight/images/$H.jpg /var/lib/fenestra-spotlight/images/
if [ "$SC" = ok ]; then
    for d in windows-spotlight fenestra-spotlight; do echo "{\"image\": \"/var/lib/$d/images/$H.jpg\"}" > /var/lib/$d/current.json; done
fi
mkdir -p /run/dbus; dbus-daemon --system --fork; sleep 0.5
python3 /t/fakelogind.py & sleep 1
/usr/libexec/accounts-daemon & sleep 1
U=gdmtest; uid=$(id -u $U); install -d -m700 -o $U /run/user/$uid; chmod 777 /out
EXTS=${EXTS:-"'single-user-gdm@local', 'windows-spotlight@local'"}
runuser -u $U -- env XDG_RUNTIME_DIR=/run/user/$uid HOME=/home/$U XDG_SESSION_ID=c1 XDG_SESSION_CLASS=greeter \
    QA_LOGIN_EXT="${QA_LOGIN_EXT:-single-user-gdm@local}" dbus-run-session -- bash -c "
dconf write /org/gnome/shell/enabled-extensions \"[$EXTS, 'gdmqa@local']\"
dconf write /org/gnome/shell/disable-user-extensions false
timeout 60 gnome-shell --headless --virtual-monitor=1920x1080 --wayland --mode=gdm --wayland-display=gdmqa" > /out/shell.log 2>&1
grep -aE 'QA_|JS ERROR|Fenestra login|TypeError|SyntaxError|ReferenceError|Extension [a-z-]+@' /out/shell.log | cut -c1-400

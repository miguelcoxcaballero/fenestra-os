#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Explorer open / save dialogs: a headless GNOME Shell in the fenestra-greeterlab image (see
# tests/greeter) with the repo's Explorer layer; an app-like client asks the FileChooser portal
# for "Save as" or "Open", the dialog (Nautilus + overlay) asks the shotqa probe for a
# screenshot, saved as OUT/NAME-1.png. Fails if the dialog never appears.
#   tests/explorer-dialogs/run.sh NAME [SaveFile|OpenFile] [light|dark] [OUT]
# The same dialog serves the Fenestra (KWin) session: only the portal routing differs.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
OUT=${4:-$REPO/tests/explorer-dialogs/out}
mkdir -p "$OUT"; rm -f "$OUT/$1-1.png"
docker run --rm --privileged -v "$REPO":/src:ro -v "$HERE":/w:ro -v "$OUT":/out -e NAME=$1 -e METHOD=${2:-SaveFile} -e SCHEME=${3:-light} fenestra-greeterlab bash -c '
cp -a /src/tests/explorer-dialogs/shotqa@local /usr/share/gnome-shell/extensions/; chmod -R a+rX /usr/share/gnome-shell/extensions
rm -f /usr/share/nautilus-python/extensions/*.py; cp /src/desktop/nautilus/python/*.py /usr/share/nautilus-python/extensions/
rm -rf /usr/share/fenestra/nautilus/overlay/51; cp -a /src/desktop/nautilus/overlay/51 /usr/share/fenestra/nautilus/overlay/51
cat > /usr/share/dbus-1/services/org.gnome.Nautilus.service <<SVC
[D-BUS Service]
Name=org.gnome.Nautilus
Exec=/usr/libexec/fenestra/fenestra-nautilus --gapplication-service
SVC
id alex >/dev/null 2>&1 || useradd -m -u 1000 -c "Alex Morgan" alex
# No RealtimeKit on the system bus (see tests/shell-kwin/session.sh): in a container it never
# answers, and xdg-desktop-portal blocks 3 x 25 s on it before exporting the FileChooser.
rm -f /usr/share/dbus-1/system-services/org.freedesktop.RealtimeKit1.service
mkdir -p /run/dbus /run/systemd/seats; rm -f /run/dbus/system_bus_socket /run/dbus/pid
dbus-daemon --system --fork; sleep 0.5
python3 /src/tests/greeter/fakelogind.py & sleep 1
/usr/libexec/accounts-daemon & sleep 1
chmod 777 /out
install -d -m700 -o alex /run/user/1000
runuser -u alex -- env XDG_RUNTIME_DIR=/run/user/1000 HOME=/home/alex XDG_SESSION_ID=c1 XDG_SESSION_CLASS=user XDG_SESSION_TYPE=wayland \
  LANG=es_ES.UTF-8 LC_ALL=es_ES.UTF-8 XDG_CURRENT_DESKTOP=GNOME dbus-run-session -- bash -c "
cd; rm -rf ~/.config/gtk-4.0; cp -r /src/desktop/skel/.config/gtk-4.0 ~/.config/; cp /src/desktop/gtk/caption-buttons-gtk4.css ~/.config/gtk-4.0/fenestra-caption-buttons.css; printf \"@define-color fenestra_accent_dark #4cc2ff;\\n@define-color fenestra_accent_light #0067c0;\\n@define-color fenestra_accent_dark_fg #000000;\\n@define-color fenestra_accent_light_fg #ffffff;\\n\" > ~/.config/gtk-4.0/fenestra-accent.css; mkdir -p Documentos Descargas Imágenes Música Vídeos Escritorio
LC_ALL=C xdg-user-dirs-update --force >/dev/null 2>&1 || true
for f in Documentos/Notas.txt Documentos/Presupuesto.ods Documentos/Informe-anual.pdf Descargas/fondo.jpg Descargas/instalador.rpm; do echo demo > ~/\$f; done
gsettings set org.gnome.desktop.interface color-scheme prefer-$SCHEME
python3 /w/enable-shotqa.py
# Services the shell starts (portals, Nautilus for the desktop icons) get the display up front.
export FENESTRA_CHOOSER_SHOT=$NAME WAYLAND_DISPLAY=w0
dbus-update-activation-environment WAYLAND_DISPLAY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP LANG LC_ALL FENESTRA_CHOOSER_SHOT
gnome-shell --headless --virtual-monitor=1280x800 --wayland --wayland-display=w0 > /tmp/shell.log 2>&1 &
for i in \$(seq 120); do grep -q SHOTQA /tmp/shell.log && break; sleep 0.5; done
python3 /w/portal-call.py $METHOD 30 > /tmp/call.log 2>&1 &
for i in \$(seq 160); do [ -f /out/$NAME-1.png ] && break; sleep 0.5; done
grep -a -E \"SHOTQA|JS ERROR\" /tmp/shell.log | tail -3; cat /tmp/call.log
"
'
[ -f "$OUT/$1-1.png" ] && echo "PASS $OUT/$1-1.png" || { echo "FAIL: no dialog screenshot"; exit 1; }

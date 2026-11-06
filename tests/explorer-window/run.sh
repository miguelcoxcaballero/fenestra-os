#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Explorer window bench: a headless GNOME Shell (1920x1080) in the fenestra-greeterlab image
# with the repo's Explorer layer (Nautilus + overlay + python + user CSS). Every JOB file is
# run in order against a fresh Nautilus window:
#   @scheme light|dark       colour scheme for this job (default: dark)
#   @open PATH|URI           location to open (default: ~), relative paths are under $HOME
#   @view FOLDER large|list|details|...   Explorer view remembered for ~/FOLDER
#   anything else            explorerqa@local script lines (see its extension.js)
# The window is placed at the reference box: frame 408,206 1123x632, so the 1 px outline GTK draws outside the frame lands on the reference border (407,205 1125x634) unless the job says `win ...`.
#   [LANGDIR=DIR] tests/explorer-window/run.sh OUT JOB...
# jobs/ holds one job per reference state (reference-shots apps/*-100-40-explorer-*), named
# after the screenshot it takes; the window's Documentos row is at (497, 522) here because the
# navigation pane has no OneDrive row.
# The image has no Spanish locale or translations (Nautilus' own strings come out in English);
# LANGDIR may hold usr/share/locale/es and usr/lib/locale/es_ES.utf8 unpacked from Fedora's
# glibc-langpack-es, nautilus, gtk4, libadwaita and glib2 packages, copied over the image's.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
OUT=$(realpath -m "$1"); shift
mkdir -p "$OUT/jobs"; chmod 777 "$OUT"
for j in "$@"; do cp "$j" "$OUT/jobs/"; done
LANGMNT=(); [ -n "${LANGDIR:-}" ] && LANGMNT=(-v "$(realpath "$LANGDIR")":/lang:ro)
docker run --rm --privileged "${LANGMNT[@]}" -v "$REPO":/src:ro -v "$HERE":/w:ro -v "$OUT":/out fenestra-greeterlab bash -c '
[ -d /lang/usr ] && cp -a /lang/usr/. /usr/
cp -a /w/explorerqa@local /usr/share/gnome-shell/extensions/; chmod -R a+rX /usr/share/gnome-shell/extensions
rm -f /usr/share/nautilus-python/extensions/*.py; cp /src/desktop/nautilus/python/*.py /w/fenestra_treedump.py /usr/share/nautilus-python/extensions/
rm -rf /usr/share/fenestra/nautilus/overlay/51; cp -a /src/desktop/nautilus/overlay/51 /usr/share/fenestra/nautilus/overlay/51
cat > /usr/share/dbus-1/services/org.gnome.Nautilus.service <<SVC
[D-BUS Service]
Name=org.gnome.Nautilus
Exec=/usr/libexec/fenestra/fenestra-nautilus --gapplication-service
SVC
id alex >/dev/null 2>&1 || useradd -m -u 1000 -c "Alex Morgan" alex
rm -f /usr/share/dbus-1/system-services/org.freedesktop.RealtimeKit1.service
mkdir -p /run/dbus /run/systemd/seats; rm -f /run/dbus/system_bus_socket /run/dbus/pid
dbus-daemon --system --fork; sleep 0.5
python3 /src/tests/greeter/fakelogind.py & sleep 1
/usr/libexec/accounts-daemon & sleep 1
install -d -m700 -o alex /run/user/1000
runuser -u alex -- env XDG_RUNTIME_DIR=/run/user/1000 HOME=/home/alex XDG_SESSION_ID=c1 XDG_SESSION_CLASS=user XDG_SESSION_TYPE=wayland \
  LANG=es_ES.UTF-8 LC_ALL=es_ES.UTF-8 XDG_CURRENT_DESKTOP=GNOME TZ=Europe/Madrid dbus-run-session -- bash /w/session.sh
'
ls "$OUT"/*.png 2>/dev/null | wc -l | xargs echo "screenshots:"

#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Open / save dialog bench on the host, no container: a headless GNOME Shell in its own
# dbus-run-session, its own XDG_RUNTIME_DIR, HOME and keyfile GSettings (the user's session, bus,
# dconf and Nautilus are never touched), the installed patched Nautilus with THIS checkout's
# overlay/51 + nautilus-python modules + gtk.css, and xdg-desktop-portal(-gnome) routed exactly as
# session/portals/fenestra-portals.conf routes them in the Fenestra session.
#   tests/explorer-dialogs/host.sh start OUT [dark|light] [SCALE] [WxH]   (default dark 1.5 2880x1800)
#   tests/explorer-dialogs/host.sh run OUT CMD...      run CMD inside that session (portal calls, apps)
#   tests/explorer-dialogs/host.sh job OUT NAME LINES  explorerqa script (tests/explorer-window/
#                                                      explorerqa@local): move/click/key/shot/burst...
#   tests/explorer-dialogs/host.sh stop OUT
# Screenshots land in OUT/ (stage pixels: 2880x1800 at 1.5 = the user's laptop). Needs the patched
# Nautilus (/usr/libexec/fenestra/nautilus, made by fenestra-patch-nautilus), gnome-shell,
# xdg-desktop-portal-gnome and nautilus-python installed; runs in fenestra-tests.slice when
# ~/.local/bin/fenestra-test-run exists.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
op=$1; OUT=$(realpath -m "$2"); shift 2
envf=$OUT/session.env
case $op in
run)
    # shellcheck disable=SC1090
    set -a; . "$envf"; set +a
    exec "$@" ;;
job)
    name=$1; shift
    rm -f "$OUT/$name.done"
    printf '%s\n' "$@" > "$OUT/req/$name.tmp" && mv "$OUT/req/$name.tmp" "$OUT/req/$name"
    for _ in $(seq 600); do [ -f "$OUT/$name.done" ] && exit 0; sleep 0.1; done
    echo "job $name timed out" >&2; exit 1 ;;
stop)
    # Everything started on that bus carries its XDG_RUNTIME_DIR.
    for p in $(pgrep -u "$(id -u)"); do
        grep -qz "^XDG_RUNTIME_DIR=$OUT/run\$" "/proc/$p/environ" 2>/dev/null && kill "$p" 2>/dev/null
    done
    sleep 1
    for m in "$OUT/run/gvfs" "$OUT/run/doc"; do mountpoint -q "$m" && fusermount3 -u "$m" 2>/dev/null; done
    exit 0 ;;
start) [ -d "$OUT/run" ] && "$0" stop "$OUT" ;;
*) sed -n 2,17p "$0"; exit 2 ;;
esac
SCHEME=${1:-dark}; SCALE=${2:-1.5}; SIZE=${3:-2880x1800}
rm -rf "$OUT"; mkdir -p "$OUT"/{home,run,req,tree,share/nautilus-python/extensions,share/xdg-desktop-portal,share/gnome-shell/extensions,share/dbus-1/services}
chmod 700 "$OUT/run"
H=$OUT/home
mkdir -p "$H"/.config/gtk-4.0 "$H"/.local/share "$H"/Documents "$H"/Downloads "$H"/Desktop "$H"/Pictures "$H"/Music "$H"/Videos
# Fonts and icon themes the user has (read-only use).
for d in fonts icons themes; do [ -e "$HOME/.local/share/$d" ] && ln -s "$HOME/.local/share/$d" "$OUT/share/$d"; done
cat > "$H/.config/user-dirs.dirs" <<'D'
XDG_DESKTOP_DIR="$HOME/Desktop"
XDG_DOWNLOAD_DIR="$HOME/Downloads"
XDG_DOCUMENTS_DIR="$HOME/Documents"
XDG_MUSIC_DIR="$HOME/Music"
XDG_PICTURES_DIR="$HOME/Pictures"
XDG_VIDEOS_DIR="$HOME/Videos"
D
printf 'Quarterly report (demo)\n' > "$H/Documents/Quarterly report.txt"
touch -d '2026-11-07 02:00' "$H/Documents/Quarterly report.txt"
# User CSS exactly as /etc/skel installs it, importing this checkout's theme.
sed "s|/usr/share/themes/Fenestra-Dark|$REPO/desktop/themes/Fenestra-Dark|" "$REPO/desktop/skel/.config/gtk-4.0/gtk.css" > "$H/.config/gtk-4.0/gtk.css"
cp "$REPO/desktop/gtk/caption-buttons-gtk4.css" "$H/.config/gtk-4.0/fenestra-caption-buttons.css"
if [ -f "$HOME/.config/gtk-4.0/fenestra-accent.css" ]; then cp "$HOME/.config/gtk-4.0/fenestra-accent.css" "$H/.config/gtk-4.0/"
else printf '@define-color fenestra_accent_dark #4cc2ff;\n@define-color fenestra_accent_light #0067c0;\n' > "$H/.config/gtk-4.0/fenestra-accent.css"; fi
cp "$REPO"/desktop/nautilus/python/*.py "$REPO/tests/explorer-window/fenestra_treedump.py" "$OUT/share/nautilus-python/extensions/"
cp -a "$REPO/tests/explorer-window/explorerqa@local" "$OUT/share/gnome-shell/extensions/"
cp "$REPO/session/portals/fenestra-portals.conf" "$OUT/share/xdg-desktop-portal/"
# Nautilus on this bus: the patched copy with this checkout's overlay (fenestra-nautilus, minus the
# installed overlay path).
cat > "$OUT/nautilus" <<N
#!/bin/bash
export G_RESOURCE_OVERLAYS="/org/gnome/nautilus=$REPO/desktop/nautilus/overlay/51"
# No AT-SPI bus here: GTK's fallback AT context has no announce() and Nautilus' "file already
# exists" label (Save over an existing name) would crash in gtk_accessible_announce.
export GTK_A11Y=none
exec /usr/libexec/fenestra/nautilus "\$@"
N
chmod +x "$OUT/nautilus"
printf '[D-BUS Service]\nName=org.gnome.Nautilus\nExec=%s --gapplication-service\n' "$OUT/nautilus" > "$OUT/share/dbus-1/services/org.gnome.Nautilus.service"
# Services a dialog bench does not need (calendar, accounts, indexer, phone/camera monitors):
# shadowed on this bus so they never start.
for svc in org.gnome.evolution.dataserver.Sources5 org.gnome.evolution.dataserver.Calendar8 \
           org.gnome.evolution.dataserver.AddressBook10 org.gnome.OnlineAccounts org.gnome.Identity \
           org.gnome.Shell.CalendarServer org.freedesktop.LocalSearch3 org.freedesktop.Tracker3.Miner.Files \
           org.gtk.vfs.GPhoto2VolumeMonitor org.gtk.vfs.AfcVolumeMonitor org.gtk.vfs.MTPVolumeMonitor \
           org.gtk.vfs.GoaVolumeMonitor org.freedesktop.IBus org.gnome.ScreenSaver; do
    printf '[D-BUS Service]\nName=%s\nExec=/bin/false\n' "$svc" > "$OUT/share/dbus-1/services/$svc.service"
done
cat > "$OUT/inner.sh" <<'INNER'
#!/bin/bash
set -u
cd "$HOME"
{ echo "DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS"; for v in HOME XDG_RUNTIME_DIR XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME XDG_DATA_DIRS XDG_CURRENT_DESKTOP XDG_SESSION_TYPE GSETTINGS_BACKEND LANG LC_ALL SHOTQA_REQ SHOTQA_OUT TREEDUMP_REQ; do echo "$v=${!v}"; done; echo WAYLAND_DISPLAY=$WLD; echo GDK_BACKEND=wayland; } > "$OUTD/session.env"
# Fenestra's dconf defaults (desktop/dconf/local.d/00-fenestra) for Files and the GTK chooser.
python3 - "$REPO/desktop/dconf/local.d/00-fenestra" <<'PY'
import configparser, subprocess, sys
c = configparser.ConfigParser(interpolation=None, strict=False); c.optionxform = str
c.read(sys.argv[1])
for path in c.sections():
    if path.startswith(('org/gnome/nautilus/', 'org/gtk/gtk4/settings/file-chooser', 'org/gnome/desktop/interface')):
        schema = path.replace('/', '.')
        for k, v in c[path].items():
            subprocess.run(['gsettings', 'set', schema, k, v], stderr=subprocess.DEVNULL)
PY
gsettings set org.gnome.desktop.interface color-scheme prefer-$SCHEME
gsettings set org.gnome.desktop.interface icon-theme 'Fenestra-Windows'
gsettings set org.gnome.desktop.interface font-name 'Segoe UI Variable 10'
gsettings set org.gnome.desktop.interface enable-animations true
gsettings set org.gnome.mutter experimental-features "['scale-monitor-framebuffer']"
gsettings set org.gnome.shell enabled-extensions "['explorerqa@local']"
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.shell welcome-dialog-last-shown-version '999'
gsettings set org.gnome.nautilus.preferences default-folder-viewer 'list-view'
# The bus learns about this checkout's Nautilus before anything activates it.
dbus-update-activation-environment XDG_CURRENT_DESKTOP XDG_DATA_DIRS XDG_SESSION_TYPE LANG LC_ALL GSETTINGS_BACKEND SHOTQA_REQ SHOTQA_OUT TREEDUMP_REQ HOME XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME WAYLAND_DISPLAY=$WLD
gnome-shell --headless --virtual-monitor="$SIZE" --wayland --no-x11 --wayland-display="$WLD" > "$OUTD/shell.log" 2>&1 &
echo $! > "$OUTD/shell.pid"
for _ in $(seq 120); do grep -q 'SHOTQA ready' "$OUTD/shell.log" && break; sleep 0.5; done
python3 - "$SCALE" <<'PY' >> "$OUTD/shell.log" 2>&1
import sys
from gi.repository import Gio, GLib
scale = float(sys.argv[1])
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
p = Gio.DBusProxy.new_sync(bus, 0, None, 'org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig', 'org.gnome.Mutter.DisplayConfig')
serial, monitors, logical, props = p.call_sync('GetCurrentState', None, 0, -1, None).unpack()
(conn, *_), modes, *_ = monitors[0]
mode = next(m for m in modes if m[6].get('is-current'))
scales = mode[5]
s = min(scales, key=lambda v: abs(v - scale))
cfg = [(0, 0, s, 0, True, [(conn, mode[0], {})])]
p.call_sync('ApplyMonitorsConfig', GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})', (serial, 1, cfg, {})), 0, -1, None)
print('SHOTQA scale', s, mode[0])
PY
# Portals as the Fenestra session starts them (xdg-desktop-portal reads XDG_CURRENT_DESKTOP=Fenestra
# -> fenestra-portals.conf: FileChooser = gnome -> Nautilus).
/usr/libexec/xdg-desktop-portal-gnome > "$OUTD/xdp-gnome.log" 2>&1 &
/usr/libexec/xdg-desktop-portal-gtk > "$OUTD/xdp-gtk.log" 2>&1 &
/usr/libexec/xdg-desktop-portal -r > "$OUTD/xdp.log" 2>&1 &
echo READY > "$OUTD/ready"
wait "$(cat "$OUTD/shell.pid")"
INNER
chmod +x "$OUT/inner.sh"
RUNNER=(); [ -x "$HOME/.local/bin/fenestra-test-run" ] && RUNNER=("$HOME/.local/bin/fenestra-test-run")
setsid "${RUNNER[@]}" env -i PATH=/usr/local/bin:/usr/bin:/bin REPO="$REPO" USER="$USER" LOGNAME="$USER" HOME="$H" \
    XDG_RUNTIME_DIR="$OUT/run" XDG_CONFIG_HOME="$H/.config" XDG_DATA_HOME="$OUT/share" \
    XDG_CACHE_HOME="$H/.cache" XDG_STATE_HOME="$H/.local/state" \
    XDG_DATA_DIRS="/usr/local/share:/usr/share" XDG_CURRENT_DESKTOP=Fenestra XDG_SESSION_TYPE=wayland \
    GSETTINGS_BACKEND=keyfile LANG=${BENCH_LANG:-en_GB.UTF-8} LC_ALL=${BENCH_LANG:-en_GB.UTF-8} \
    SHOTQA_REQ="$OUT/req" SHOTQA_OUT="$OUT" TREEDUMP_REQ="$OUT/tree" OUTD="$OUT" SCHEME="$SCHEME" SCALE="$SCALE" SIZE="$SIZE" \
    WLD="fdlg-$(basename "$OUT")" \
    dbus-run-session -- "$OUT/inner.sh" > "$OUT/session.log" 2>&1 < /dev/null &
echo $! > "$OUT/pid"
for _ in $(seq 120); do [ -f "$OUT/ready" ] && { grep SHOTQA "$OUT/shell.log"; echo "READY $OUT"; exit 0; }; sleep 0.5; done
echo "session did not start: $OUT/shell.log" >&2; tail -20 "$OUT/shell.log" >&2; exit 1

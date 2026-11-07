#!/bin/bash
# Fenestra Explorer (Nautilus) on a folder, in a throwaway headless GNOME Shell, for icon checks.
# Nothing of the user's session is touched: own D-Bus session (dbus-run-session), own dconf database
# (XDG_CONFIG_HOME in a temporary folder), own Wayland socket; the test-only unsafe-mode extension
# (tests/shell) comes from a temporary XDG_DATA_DIRS entry. The user's icon themes are read as they are.
#   tests/icon-pack/nautilus-shot.sh shot DIR OUT.png      (env NAUT=/usr/libexec/fenestra/fenestra-nautilus, ICON_THEME)
#   tests/icon-pack/nautilus-shot.sh resolve DIR SIZE       (GTK lookups only, under a headless mutter)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/cfg" "$T/ext/gnome-shell/extensions"; cp -r "$HERE/../shell/unsafe-mode@fenestra-tests" "$T/ext/gnome-shell/extensions/"
cat > "$T/inner.sh" <<'IN'
#!/bin/bash
gsettings set org.gnome.desktop.interface icon-theme "${ICON_THEME:-Fenestra-Windows}"
gsettings set org.gnome.desktop.interface color-scheme prefer-light
gsettings set org.gnome.desktop.interface enable-animations false
export WAYLAND_DISPLAY=fenestra-icon-check GDK_BACKEND=wayland XDG_SESSION_TYPE=wayland
if [ "$1" = resolve ]; then
    mutter --headless --wayland --no-x11 --wayland-display=$WAYLAND_DISPLAY --virtual-monitor 1280x720 >/dev/null 2>&1 & P=$!; sleep 3
    python3 "$HERE/resolve-gtk-icons.py" "$2" "$3"; kill $P; exit 0
fi
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.shell enabled-extensions "['unsafe-mode@fenestra-tests']"
gsettings set org.gnome.shell welcome-dialog-last-shown-version 999
E() { gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "$1"; }
gnome-shell --headless --wayland --no-x11 --wayland-display=$WAYLAND_DISPLAY --virtual-monitor 1920x1080 >/dev/null 2>&1 & P=$!
for i in $(seq 60); do E 1 2>/dev/null | grep -q true && break; sleep 1; done
E 'Main.messageTray.getSources().forEach(s=>s.destroy());Main.overview.hide();"ok"' >/dev/null
${NAUT:-/usr/libexec/fenestra/fenestra-nautilus} --new-window "$2" >/dev/null 2>&1 & sleep 8
E 'let w=global.display.focus_window;if(w){w.move_resize_frame(false,0,0,1920,1080);w.maximize();}"ok"' >/dev/null; sleep 3
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false "$3" >/dev/null
kill $P
IN
chmod +x "$T/inner.sh"
OUTARG=${3:-48}; [ "$1" = shot ] && OUTARG=$(realpath -m "$3")
HERE=$HERE env -u WAYLAND_DISPLAY -u DISPLAY XDG_CONFIG_HOME="$T/cfg" XDG_DATA_DIRS="$T/ext:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}" \
    dbus-run-session -- "$T/inner.sh" "$1" "$(realpath "$2")" "$OUTARG"

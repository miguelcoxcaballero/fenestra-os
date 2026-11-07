#!/bin/bash
# Inside the KWin lab image (popups-gl.sh): KWin --virtual with OpenGL compositing and the blur
# effect at SCALE, Fenestra Shell from /build with the user's wallpaper, fonts, icon theme and
# icon pack, demo apps named like the reference's pins, recent files and a Search history.
set -u
export XDG_RUNTIME_DIR=/tmp/xdg LANG=C.UTF-8 QT_FORCE_STDERR_LOGGING=1 XDG_CURRENT_DESKTOP=Fenestra XDG_SESSION_TYPE=wayland
export FENESTRA_SHELL_TEST=1 FENESTRA_SHELL_NO_ACTIVATION=1
mkdir -p -m700 $XDG_RUNTIME_DIR /out ~/.config ~/.local/share/applications ~/.local/state/windows-search
[ -e /home/${HOSTUSER:-x} ] || { mkdir -p /home; ln -s /root /home/${HOSTUSER:-x}; }
cat > ~/.config/kwinrc <<RC
[Compositing]
Backend=OpenGL
[Plugins]
blurEnabled=true
fadingpopupsEnabled=${FADINGPOPUPS:-true}
[Xwayland]
Scale=1
RC
printf '[Daemon]\nAutolock=false\nLockOnResume=false\nTimeout=0\n' > ~/.config/kscreenlockerrc
PY=$(readlink -f /usr/bin/python3)
cat > /usr/share/applications/fenestra-frame-shot.desktop <<DE
[Desktop Entry]
Type=Application
Name=Frame bench shot
Exec=$PY
NoDisplay=true
X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2
DE
cmake --install /build --prefix /usr >/dev/null
install -Dm644 -t /usr/share/backgrounds/fenestra /src/assets/generated/wallpapers/*.jpg
for d in branding search menu-icons status battery folders power osd security consent privacy; do
    install -Dm644 -t /usr/share/fenestra/assets/$d /src/assets/generated/$d/*.* 2>/dev/null
done
# Demo apps with the reference's names (icons of the user's Fenestra-Windows theme where it has one).
I=/root/.local/share/icons/Fenestra-Windows/256x256/apps
app() { # id name icon categories
    local icon=$3; [ -f "$I/$3.png" ] && icon=$I/$3.png
    printf '[Desktop Entry]\nType=Application\nName=%s\nIcon=%s\nExec=true\nCategories=%s;\n' "$2" "$icon" "$4" > ~/.local/share/applications/$1.desktop
}
app edge "Microsoft Edge" microsoft-edge Network
app word Word org.fenestra.Notepad Office
app excel Excel calculator Office
app powerpoint PowerPoint org.fenestra.Paint Office
app copilot Copilot m365-copilot Utility
app outlook Outlook outlook Office
app store "Microsoft Store" microsoft-store System
app photos Photos photos Graphics
app samsung-settings "Samsung Settings" fenestra-settings Settings
app samsung-notes "Samsung Notes" org.fenestra.Notepad Office
app quick-search "Quick Search" search-indexer Utility
app gallery Gallery org.gnome.Loupe Graphics
app settings Settings fenestra-settings Settings
app xbox XBOX xbox Game
app solitaire "Solitaire & Casual Games" game-bar Game
app spotify Spotify media-player AudioVideo
app chatgpt ChatGPT microsoft-teams Development
app cmd "Command Prompt" cmd System
kbuildsycoca6 --noincremental >/dev/null 2>&1
mkdir -p ~/Documents ~/Downloads
for f in "PL05 MIGUEL COX CABALLERO.nb" "ejemplo.nb" "sPL05 MIGUEL COX CABALLERO.nb" "PL05_MIGUEL_COX_CABALLERO.nb" "Informe.txt" "Notas.md" "Plan.txt" "Lista.txt"; do
    printf 'x' > ~/Documents/"$f"; done
printf 'x' > ~/Downloads/Hola.pdf
y=$(date -u -d yesterday +%Y-%m-%dT11:%M:00Z)
{
    echo '<?xml version="1.0" encoding="UTF-8"?><xbel version="1.0">'
    for f in "PL05 MIGUEL COX CABALLERO.nb" "ejemplo.nb" "sPL05 MIGUEL COX CABALLERO.nb" "PL05_MIGUEL_COX_CABALLERO.nb" "Informe.txt" "Notas.md" "Plan.txt" "Lista.txt"; do
        echo "<bookmark href=\"file:///root/Documents/$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$f")\" added=\"$y\" modified=\"$y\" visited=\"$y\"/>"
    done
    echo '</xbel>'
} > ~/.local/share/recently-used.xbel
python3 - <<'PY'
import json, time
now = int(time.time() * 1000); h = 3600 * 1000
apps = [("chatgpt", 17), ("cmd", 18), ("photos", 19), ("xbox", 19), ("edge", 22), ("outlook", 23), ("store", 25),
        ("spotify", 26), ("gallery", 30), ("copilot", 31), ("settings", 33), ("solitaire", 50)]
json.dump({"queries": [], "apps": [a + ".desktop" for a, _ in apps],
           "entries": [{"kind": "app", "value": a + ".desktop", "at": now - n * h} for a, n in apps]},
          open("/root/.local/state/windows-search/history.json", "w"))
PY
usermod -c "Miguel Cox" root 2>/dev/null
mkdir -p ~/.config/fenestra
WP=/out/wallpaper.${WPEXT:-png}; [ -f "$WP" ] || WP=/usr/share/backgrounds/fenestra/fenestra-bloom-dark.jpg
{
    printf '[Appearance]\nAccent=#647C64\nWallpaper=%s\n' "$WP"
    [ -n "${TRANSPARENCY:-}" ] && printf 'Transparency=%s\n' "$TRANSPARENCY"
    printf 'SearchIcon=/root/.local/share/fenestra/assets/search/search.png\n'
    printf '[Taskbar]\nTaskView=false\nPinned=org.gnome.Nautilus.desktop\nSearchMode=icon\n'
    printf '[Start]\nPinned=edge.desktop, word.desktop, excel.desktop, powerpoint.desktop, copilot.desktop, outlook.desktop, store.desktop, photos.desktop, samsung-settings.desktop, samsung-notes.desktop, quick-search.desktop, gallery.desktop, settings.desktop, xbox.desktop, solitaire.desktop, spotify.desktop, chatgpt.desktop, cmd.desktop\n'
} > ~/.config/fenestra/shell.conf

exec dbus-run-session -- bash -s <<'INNER'
set -u
mkdir -p /run/dbus; rm -f /run/dbus/system_bus_socket; dbus-daemon --system --fork 2>/dev/null
/usr/libexec/accounts-daemon >/dev/null 2>&1 &
# PipeWire for KWin's window screencasts (the taskbar's live previews), when the image has it.
if command -v pipewire >/dev/null; then
    pipewire > /out/pipewire.log 2>&1 &
    sleep 0.5; command -v wireplumber >/dev/null && wireplumber > /out/wireplumber.log 2>&1 &
fi
kwin_wayland --virtual --socket wl-f --width ${W:-2880} --height ${H:-1800} > /out/kwin.log 2>&1 &
for i in $(seq 60); do [ -S $XDG_RUNTIME_DIR/wl-f ] && break; sleep 0.25; done
export WAYLAND_DISPLAY=wl-f
sleep 2
kscreen-doctor output.Virtual-0.scale.${SCALE:-1.5} >/dev/null 2>&1; sleep 1
LANG=${SHELL_LANG:-en_GB.UTF-8} QT_QPA_PLATFORM=wayland fenestra-shell > /out/shell.log 2>&1 &
for i in $(seq 60); do grep -q FENESTRA_SHELL_READY /out/shell.log && break; sleep 0.5; done
env | grep -E '^(DBUS_SESSION_BUS_ADDRESS|WAYLAND_DISPLAY|XDG_RUNTIME_DIR)=' | sed 's/^/export /' > /tmp/env
echo READY > /out/ready
exec sleep infinity
INNER

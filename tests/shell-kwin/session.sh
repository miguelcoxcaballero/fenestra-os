#!/bin/bash
# Runs inside the KWin lab container (tests/shell-kwin/Containerfile): headless KWin
# (--virtual) + Fenestra Shell + test clients, screenshots and a QA verdict.
#   /src  repo (ro)    /build  CMake build dir of shell/    /out  logs and screenshots
set -u
# No GPU in the container or CI: QPainter compositing in KWin, llvmpipe for clients.
export KWIN_COMPOSE=${KWIN_COMPOSE:-Q} LIBGL_ALWAYS_SOFTWARE=1
# Without a terminal, Qt logs to the journal; the bench reads stderr.
export QT_FORCE_STDERR_LOGGING=1 QT_QUICK_BACKEND=${QT_QUICK_BACKEND:-software} LANG=C.UTF-8
export FENESTRA_SHELL_TEST=1 FENESTRA_SHELL_NO_ACTIVATION=1 XDG_RUNTIME_DIR=/tmp/xdg QT_QPA_PLATFORM=wayland XDG_CURRENT_DESKTOP=Fenestra XDG_SESSION_TYPE=wayland
mkdir -p -m700 "$XDG_RUNTIME_DIR" /out
rm -f /run/dbus/pid
W=${WIDTH:-1920} H=${HEIGHT:-1080}

# What the RPM will install (packaging/): binary, .desktop (window-management access), assets.
cmake --install /build --prefix /usr >/dev/null
install -Dm644 -t /usr/share/backgrounds/fenestra /src/assets/generated/wallpapers/*.jpg
for d in branding search menu-icons status battery folders power osd security consent privacy; do
    install -Dm644 -t /usr/share/fenestra/assets/$d /src/assets/generated/$d/*.* 2>/dev/null
done
# The apps, as the RPMs install them: launchers in PATH and their .desktop entries.
for a in notepad paint; do
    printf '#!/bin/sh\ncd /src/apps/fenestra-%s && exec python3 -B -m fenestra_%s "$@"\n' $a $a > /usr/bin/fenestra-$a
    chmod +x /usr/bin/fenestra-$a
    install -Dm644 -t /usr/share/applications /src/apps/fenestra-$a/data/*.desktop 2>/dev/null
done
for a in settings taskmgr; do
    printf '#!/bin/sh\ncd /src/apps/fenestra-%s && exec python3 -B -m fenestra_%s "$@"\n' $a $a > /usr/bin/fenestra-$a
    chmod +x /usr/bin/fenestra-$a
    install -Dm644 -t /usr/share/applications /src/apps/fenestra-$a/data/*.desktop 2>/dev/null
done
kbuildsycoca6 --noincremental >/dev/null 2>&1

mkdir -p ~/.config && touch ~/.config/gnome-initial-setup-done
# Demo data (never personal data): a user name and picture-less account, documents, a photo,
# a folder and recently used files for Start's Recommended and Search.
usermod -c "Usuario Demo" root 2>/dev/null
mkdir -p ~/Documents/Proyectos ~/Pictures ~/Downloads ~/.local/share ~/Desktop/Proyectos ~/Desktop/Vacía ~/Templates
printf 'Demo\n' > ~/Desktop/"Lista de tareas.txt"; printf 'x' > ~/Desktop/Proyectos/plan.txt
printf '' > ~/Templates/"Documento de texto.txt"
# Spotlight fixture: the daily picture as the GNOME layer's service writes it.
mkdir -p /var/lib/fenestra-spotlight/images
cp /usr/share/backgrounds/fenestra/fenestra-bloom-light.jpg /var/lib/fenestra-spotlight/images/$(printf '%064d' 0 | tr 0 a).jpg
printf '{"image": "/var/lib/fenestra-spotlight/images/%s.jpg"}\n' $(printf '%064d' 0 | tr 0 a) > /var/lib/fenestra-spotlight/current.json
printf 'Demo\n' > ~/Documents/"Informe trimestral.txt"
printf '# Notas\n' > ~/Documents/"Notas de la reunión.md"
cp /usr/share/backgrounds/fenestra/fenestra-bloom-light.jpg ~/Pictures/playa-verano.jpg
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
    echo '<?xml version="1.0" encoding="UTF-8"?><xbel version="1.0">'
    for f in "Documents/Informe trimestral.txt" "Documents/Notas de la reunión.md" "Pictures/playa-verano.jpg"; do
        echo "<bookmark href=\"file://$HOME/$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$f")\" added=\"$now\" modified=\"$now\" visited=\"$now\"/>"
    done
    echo '</xbel>'
} > ~/.local/share/recently-used.xbel

log() { echo "$*" | tee -a /out/checks.txt; }
check() { # name condition-command...
    local name=$1; shift
    if "$@"; then log "CHECK $name PASS"; else log "CHECK $name FAIL"; FAILS=$((FAILS+1)); fi
}
FAILS=0; : > /out/checks.txt
# Shell surfaces through the test probe, composed by anchors (KWin's ScreenShot2 needs OpenGL;
# with QPainter compositing KWin 6.8 crashes in RenderDevice::eglContext()).
shot() {
    gdbus call --session -d org.fenestra.Shell -o /org/fenestra/Shell/Test -m org.fenestra.Shell.Test.Grab "/out/$1" >/dev/null 2>>/out/probe.log &&
        python3 /src/tests/shell-kwin/compose.py "/out/$1" "/out/$1.png" >>/out/probe.log 2>&1
}
# A screenshot that must contain a surface of the given layer-shell scope (the flyout under test).
shot_with() { shot "$2" && grep -q "\"scope\": \"$1\"" "/out/$2/surfaces.json"; }
ready_count() { grep -c FENESTRA_SHELL_READY /out/shell.log; }
wait_for() { local i; for i in $(seq 1 "${2:-40}"); do eval "$1" && return 0; sleep 0.5; done; return 1; }

probe() { gdbus call --session -d org.fenestra.Shell -o /org/fenestra/Shell/Test -m org.fenestra.Shell.Test.Eval "$1" 2>&1; }
bar() { echo "screensView.objectAt(${2:-0}).taskbar.$1"; }
# TaskbarModel roles (Qt::UserRole + n): 257 storageId, 260 pinned, 261 windowCount.
role() { probe "TaskbarModel.data(TaskbarModel.index($1,0), $2)"; }
is() { [ "$1" = "('[$2]',)" ]; }  # gdbus prints the JSON result as ('[value]',)
conf() { mkdir -p ~/.config/fenestra; printf '%s\n' "$@" > ~/.config/fenestra/shell.conf.tmp && mv ~/.config/fenestra/shell.conf.tmp ~/.config/fenestra/shell.conf; sleep 1.5; }

session() {
    export WAYLAND_DISPLAY=wayland-fen
    # System bus + AccountsService (Start's account name), as on a real system.
    mkdir -p /run/dbus; rm -f /run/dbus/system_bus_socket; dbus-daemon --system --fork 2>/dev/null
    /usr/libexec/accounts-daemon >/dev/null 2>&1 &
    # Two keyboard layouts (KWin reads kxkbrc at start): the tray shows the layout indicator.
    mkdir -p ~/.config; printf '[Layout]\nUse=true\nLayoutList=es,us\n' > ~/.config/kxkbrc
    kwin_wayland --virtual --xwayland --socket wayland-fen --width "$W" --height "$H" --output-count "${OUTPUTS:-1}" > /out/kwin.log 2>&1 &
    KWIN=$!
    wait_for '[ -S $XDG_RUNTIME_DIR/wayland-fen ]' 60 || { log "CHECK kwin-start FAIL"; return 1; }
    log "CHECK kwin-start PASS"
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' 'SearchMode=box'
    fenestra-shell > /out/shell.log 2>&1 & SHELL_PID=$!
    check shell-ready wait_for 'grep -q FENESTRA_SHELL_READY /out/shell.log' 40
    check window-management wait_for 'grep -q "windowManagement=true\|FENESTRA_SHELL_WM available=true" /out/shell.log' 20
    check "screens-${OUTPUTS:-1}" wait_for "grep -q 'screens=${OUTPUTS:-1}' /out/shell.log" 10
    check B02-pinned-buttons wait_for 'is "$(probe "TaskbarModel.rowCount()")" 2' 20
    # B02: clicking a pinned button launches the app (KIO); its window joins that button.
    probe "TaskbarModel.activate(0)" >/dev/null
    check B02-launch-from-pinned wait_for 'grep -q "FENESTRA_SHELL_WINDOWS count=1" /out/shell.log' 60
    check B02-window-grouped-with-pinned wait_for 'is "$(role 0 261)" 1' 20
    # An app without a pinned button (X11, through Xwayland) gets its own button.
    X11DISPLAY=$(wait_for 'ls /tmp/.X11-unix/X* >/dev/null 2>&1' 20 && ls /tmp/.X11-unix | sed -n 's/^X/:/p' | head -1)
    DISPLAY=${X11DISPLAY:-:0} GDK_BACKEND=x11 python3 -B -c "
import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk
w=Gtk.Window(title='X11 client'); w.set_default_size(520,320); w.connect('destroy',Gtk.main_quit); w.show_all(); Gtk.main()" >/out/x11.log 2>&1 &
    check B02-unpinned-app-button wait_for 'is "$(probe "TaskbarModel.rowCount()")" 3' 60
    sleep 2
    # B08: an app's StatusNotifierItem shows in the overflow flyout; activation and its menu work.
    python3 /src/tests/shell-kwin/sni-item.py > /out/sni.log 2>&1 &
    check B08-tray-item wait_for 'is "$(probe "TrayItems.count")" 1' 20
    check B08-keyboard-layouts wait_for 'is "$(probe "KeyboardStatus.count")" 2' 20
    probe "TrayItems.activate(0, 10, 10)" >/dev/null
    check B08-tray-activate wait_for 'grep -q SNI_ACTIVATE /out/sni.log' 10
    probe "$(bar 'testOverflow()')" >/dev/null; sleep 1; check B08-overflow shot_with fenestra-flyout 01b-overflow
    probe "$(bar 'testCloseFlyouts()')" >/dev/null
    probe "screensView.objectAt(0).taskbar.children" >/dev/null
    probe "$(bar 'testMenuOfTray(0)')" >/dev/null; sleep 1; check B08-item-menu shot_with fenestra-flyout 01c-item-menu
    probe "TrayItems.triggerMenuItem(0, 2)" >/dev/null
    check B08-menu-event wait_for 'grep -q "SNI_MENU_CLICKED 2" /out/sni.log' 10
    probe "$(bar 'testCloseFlyouts()')" >/dev/null
    check screenshot shot 01-taskbar
    # B10: one taskbar and one wallpaper on every output.
    check B10-taskbar-per-output python3 -c "
import json, sys
s = json.load(open('/out/01-taskbar/surfaces.json'))
bars = {tuple(x['screen']) for x in s if x['scope'] == 'fenestra-taskbar'}
sys.exit(len(bars) != ${OUTPUTS:-1})"
    probe "$(bar 'testPreview(0)')" >/dev/null; sleep 1; check B03-preview shot_with fenestra-flyout 02-preview
    probe "$(bar 'testCloseFlyouts()')" >/dev/null
    probe "$(bar 'testButton(0).rightClicked()')" >/dev/null; sleep 1; check B02-app-menu shot_with fenestra-flyout 03-app-menu
    probe "$(bar 'testCloseFlyouts()')" >/dev/null
    probe "$(bar 'testBarMenu(900)')" >/dev/null; sleep 1; check B07-taskbar-menu shot_with fenestra-flyout 04-taskbar-menu
    probe "$(bar 'testCloseFlyouts()')" >/dev/null
    # B01, B06 and light mode, changed live through shell.conf (as Fenestra Settings does).
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' 'Alignment=left' 'SearchMode=icon'
    check B01-left-aligned shot 05-left-icon
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' 'SearchMode=iconLabel'
    check B06-icon-label shot 06-icon-label
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' 'SearchMode=hidden' '[Appearance]' 'ColorScheme=light' 'Wallpaper=/usr/share/backgrounds/fenestra/fenestra-bloom-light.jpg'
    check light-mode shot 07-light-hidden-search
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop'
    # Unpin from the menu path: the running Notepad keeps its (now unpinned) button.
    probe "TaskbarModel.togglePinned(0)" >/dev/null
    check B02-unpin wait_for 'grep -q "Pinned=org.fenestra.Paint.desktop$" ~/.config/fenestra/shell.conf' 10
    # ---- H3: Start and Search ----
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' 'SearchMode=box'
    st() { echo "screensView.objectAt(0).start.$1"; }
    se() { echo "screensView.objectAt(0).search.$1"; }
    gdbus call --session -d org.fenestra.Shell -o /org/fenestra/Shell -m org.fenestra.Shell.ToggleStart >/dev/null
    check S01-start-opens-from-dbus wait_for 'is "$(probe "$(st shown)")" true' 10
    check S01-start-pins wait_for '[ "$(probe "StartPins.apps.length")" != "('"'"'[0]'"'"',)" ]' 5
    check S01-recommended wait_for 'is "$(probe "RecentFiles.items.length")" 3' 10
    sleep 1; check S01-start shot_with fenestra-start 09-start
    probe "$(st 'testPowerMenu()')" >/dev/null; sleep 1; check S01-power-menu shot_with fenestra-flyout 09b-power-menu
    probe "$(st 'testCloseMenus()')" >/dev/null
    probe "$(st 'testAccountMenu()')" >/dev/null; sleep 1; check S01-account-menu shot_with fenestra-flyout 09c-account-menu
    probe "$(st 'testCloseMenus()')" >/dev/null
    probe "$(st 'allApps = true')" >/dev/null; sleep 1; check S01-all-category shot_with fenestra-start 10-all-category
    probe "$(st 'allView = "grid"')" >/dev/null; sleep 1; check S01-all-grid shot_with fenestra-start 11-all-grid
    probe "$(st 'allView = "list"')" >/dev/null; sleep 1; check S01-all-list shot_with fenestra-start 12-all-list
    probe "$(st 'close()')" >/dev/null; sleep 1
    check S02-start-closes wait_for 'is "$(probe "$(st shown)")" false' 5
    # Search: home, then results with the preview, files, photos and Settings pages.
    probe "$(se "openWith('')")" >/dev/null; sleep 1
    check S04-search-home shot_with fenestra-start 13-search-home
    probe "$(se "openWith('playa')")" >/dev/null
    check S05-finds-photo wait_for 'probe "Search.sections.map(s => s.items.map(i => i.kind).join()).join()" | grep -q photo' 20
    sleep 1; check S04-results-preview shot_with fenestra-start 14-results
    probe "$(se "openWith('display')")" >/dev/null
    probe "Search.filter = \"settings\"" >/dev/null
    check S05-finds-settings-page wait_for 'probe "Search.sections.map(s => s.items.map(i => i.kind).join()).join()" | grep -q setting' 30
    sleep 1; check S04-settings-filter shot_with fenestra-start 15-settings
    probe "Search.filter = \"all\"" >/dev/null
    probe "$(se "openWith('paint')")" >/dev/null
    check S05-finds-app wait_for 'is "$(probe "Search.best.kind")" \"app\"' 10
    probe "Search.activate(Search.best)" >/dev/null
    check S05-opens-app wait_for 'grep -q "FENESTRA_SHELL_WINDOWS count=3" /out/shell.log' 60
    check S04-history-saved wait_for 'grep -q paint ~/.local/state/windows-search/history.json' 5
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' '[Appearance]' 'ColorScheme=light' 'Wallpaper=/usr/share/backgrounds/fenestra/fenestra-bloom-light.jpg'
    gdbus call --session -d org.fenestra.Shell -o /org/fenestra/Shell -m org.fenestra.Shell.ToggleStart >/dev/null; sleep 1
    check S01-start-light shot_with fenestra-start 16-start-light
    probe "$(st 'close()')" >/dev/null
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop'
    # ---- H4: notifications, calendar, quick settings, media, OSD, Ctrl+Alt+Del ----
    notify() { # summary body [actions-json] [hints]
        gdbus call --session -d org.freedesktop.Notifications -o /org/freedesktop/Notifications \
            -m org.freedesktop.Notifications.Notify "${5:-Demo}" 0 "${6:-dialog-information}" "$1" "$2" "${3:-[]}" "${4:-{\}}" 5000
    }
    check N02-server-registered bash -c 'gdbus call --session -d org.freedesktop.Notifications -o /org/freedesktop/Notifications -m org.freedesktop.Notifications.GetServerInformation | grep -q Fenestra'
    notify "Reunión en 10 minutos" "Sala Norte, planta 2" '["open", "Abrir", "snooze", "Posponer"]' >/dev/null
    check N02-banner wait_for 'is "$(probe "Notifications.popups.length")" 1' 10
    sleep 1; check N02-banner-shot shot_with fenestra-toasts 17-banner
    notify "Captura de pantalla" "Demo" '[]' "{'image-path': <'$HOME/Pictures/playa-verano.jpg'>}" >/dev/null
    sleep 1; check Q04-image-notification shot_with fenestra-toasts 18-image-toast
    probe "Notifications.popups.map(p => Notifications.hidePopup(p.notificationId))" >/dev/null
    probe "ShellState.toggleCalendar(null, -1)" >/dev/null; sleep 1
    check N01-center-and-calendar shot_with fenestra-flyout 19-center
    check N01-history wait_for 'is "$(probe "Notifications.count")" 2' 5
    probe "Notifications.popups.map(p => Notifications.hidePopup(p.notificationId))" >/dev/null
    probe "Notifications.doNotDisturb = true" >/dev/null
    log "popups before DND test: $(probe "Notifications.popups.length") dnd: $(probe "Notifications.doNotDisturb")"
    notify "Silenciosa" "No debe salir como banner" >/dev/null; sleep 1
    log "popups after: $(probe "JSON.stringify(Notifications.popups)")"
    check N01-do-not-disturb wait_for 'is "$(probe "Notifications.popups.length")" 0' 3
    probe "Notifications.doNotDisturb = false" >/dev/null
    gdbus monitor --session -d org.freedesktop.Notifications > /out/notify-monitor.log 2>&1 & MON=$!
    sleep 0.5
    probe "Notifications.invoke(Notifications.data(Notifications.index(Notifications.count - 1, 0), 257), \"open\")" >/dev/null
    check N02-action-invoked wait_for 'grep -q "ActionInvoked" /out/notify-monitor.log' 5
    kill $MON 2>/dev/null
    probe "Notifications.startFocus(25)" >/dev/null
    check N01-focus-session wait_for '[ "$(probe "Notifications.focusRemaining > 1400")" = "('"'"'[true]'"'"',)" ]' 3
    probe "Notifications.endFocus()" >/dev/null
    probe "Notifications.clearAll()" >/dev/null
    check N01-clear-all wait_for 'is "$(probe "Notifications.count")" 0' 3
    probe "ShellState.toggleCalendar(null, -1)" >/dev/null
    python3 /src/tests/shell-kwin/mpris-player.py > /out/mpris.log 2>&1 & MPRIS=$!
    check Q02-media-player wait_for 'is "$(probe "Media.title")" "\"Canción de prueba\""' 10
    probe "ShellState.toggleQuickSettings(null, -1)" >/dev/null; sleep 1
    check Q01-quick-settings shot_with fenestra-flyout 20-quick-settings
    probe "Media.playPause()" >/dev/null
    check Q02-play-pause wait_for 'grep -q MPRIS_PLAYPAUSE /out/mpris.log' 5
    probe "ShellState.toggleQuickSettings(null, -1)" >/dev/null
    kill $MPRIS 2>/dev/null
    probe "screensView.objectAt(0).osd.show(\"volume\", 40)" >/dev/null; sleep 0.5
    check Q03-osd shot_with fenestra-osd 21-osd
    probe "securityScreen.open()" >/dev/null; sleep 1
    check Q05-security-screen shot_with fenestra-security 22-security
    probe "securityScreen.menu = \"power\"" >/dev/null; sleep 0.5
    check Q05-power-menu shot_with fenestra-security 22b-security-power
    probe "securityScreen.close()" >/dev/null
    # ---- H5: desktop ----
    dk() { echo "screensView.objectAt(0).desktop.$1"; }
    check D01-desktop-icons wait_for 'is "$(probe "DesktopModel.rowCount()")" 4' 10   # Recycle Bin + 3 entries
    sleep 1; check D01-desktop shot 23-desktop
    probe "$(dk 'testBackgroundMenu()')" >/dev/null; sleep 1; check D02-background-menu shot_with fenestra-flyout 24-desktop-menu
    probe "$(dk 'testCloseMenu()')" >/dev/null
    probe "$(dk 'testItemMenu(2)')" >/dev/null; sleep 1; check D02-item-menu shot_with fenestra-flyout 25-item-menu
    probe "$(dk 'testCloseMenu()')" >/dev/null
    probe "DesktopModel.newFolder()" >/dev/null
    check D01-new-folder wait_for '[ -d ~/Desktop/"New folder" ]' 5
    check D01-rename-starts wait_for '[ "$(probe "$(dk renaming)")" != "('"'"'[-1]'"'"',)" ]' 5
    probe "DesktopModel.rename($(probe "$(dk renaming)" | tr -dc 0-9), \"Fotos de demo\")" >/dev/null
    check D01-rename wait_for '[ -d ~/Desktop/"Fotos de demo" ]' 5
    probe "DesktopModel.moveTo(1, 3, 2)" >/dev/null
    check D01-move-remembered wait_for 'grep -q "\[3,2\]" ~/.config/fenestra/desktop-positions.json' 5
    probe "DesktopModel.trash([DesktopModel.rowCount() - 1])" >/dev/null
    check D01-trash wait_for '[ "$(ls ~/.local/share/Trash/files 2>/dev/null | wc -l)" -ge 1 ]' 10
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' '[Appearance]' 'Wallpaper=#0063b1'
    check D03-solid-colour wait_for 'is "$(probe "WallpaperSource.color")" "\"#0063b1\""' 5
    sleep 1; check D03-solid-shot shot 26-solid
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop' '[Appearance]' 'Wallpaper=spotlight'
    check D03-spotlight wait_for 'probe "WallpaperSource.image" | grep -q fenestra-spotlight/images' 5
    conf '[Taskbar]' 'Pinned=org.fenestra.Notepad.desktop, org.fenestra.Paint.desktop'
    # ---- H6: windows ----
    check W01-decoration-config wait_for 'grep -q "theme=__aurorae__svg__Fenestra-" ~/.config/kwinrc' 10
    check W04-switcher-config bash -c 'grep -q "LayoutName=fenestra" ~/.config/kwinrc'
    gdbus call --session -d org.kde.KWin -o /KWin -m org.kde.KWin.supportInformation > /out/kwin-support.txt 2>&1
    check W01-decoration-loaded bash -c 'grep -qi "Fenestra-Dark\|aurorae" /out/kwin-support.txt'
    probe "root.snapLayouts.open()" >/dev/null; sleep 1
    check W03-snap-layouts shot_with fenestra-snap 27-snap-layouts
    probe "root.snapLayouts.visible = false" >/dev/null
    # The X11 test window, active, into the left half of the work area (1920 × 1032).
    X11ROW=$(probe "(() => { for (let i = 0; i < WindowsModel.count; ++i) if (WindowsModel.data(WindowsModel.index(i, 0), 257) === 'X11 client') return i; return -1 })()" | tr -dc 0-9)
    probe "WindowsModel.activate($X11ROW)" >/dev/null; sleep 1
    probe "KWinIntegration.placeActiveWindow(Qt.rect(0, 0, 0.5, 1))" >/dev/null
    check W03-snap-left-half wait_for '[ "$(probe "(() => { const g = WindowsModel.data(WindowsModel.index('$X11ROW', 0), 266); return g.x + \",\" + g.width })()")" = "('"'"'[\"0,960\"]'"'"',)" ]' 10
    log "snapped geometry: $(probe "JSON.stringify(WindowsModel.data(WindowsModel.index($X11ROW, 0), 266))")"
    # L01: the lock screen gets the Fenestra look-and-feel and the current picture.
    check L01-lock-lnf bash -c 'grep -q "LookAndFeelPackage=org.fenestra.desktop" ~/.config/kdeglobals'
    check L01-lock-background bash -c 'grep -q "Background=/" ~/.config/kscreenlockerrc'
    # W05: first login curtain (fresh state, no setup window): black first, then gone.
    rm -f ~/.config/gnome-initial-setup-done
    probe "root.sessionSurfaces.curtain.active = true; root.sessionSurfaces.curtain.visible = true" >/dev/null; sleep 1
    check W05-curtain-shown shot_with fenestra-curtain 28-first-login
    check W05-curtain-lifts wait_for 'is "$(probe "root.sessionSurfaces.curtain.visible")" false' 20
    touch ~/.config/gnome-initial-setup-done
    # A shell crash must not take KWin or the windows down; a new shell picks the windows up again.
    kill -SEGV $SHELL_PID; sleep 2
    check kwin-survives-shell-crash kill -0 $KWIN
    check windows-survive-shell-crash bash -c 'pgrep -f fenestra_notepad >/dev/null'
    fenestra-shell >> /out/shell.log 2>&1 & SHELL_PID=$!
    check shell-restarted wait_for '[ "$(ready_count)" -ge 2 ]' 40
    check windows-after-restart wait_for 'awk "/FENESTRA_SHELL_READY/{r++} r==2 && /FENESTRA_SHELL_WINDOWS count=3/{f=1} END{exit !f}" /out/shell.log' 40
    sleep 2
    check screenshot-after-restart shot 08-after-restart
    if [ -n "${PERF:-}" ]; then
        kill $SHELL_PID 2>/dev/null; sleep 1
        bash /src/tests/perf/shell-idle.sh "${PERF_SECONDS:-30}" "${PERF_RUNS:-3}" > /out/perf.jsonl 2>/out/perf.err
        log "perf: $(cat /out/perf.jsonl | tr '\n' ' ')"
        pkill -x fenestra-shell
    fi
    kill $SHELL_PID $KWIN 2>/dev/null
}
export -f probe bar role conf is
export -f session log check shot shot_with ready_count wait_for
export W H
timeout "${TIMEOUT:-180}" dbus-run-session -- bash -c 'FAILS=0; session; exit $FAILS'
rc=$?
FAILS=$(grep -c "FAIL$" /out/checks.txt)
if [ "$rc" = 0 ] && [ "$FAILS" = 0 ]; then echo "QA_RESULT PASS" | tee /out/result.txt; else echo "QA_RESULT FAIL ($FAILS failed checks, rc=$rc)" | tee /out/result.txt; exit 1; fi

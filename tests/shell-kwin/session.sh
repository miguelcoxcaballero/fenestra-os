#!/bin/bash
# Runs inside the KWin lab container (tests/shell-kwin/Containerfile): headless KWin
# (--virtual) + Fenestra Shell + test clients, screenshots and a QA verdict.
#   /src  repo (ro)    /build  CMake build dir of shell/    /out  logs and screenshots
set -u
# No GPU in the container or CI: QPainter compositing in KWin, llvmpipe for clients.
export KWIN_COMPOSE=${KWIN_COMPOSE:-Q} LIBGL_ALWAYS_SOFTWARE=1
# Without a terminal, Qt logs to the journal; the bench reads stderr.
export QT_FORCE_STDERR_LOGGING=1 QT_QUICK_BACKEND=${QT_QUICK_BACKEND:-software} LANG=C.UTF-8
export FENESTRA_SHELL_TEST=1 XDG_RUNTIME_DIR=/tmp/xdg QT_QPA_PLATFORM=wayland XDG_CURRENT_DESKTOP=Fenestra XDG_SESSION_TYPE=wayland
mkdir -p -m700 "$XDG_RUNTIME_DIR" /out
rm -f /run/dbus/pid
W=${WIDTH:-1920} H=${HEIGHT:-1080}

# What the RPM will install (packaging/): binary, .desktop (window-management access), assets.
cmake --install /build --prefix /usr >/dev/null
install -Dm644 -t /usr/share/backgrounds/fenestra /src/assets/generated/wallpapers/*.jpg
install -Dm644 -t /usr/share/fenestra/assets/branding /src/assets/generated/branding/*

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
ready_count() { grep -c FENESTRA_SHELL_READY /out/shell.log; }
wait_for() { local i; for i in $(seq 1 "${2:-40}"); do eval "$1" && return 0; sleep 0.5; done; return 1; }

session() {
    export WAYLAND_DISPLAY=wayland-fen
    kwin_wayland --virtual --xwayland --socket wayland-fen --width "$W" --height "$H" > /out/kwin.log 2>&1 &
    KWIN=$!
    wait_for '[ -S $XDG_RUNTIME_DIR/wayland-fen ]' 60 || { log "CHECK kwin-start FAIL"; return 1; }
    log "CHECK kwin-start PASS"
    fenestra-shell > /out/shell.log 2>&1 & SHELL_PID=$!
    check shell-ready wait_for 'grep -q FENESTRA_SHELL_READY /out/shell.log' 40
    check window-management wait_for 'grep -q "windowManagement=true\|FENESTRA_SHELL_WM available=true" /out/shell.log' 20
    # Wayland GTK 4 client (Notepad) and an X11 client through Xwayland.
    (cd /src/apps/fenestra-notepad && GDK_BACKEND=wayland exec python3 -B -m fenestra_notepad >/out/notepad.log 2>&1) &
    X11DISPLAY=$(wait_for 'ls /tmp/.X11-unix/X* >/dev/null 2>&1' 20 && ls /tmp/.X11-unix | sed -n 's/^X/:/p' | head -1)
    DISPLAY=${X11DISPLAY:-:0} GDK_BACKEND=x11 python3 -B -c "
import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk
w=Gtk.Window(title='X11 client'); w.set_default_size(520,320); w.connect('destroy',Gtk.main_quit); w.show_all(); Gtk.main()" >/out/x11.log 2>&1 &
    check two-windows-in-taskbar wait_for 'grep -q "FENESTRA_SHELL_WINDOWS count=2" /out/shell.log' 60
    sleep 2
    check screenshot shot 01-session
    # A shell crash must not take KWin or the windows down; a new shell picks the windows up again.
    kill -SEGV $SHELL_PID; sleep 2
    check kwin-survives-shell-crash kill -0 $KWIN
    check windows-survive-shell-crash bash -c 'pgrep -f fenestra_notepad >/dev/null'
    fenestra-shell >> /out/shell.log 2>&1 & SHELL_PID=$!
    check shell-restarted wait_for '[ "$(ready_count)" -ge 2 ]' 40
    # After the second READY, the new shell must list both windows again.
    check windows-after-restart wait_for 'awk "/FENESTRA_SHELL_READY/{r++} r==2 && /FENESTRA_SHELL_WINDOWS count=2/{f=1} END{exit !f}" /out/shell.log' 40
    sleep 2
    check screenshot-after-restart shot 02-after-restart
    kill $SHELL_PID $KWIN 2>/dev/null
}
export -f session log check shot ready_count wait_for
export W H
timeout "${TIMEOUT:-180}" dbus-run-session -- bash -c 'FAILS=0; session; exit $FAILS'
rc=$?
FAILS=$(grep -c "FAIL$" /out/checks.txt)
if [ "$rc" = 0 ] && [ "$FAILS" = 0 ]; then echo "QA_RESULT PASS" | tee /out/result.txt; else echo "QA_RESULT FAIL ($FAILS failed checks, rc=$rc)" | tee /out/result.txt; exit 1; fi

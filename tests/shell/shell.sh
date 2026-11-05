#!/usr/bin/env bash
# Headless GNOME Shell with the Fenestra overlay, for fast desktop screenshots
# without a VM. Run it inside a Fedora 43 container where the overlay
# (build/out/rootfs) is installed and a test user exists (see docs/TESTING.md).
#
#   tests/shell/shell.sh start [USER]     start dbus + gnome-shell --headless (1920x1080)
#   tests/shell/shell.sh eval JS          run JS in the shell (unsafe mode)
#   tests/shell/shell.sh shot OUT.png     full-screen screenshot
#   tests/shell/shell.sh click X Y [BTN]  click (1 = left, 3 = right) through a virtual pointer
#   tests/shell/shell.sh key KEYSYM...    press keys, e.g. Super_L, Escape, Return, or type "text:hello"
#   tests/shell/shell.sh run CMD...       run an app inside the test session
#   tests/shell/shell.sh stop
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
U="${FENESTRA_SHELL_USER:-alex}"
uid() { id -u "$U"; }
envs() {
    local r="/run/user/$(uid)"
    echo "XDG_RUNTIME_DIR=$r DBUS_SESSION_BUS_ADDRESS=unix:path=$r/bus WAYLAND_DISPLAY=wayland-fenestra XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=GNOME GDK_BACKEND=wayland"
}
as_user() { runuser -u "$U" -- env $(envs) "$@"; }
gcall() { as_user gdbus call --session --dest org.gnome.Shell "$@"; }

case "${1:-}" in
  start)
    [ -n "${2:-}" ] && U="$2"
    [ -S /run/dbus/system_bus_socket ] || { mkdir -p /run/dbus; dbus-daemon --system --fork; }
    r="/run/user/$(uid)"; install -d -m700 -o "$U" "$r"
    ext="$(runuser -u "$U" -- sh -c 'echo $HOME')/.local/share/gnome-shell/extensions"
    runuser -u "$U" -- mkdir -p "$ext"
    runuser -u "$U" -- cp -r "$HERE/unsafe-mode@fenestra-tests" "$ext/"
    pgrep -u "$U" -x dbus-daemon >/dev/null || as_user dbus-daemon --session --address="unix:path=$r/bus" --fork
    as_user dconf write /org/gnome/shell/disable-user-extensions false
    cur="$(as_user gsettings get org.gnome.shell enabled-extensions)"
    case "$cur" in *unsafe-mode@fenestra-tests*) ;; *)
        as_user gsettings set org.gnome.shell enabled-extensions "$(python3 -c 'import ast,sys; l=ast.literal_eval(sys.argv[1].replace("@as ","")); l.append("unsafe-mode@fenestra-tests"); print(l)' "$cur")" ;;
    esac
    as_user sh -c 'nohup gnome-shell --headless --wayland --no-x11 --wayland-display=wayland-fenestra --virtual-monitor 1920x1080 --force-animations > "$XDG_RUNTIME_DIR/gnome-shell.log" 2>&1 &'
    for _ in $(seq 60); do gcall --object-path /org/gnome/Shell --method org.gnome.Shell.Eval 1 >/dev/null 2>&1 && break; sleep 1; done
    sleep 3
    # Drop the "System was put in unsafe mode" notification before screenshots.
    gcall --object-path /org/gnome/Shell --method org.gnome.Shell.Eval 'Main.messageTray.getSources().forEach(s=>s.destroy());"ok"' >/dev/null || true
    echo "gnome-shell running as $U (log: $r/gnome-shell.log)" ;;
  eval) shift; gcall --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "$*" ;;
  shot)
    out="$(realpath -m "$2")"; tmp="/tmp/fenestra-shot-$$.png"
    gcall --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false "$tmp" >/dev/null
    mv "$tmp" "$out"; echo "$out" ;;
  click)
    b="${4:-1}"
    js="const C=imports.gi.Clutter;const s=global.stage.context.get_backend().get_default_seat();"
    js+="global._fT??=s.create_virtual_device(C.InputDeviceType.POINTER_DEVICE);const d=global._fT;const t=global.get_current_time()*1000;"
    js+="d.notify_absolute_motion(t,$2,$3);d.notify_button(t+1000,$b,C.ButtonState.PRESSED);d.notify_button(t+2000,$b,C.ButtonState.RELEASED);'ok'"
    gcall --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "$js" ;;
  move)
    js="const C=imports.gi.Clutter;const s=global.stage.context.get_backend().get_default_seat();"
    js+="global._fT??=s.create_virtual_device(C.InputDeviceType.POINTER_DEVICE);global._fT.notify_absolute_motion(global.get_current_time()*1000,$2,$3);'ok'"
    gcall --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "$js" ;;
  key)
    shift
    for k in "$@"; do
      js="const C=imports.gi.Clutter;const s=global.stage.context.get_backend().get_default_seat();"
      js+="global._fK??=s.create_virtual_device(C.InputDeviceType.KEYBOARD_DEVICE);const d=global._fK;let t=global.get_current_time()*1000;"
      if [[ "$k" == text:* ]]; then
        txt="${k#text:}"
        js+="for(const ch of $(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$txt")){const v=C.unicode_to_keysym(ch.codePointAt(0));d.notify_keyval(t++,v,C.KeyState.PRESSED);d.notify_keyval(t++,v,C.KeyState.RELEASED);}'ok'"
      elif [[ "$k" == *+* ]]; then
        mod="${k%%+*}"; key="${k#*+}"
        js+="d.notify_keyval(t++,C.KEY_$mod,C.KeyState.PRESSED);d.notify_keyval(t++,C.KEY_$key,C.KeyState.PRESSED);d.notify_keyval(t++,C.KEY_$key,C.KeyState.RELEASED);d.notify_keyval(t++,C.KEY_$mod,C.KeyState.RELEASED);'ok'"
      else
        js+="d.notify_keyval(t++,C.KEY_$k,C.KeyState.PRESSED);d.notify_keyval(t++,C.KEY_$k,C.KeyState.RELEASED);'ok'"
      fi
      gcall --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "$js" >/dev/null
      sleep 0.3
    done ;;
  run) shift; as_user sh -c 'nohup "$@" >/dev/null 2>&1 &' _ "$@" ;;
  stop)
    pkill -u "$U" -x gnome-shell || true
    # Wait until it is gone (zombies don't count: containers often have no init to reap them).
    for _ in $(seq 30); do ps -u "$U" -o stat=,comm= | grep -v '^Z' | grep -qw gnome-shell || break; sleep 1; done ;;
  *) sed -n 2,11p "$0"; exit 1 ;;
esac

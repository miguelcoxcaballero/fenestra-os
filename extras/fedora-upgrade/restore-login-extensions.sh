#!/usr/bin/bash
# Bring back Fenestra's login-screen extensions on GNOME 51 (Fedora 45), one step at a time.
#
#   sudo bash restore-login-extensions.sh                 step 1: install the fixed copies, enable
#                                                         windows-spotlight@local only (background,
#                                                         lock-screen look); the login form stays GNOME's
#   sudo bash restore-login-extensions.sh --enable-login  step 2: also enable single-user-gdm@local
#                                                         (Fenestra clock curtain on the login screen)
#   sudo bash restore-login-extensions.sh --status        what is installed / enabled, nothing changes
#   sudo bash restore-login-extensions.sh --rollback      back to the state before step 1 (standard
#                                                         GNOME login, extensions parked as .disabled)
#
# Never restarts GDM or the computer (that would close your session): changes apply at the next
# login screen (log out, or restart when you choose). Every change is backed up first under
# /var/backups/fenestra-login-restore/<time>/ and the script can be run again safely.
#
# The fixed copies come from extras/fedora-upgrade/system-extensions/ (validated by
# tests/greeter/bench.sh on GNOME 51: login curtain, fail-safe and lock screen).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
SRC="$HERE/system-extensions"
EXT_DIR=/usr/share/gnome-shell/extensions
PARK=/usr/share/gnome-shell                     # where the rescue parked <uuid>.disabled
GDM_DB=/etc/dconf/db/gdm.d
BACKUPS=/var/backups/fenestra-login-restore
LOG=/var/log/fenestra-login-restore.log
SPOT=windows-spotlight@local
LOGIN=single-user-gdm@local

say() { echo "$*"; echo "$(date -Is) $*" >> "$LOG"; }
die() { say "ERROR: $*"; exit 1; }
[ "$(id -u)" = 0 ] || die "run with sudo"

shell_major() { gnome-shell --version 2>/dev/null | grep -o '[0-9]\+' | head -1; }

# The gdm keyfile that sets org/gnome/shell enabled-extensions (created if none).
gdm_keyfile() {
    local f
    f=$(grep -l '^enabled-extensions' "$GDM_DB"/* 2>/dev/null | head -1 || true)
    echo "${f:-$GDM_DB/90-fenestra-login-extensions}"
}

current_list() {
    local f; f=$(gdm_keyfile)
    [ -f "$f" ] && sed -n 's/^enabled-extensions *= *//p' "$f" | head -1
}

set_list() {  # python-style list, e.g. ['a@b']
    local f; f=$(gdm_keyfile)
    if [ -f "$f" ] && grep -q '^enabled-extensions' "$f"; then
        sed -i "s|^enabled-extensions *=.*|enabled-extensions=$1|" "$f"
    else
        install -d "$GDM_DB"
        printf '[org/gnome/shell]\nenabled-extensions=%s\n' "$1" >> "$f"
    fi
    dconf update
    say "gdm enabled-extensions = $1 ($f)"
}

check_copy() {  # uuid: fixed copy exists, declares this GNOME, no unguarded set_file
    local uuid=$1 major; major=$(shell_major)
    [ -d "$SRC/$uuid" ] || die "fixed copy missing: $SRC/$uuid"
    python3 - "$SRC/$uuid/metadata.json" "$major" <<'PY' || die "$1 does not declare GNOME $(shell_major)"
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if sys.argv[2] in [str(v).split('.')[0] for v in d.get('shell-version', [])] else 1)
PY
    if grep -l 'set_file(' "$SRC/$uuid"/*.js 2>/dev/null | xargs -r grep -L 'HAS_SET_FILE' | grep -q .; then
        die "$uuid still calls Meta.Background.set_file without the GNOME 51 guard"
    fi
}

status() {
    echo "GNOME Shell: $(gnome-shell --version 2>/dev/null)"
    echo "GDM enabled-extensions: $(current_list || true)  [$(gdm_keyfile)]"
    for u in $SPOT $LOGIN; do
        printf '%-26s installed: %-3s parked: %s\n' "$u" \
            "$([ -d "$EXT_DIR/$u" ] && echo yes || echo no)" "$([ -d "$PARK/$u.disabled" ] && echo yes || echo no)"
    done
    echo "Hello frames: $([ -f /usr/share/fenestra/assets/hello/frames.json ] && echo present || echo MISSING)"
    echo "Login-screen guard: $(systemctl is-enabled fenestra-greeter-guard.service 2>/dev/null || echo not installed)"
    [ -x "$GUARD_DIR/fenestra-login-guard" ] && python3 "$GUARD_DIR/fenestra-login-guard" status | head -20
    echo "Last backup: $(ls -1d "$BACKUPS"/*/ 2>/dev/null | tail -1 || echo none)"
    # User copies of lock/login extensions that still use the removed API.
    for f in /home/*/.local/share/gnome-shell/extensions/*/face.js; do
        [ -f "$f" ] || continue
        if grep -q 'set_file(' "$f" && ! grep -q 'HAS_SET_FILE' "$f"; then
            echo "WARNING: $(dirname "$f") calls set_file without the GNOME 51 guard (lock screen may fail)"
        fi
    done
}

backup() {
    local b="$BACKUPS/$(date +%Y%m%d-%H%M%S)"
    install -d -m 0700 "$b"
    cp -a "$GDM_DB" "$b/gdm.d" 2>/dev/null || install -d "$b/gdm.d"
    current_list > "$b/enabled-extensions.txt" || true
    for u in $SPOT $LOGIN; do
        [ -d "$EXT_DIR/$u" ] && cp -a "$EXT_DIR/$u" "$b/installed-$u"
        [ -d "$PARK/$u.disabled" ] && echo "$u" >> "$b/parked.txt"
    done
    for a in hello status; do
        [ -d /usr/share/fenestra/assets/$a ] && echo yes > "$b/had-$a" || echo no > "$b/had-$a"
    done
    say "backup: $b"
    echo "$b"
}

install_copy() {
    local uuid=$1
    rm -rf "$EXT_DIR/$uuid.new"
    cp -a "$SRC/$uuid" "$EXT_DIR/$uuid.new"
    # Not used by the code (frames come from /usr/share/fenestra/assets/hello).
    rm -rf "$EXT_DIR/$uuid.new/hello-assets"
    rm -rf "$EXT_DIR/$uuid"
    mv "$EXT_DIR/$uuid.new" "$EXT_DIR/$uuid"
    chmod -R u+rwX,go+rX,go-w "$EXT_DIR/$uuid"
    say "installed $EXT_DIR/$uuid"
}

install_assets() {
    if [ ! -f /usr/share/fenestra/assets/hello/frames.json ]; then
        install -d /usr/share/fenestra/assets
        cp -a "$REPO/assets/generated/hello" /usr/share/fenestra/assets/hello
        say "installed /usr/share/fenestra/assets/hello (Fenestra's own frames)"
    fi
    if [ ! -d /usr/share/fenestra/assets/status ]; then
        cp -a "$REPO/assets/generated/status" /usr/share/fenestra/assets/status
        say "installed /usr/share/fenestra/assets/status"
    fi
    chmod -R a+rX /usr/share/fenestra/assets
}

# The safety net goes in first: if a re-enabled extension ever breaks the login screen, the
# guard turns that one off (and only that one) in the greeter settings.
GUARD_DIR=/usr/local/libexec/fenestra
GUARD_UNIT=/etc/systemd/system/fenestra-greeter-guard.service
NOTICE=/etc/xdg/autostart/fenestra-release-upgrade-user.desktop
install_guard() {
    install -d "$GUARD_DIR"
    install -m755 "$REPO/desktop/libexec/fenestra-login-guard" "$GUARD_DIR/fenestra-login-guard"
    install -m644 "$REPO/extras/compat/login-extensions.json" "$GUARD_DIR/login-extensions.json"
    install -m755 "$REPO/desktop/libexec/fenestra-release-upgrade-user" "$GUARD_DIR/fenestra-release-upgrade-user"
    sed "s|/usr/libexec/fenestra/fenestra-login-guard|$GUARD_DIR/fenestra-login-guard|" \
        "$REPO/desktop/systemd/fenestra-greeter-guard.service" > "$GUARD_UNIT"
    if [ ! -f /usr/share/applications/fenestra-release-upgrade-user.desktop ] && [ ! -f "$NOTICE" ]; then
        sed "s|^Exec=.*|Exec=$GUARD_DIR/fenestra-release-upgrade-user|" \
            "$REPO/desktop/autostart/fenestra-release-upgrade-user.desktop" > "$NOTICE"
    fi
    systemctl daemon-reload 2>/dev/null || true
    systemctl enable fenestra-greeter-guard.service 2>/dev/null || true   # runs from the next GDM start
    say "installed the login-screen guard ($GUARD_DIR, $GUARD_UNIT)"
}
remove_guard() {
    systemctl disable fenestra-greeter-guard.service 2>/dev/null || true
    rm -f "$GUARD_UNIT"
    systemctl daemon-reload 2>/dev/null || true
    say "login-screen guard disabled (kept in $GUARD_DIR)"
}

relabel() { restorecon -R "$EXT_DIR" /usr/share/fenestra /etc/dconf 2>/dev/null || true; }

step1() {
    check_copy $SPOT; check_copy $LOGIN
    local b; b=$(backup | tail -1)
    [ -f "$GUARD_UNIT" ] || echo new > "$b/guard-installed"
    install_guard
    install_copy $SPOT
    install_copy $LOGIN
    install_assets
    # Only now that the fixed copies are in place: move the parked ones into the backup.
    for u in $SPOT $LOGIN; do
        if [ -d "$PARK/$u.disabled" ]; then mv "$PARK/$u.disabled" "$b/parked-$u"; say "moved $PARK/$u.disabled to $b"; fi
    done
    set_list "['$SPOT']"
    relabel
    cat <<EOF

Step 1 done: windows-spotlight is installed and enabled for the login screen; the login form
is still GNOME's. Nothing was restarted.

Check (in this order):
  1. Lock the screen (Super+L) and unlock: the lock screen shows the Spotlight picture,
     and unlocking works as before.
  2. Log out (or restart when it suits you). On the login screen: the Spotlight picture
     behind GNOME's user list, and you can sign in.
If something is wrong: switch to a text console (Ctrl+Alt+F3), sign in and run
     sudo bash $0 --rollback
then log out / restart again.
When both checks are fine, run step 2:  sudo bash $0 --enable-login
EOF
}

step2() {
    [ -d "$EXT_DIR/$SPOT" ] && [ -d "$EXT_DIR/$LOGIN" ] || die "run step 1 first"
    check_copy $LOGIN
    backup >/dev/null
    set_list "['$LOGIN', '$SPOT']"
    relabel
    cat <<EOF

Step 2 done: single-user-gdm is enabled too. Nothing was restarted.

Check: log out (or restart). The login screen shows Fenestra's clock over the picture; press a
key or click and your account's password field appears. If the curtain ever fails, the
extension itself falls back to GNOME's standard login (tested), and a text console still works:
     Ctrl+Alt+F3, sign in, sudo bash $0 --rollback
EOF
}

rollback() {
    local b; b=$(ls -1d "$BACKUPS"/*/ 2>/dev/null | head -1 || true)   # the oldest = before step 1
    [ -n "$b" ] || die "no backup in $BACKUPS"
    b=${b%/}
    say "rollback to $b"
    rm -rf "$GDM_DB"; cp -a "$b/gdm.d" "$GDM_DB"
    for u in $SPOT $LOGIN; do
        if [ -d "$b/parked-$u" ]; then
            rm -rf "$EXT_DIR/$u"; rm -rf "$PARK/$u.disabled"; mv "$b/parked-$u" "$PARK/$u.disabled"
            say "restored $PARK/$u.disabled"
        elif [ -d "$b/installed-$u" ]; then
            rm -rf "$EXT_DIR/$u"; cp -a "$b/installed-$u" "$EXT_DIR/$u"
        else
            [ -d "$EXT_DIR/$u" ] && mv "$EXT_DIR/$u" "$b/removed-$u-$(date +%s)"
        fi
    done
    for a in hello status; do
        if [ "$(cat "$b/had-$a" 2>/dev/null)" = no ] && [ -d /usr/share/fenestra/assets/$a ]; then
            mv /usr/share/fenestra/assets/$a "$b/removed-assets-$a-$(date +%s)"; say "removed /usr/share/fenestra/assets/$a (was not there before)"
        fi
    done
    [ -f "$b/guard-installed" ] && remove_guard
    dconf update
    relabel
    echo "Rolled back (standard GNOME login at the next login screen). Nothing was restarted."
}

case "${1:-}" in
    "") step1 ;;
    --enable-login) step2 ;;
    --status) status ;;
    --rollback) rollback ;;
    *) sed -n 2,18p "$0"; exit 1 ;;
esac

#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Installs the Fenestra session (KWin + Fenestra Shell) from this repository, NEXT TO GNOME:
#   sudo bash extras/fenestra-session/install-session.sh            build and install
#   sudo bash extras/fenestra-session/install-session.sh --dry-run  show what would happen
#   sudo bash extras/fenestra-session/install-session.sh --rollback remove exactly what it installed
#   sudo bash extras/fenestra-session/install-session.sh --status
# It never changes GDM, the default session, GNOME or existing files: "Fenestra" just appears in
# GDM's session menu (gear icon) on the next sign-in. Choose it there to try it; GNOME stays one
# click away. Idempotent: running it again rebuilds and reinstalls the same files.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
STATE=/var/lib/fenestra/session-install
MANIFEST=$STATE/installed-files.txt
PKGS_FILE=$STATE/installed-packages.txt
BUILD=$STATE/build
MODE=install
case "${1:-}" in --dry-run) MODE=dry ;; --rollback) MODE=rollback ;; --status) MODE=status ;; "") ;; *) echo "usage: $0 [--dry-run|--rollback|--status]"; exit 2 ;; esac
[ "$(id -u)" = 0 ] || { echo "Run it with sudo."; exit 1; }

# Runtime + build packages (Fedora). Only the missing ones are installed and recorded.
DEPS="kwin xorg-x11-server-Xwayland layer-shell-qt layer-shell-qt-devel qt6-qtbase-devel qt6-qtbase-private-devel
qt6-qtdeclarative-devel qt6-qtwayland-devel qt6-qtsvg plasma-wayland-protocols-devel wayland-devel extra-cmake-modules
cmake gcc-c++ ninja-build kf6-kservice-devel kf6-kio-devel kf6-kwindowsystem-devel kf6-networkmanager-qt-devel
kf6-bluez-qt-devel pulseaudio-qt-qt6-devel kf6-kglobalaccel-devel kf6-kconfig-devel polkit-qt6-1-devel libgweather-devel
kscreenlocker kscreen xdg-desktop-portal-kde xdg-desktop-portal-gtk"

status() {
    echo "Session file: $([ -f /usr/share/wayland-sessions/fenestra.desktop ] && echo present || echo absent)"
    echo "Installed files recorded: $([ -f "$MANIFEST" ] && wc -l < "$MANIFEST" || echo 0)"
    echo "Packages installed by this script: $([ -f "$PKGS_FILE" ] && tr '\n' ' ' < "$PKGS_FILE" || echo none)"
}

if [ $MODE = status ]; then status; exit 0; fi

if [ $MODE = rollback ]; then
    [ -f "$MANIFEST" ] || { echo "Nothing recorded; nothing to remove."; exit 0; }
    # Users who made Fenestra their default go back to GNOME first.
    for f in /var/lib/AccountsService/users/*; do
        [ -f "$f" ] && grep -q '^Session=fenestra' "$f" && sed -i 's/^Session=fenestra$/Session=gnome/' "$f" && echo "GNOME again for $(basename "$f")"
    done
    while read -r f; do [ -e "$f" ] && rm -f -- "$f"; done < "$MANIFEST"
    rm -f "$MANIFEST"
    if [ -s "$PKGS_FILE" ]; then
        echo "These packages were installed for the session: $(tr '\n' ' ' < "$PKGS_FILE")"
        echo "Remove them too with: sudo dnf remove $(tr '\n' ' ' < "$PKGS_FILE")"
    fi
    echo "Fenestra session removed. GDM, GNOME and your files were not touched."
    exit 0
fi

missing=$(for p in $DEPS; do rpm -q "$p" >/dev/null 2>&1 || echo "$p"; done | tr '\n' ' ')
echo "Packages to install: ${missing:-none}"
if [ $MODE = dry ]; then
    [ -n "$missing" ] && dnf install --assumeno $missing 2>&1 | tail -5 || true
    echo "Would build $REPO/shell into $BUILD and install under /usr (session file, shell, KWin decoration and"
    echo "switcher, lock screen, user units, portals config, migrator). Existing files are never overwritten."
    exit 0
fi

mkdir -p "$STATE"
if [ -n "$missing" ]; then
    dnf install -y $missing
    printf '%s\n' $missing >> "$PKGS_FILE"
fi
python3 "$REPO/tools/build-aurorae-theme.py" >/dev/null
cmake -S "$REPO/shell" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr >/dev/null
ninja -C "$BUILD"
# Refuse to overwrite anything this script did not install before.
DESTDIR="$STATE/stage" cmake --install "$BUILD" >/dev/null
( cd "$STATE/stage" && find . -type f -o -type l ) | sed 's|^\.||' | sort > "$STATE/new-files.txt"
conflicts=$(while read -r f; do
    if [ -e "$f" ] && ! grep -qxF "$f" "$MANIFEST" 2>/dev/null; then echo "$f"; fi
done < "$STATE/new-files.txt")
if [ -n "$conflicts" ]; then
    echo "Not installing: these files already exist and are not from this script:"; echo "$conflicts"; exit 1
fi
cmake --install "$BUILD" >/dev/null
touch "$MANIFEST"
sort -u "$STATE/new-files.txt" "$MANIFEST" > "$STATE/m.tmp" && mv "$STATE/m.tmp" "$MANIFEST"
rm -rf "$STATE/stage" "$STATE/new-files.txt"
restorecon -RF /usr/bin/fenestra-shell /usr/libexec/fenestra /usr/share/wayland-sessions 2>/dev/null || true
status
echo
echo "Done. Sign out, click your name in GDM, choose \"Fenestra\" with the gear icon and sign in."
echo "GNOME is still the default; to undo everything: sudo bash $0 --rollback"

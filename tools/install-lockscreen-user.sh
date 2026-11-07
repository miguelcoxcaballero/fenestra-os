#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Installs Fenestra's lock screen (shells/org.fenestra.desktop) for the current user only, no root:
#   ~/.local/share/plasma/shells/org.fenestra.desktop     the lock screen package
#   ~/.config/plasmashellrc [Shell] ShellPackage          kscreenlocker takes the lock screen from it
#   ~/.config/kscreenlockerrc [Greeter][LnF][General]     Picture (today's Spotlight photo), Accent
#   ~/.local/share/fenestra/assets/hello-windows          the Hello animation made from the user's
#                                                         own searching.gif / authentication.gif
#                                                         (HELLO_SRC=dir; never part of Fenestra)
# What it replaces is saved once, before the first install, in ~/.local/share/fenestra/backup-lockscreen/<date>/.
# Takes effect at the next lock; nothing running is restarted. Undo: --remove (restores the backup).
# Face sign-in also needs root once: packaging/lockscreen/fenestra-lock-hello enable.
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
DATA=${XDG_DATA_HOME:-$HOME/.local/share}
CONF=${XDG_CONFIG_HOME:-$HOME/.config}
PKG=$DATA/plasma/shells/org.fenestra.desktop
BK=$DATA/fenestra/backup-lockscreen

if [ "${1:-}" = --remove ]; then
    last=$(ls -1d "$BK"/*/ 2>/dev/null | head -1)   # the state before the first install
    rm -rf "$PKG" "$DATA/fenestra/assets/hello-windows"
    if [ -n "$last" ]; then
        for f in plasmashellrc kscreenlockerrc; do [ -f "$last/$f" ] && cp -p "$last/$f" "$CONF/$f"; done
        [ -d "$last/org.fenestra.desktop" ] && cp -a "$last/org.fenestra.desktop" "$PKG"
        [ -d "$last/hello-windows" ] && cp -a "$last/hello-windows" "$DATA/fenestra/assets/hello-windows"
        echo "restored $last"
    fi
    exit 0
fi

stamp=$(ls -1 "$BK" 2>/dev/null | head -1)
if [ -z "$stamp" ]; then
    stamp=$(date +%Y%m%d-%H%M%S); mkdir -p "$BK/$stamp"
    for f in plasmashellrc kscreenlockerrc; do [ -f "$CONF/$f" ] && cp -p "$CONF/$f" "$BK/$stamp/"; done
    [ -d "$PKG" ] && cp -a "$PKG" "$BK/$stamp/"
    [ -d "$DATA/fenestra/assets/hello-windows" ] && cp -a "$DATA/fenestra/assets/hello-windows" "$BK/$stamp/"
fi

mkdir -p "$(dirname "$PKG")"
rm -rf "$PKG.new"; cp -a "$REPO/shells/org.fenestra.desktop" "$PKG.new"
rm -rf "$PKG"; mv "$PKG.new" "$PKG"

if [ -n "${HELLO_SRC:-}" ]; then
    python3 -I "$REPO/tools/hello-atlas.py" "$HELLO_SRC" "$DATA/fenestra/assets/hello-windows"
fi

kwriteconfig6 --file plasmashellrc --group Shell --key ShellPackage org.fenestra.desktop
# Today's Spotlight photo, as Fenestra Shell writes it (KWinIntegration::applyLockScreen).
pick_spotlight() {
    python3 -I -c '
import json, os, re
ok = re.compile(r"^/(var/lib/windows-spotlight/images/[a-f0-9]{64}|var/lib/fenestra-spotlight/images/[a-f0-9]{64}|usr/share/backgrounds/fenestra/[A-Za-z0-9._-]+)[.]jpg$")
for state in ("/var/lib/windows-spotlight/current.json", "/var/lib/fenestra-spotlight/current.json"):
    try:
        p = json.load(open(state))["image"]
    except (OSError, ValueError, KeyError):
        continue
    if ok.match(p) and os.path.exists(p):
        print(p)
        break
'
}
pic=$(pick_spotlight)
[ -n "$pic" ] && kwriteconfig6 --file kscreenlockerrc --group Greeter --group LnF --group General --key Picture "$pic"
accent=$(kreadconfig6 --file "$CONF/fenestra/shell.conf" --group Appearance --key Accent 2>/dev/null)
kwriteconfig6 --file kscreenlockerrc --group Greeter --group LnF --group General --key Accent "${accent:-#0078D4}"
echo "lock screen installed (backup: $BK/$stamp); picture: ${pic:-none, the desktop picture}"

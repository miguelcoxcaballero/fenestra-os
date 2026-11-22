#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Parsec's X/Y fix for Xbox controllers (xbox-buttons.c), for the user who runs it: built into
# Parsec's own folder and preloaded into the Parsec Flatpak only. Does nothing without Parsec.
# Undo: flatpak override --user --unset-env=LD_PRELOAD com.parsecgaming.parsec
set -eu
APP=com.parsecgaming.parsec
flatpak info "$APP" >/dev/null 2>&1 || { echo "Parsec (Flatpak) is not installed: nothing to do"; exit 0; }
SRC=$(cd "$(dirname "$0")" && pwd)
# ~/.var/app/<app> is visible at the same path inside the sandbox
DIR="$HOME/.var/app/$APP/fenestra"
mkdir -p "$DIR"
cc -O2 -shared -fPIC -Wall -o "$DIR/xbox-buttons.so.new" "$SRC/xbox-buttons.c" -ldl
mv "$DIR/xbox-buttons.so.new" "$DIR/xbox-buttons.so"
flatpak override --user --env=LD_PRELOAD="$DIR/xbox-buttons.so" "$APP"
echo "Parsec: X and Y of Xbox controllers fixed (restart Parsec)"

#!/bin/bash
# tools/install-electron-captions.sh: for the current user, builds the Electron caption-button fix
# (desktop/lib/electron-captions) into ~/.local/lib/fenestra and puts a launcher in ~/.local/bin
# (first in the session's PATH) for each installed Electron app that draws its own title bar, so
# the menu, the taskbar and links all start it through the fix. No root, nothing in /usr touched.
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
LIB=$HOME/.local/lib/fenestra
mkdir -p "$LIB" "$HOME/.local/bin"
cc -shared -fPIC -O2 -Wall -o "$LIB/fenestra-electron-captions.so" "$REPO/desktop/lib/electron-captions/fenestra-electron-captions.c" -ldl
install -m755 "$REPO/desktop/bin/fenestra-electron-run" "$HOME/.local/bin/fenestra-electron-run"
# command name -> the real program (titleBarStyle "hidden" + titleBarOverlay apps).
APPS="claude-desktop:/usr/lib/claude-desktop/claude-desktop"
for entry in $APPS; do
    name=${entry%%:*}; real=${entry#*:}
    [ -x "$real" ] || continue
    printf '#!/bin/sh\n# Fenestra: %s without GNOME circles behind its caption buttons (fenestra-electron-run).\nexec "$HOME/.local/bin/fenestra-electron-run" %s "$@"\n' "$name" "$real" > "$HOME/.local/bin/$name"
    chmod +x "$HOME/.local/bin/$name"
    echo "launcher: ~/.local/bin/$name"
done

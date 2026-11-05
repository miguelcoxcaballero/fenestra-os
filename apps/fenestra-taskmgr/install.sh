#!/bin/sh
# Install Fenestra Task Manager.
#   PREFIX  (default /usr)   installation prefix (PREFIX=$HOME/.local works for a per-user install)
#   DESTDIR (default empty)  staging root for packaging
# Example: DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh
set -eu
PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
SRC="$(cd "$(dirname "$0")" && pwd)"
SHARE="$DESTDIR$PREFIX/share/fenestra-taskmgr"

install -d "$SHARE/data/icons/ui" "$SHARE/data/icons/hicolor/scalable/apps" "$DESTDIR$PREFIX/bin" \
    "$DESTDIR$PREFIX/share/applications" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-taskmgr"

rm -rf "$SHARE/fenestra_taskmgr"
cp -r "$SRC/fenestra_taskmgr" "$SHARE/"
find "$SHARE/fenestra_taskmgr" -name '__pycache__' -type d -prune -exec rm -rf {} +
# Precompile: Task Manager is opened when the machine is busy, don't compile on every start.
python3 -m compileall -q "$SHARE/fenestra_taskmgr" >/dev/null 2>&1 || true

install -m 0644 "$SRC/data/style.css" "$SHARE/data/style.css"
install -m 0644 "$SRC"/data/icons/ui/*.svg "$SHARE/data/icons/ui/"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.TaskManager.svg" \
    "$SHARE/data/icons/hicolor/scalable/apps/org.fenestra.TaskManager.svg"

install -m 0755 "$SRC/bin/fenestra-taskmgr" "$DESTDIR$PREFIX/bin/fenestra-taskmgr"
install -m 0644 "$SRC/data/org.fenestra.TaskManager.desktop" \
    "$DESTDIR$PREFIX/share/applications/org.fenestra.TaskManager.desktop"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.TaskManager.svg" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps/org.fenestra.TaskManager.svg"
install -m 0644 "$SRC/LICENSES/fluentui-system-icons-MIT.txt" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-taskmgr/fluentui-system-icons-MIT.txt"

if [ -z "$DESTDIR" ]; then
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$PREFIX/share/applications" 2>/dev/null || true
fi
echo "Fenestra Task Manager installed to $DESTDIR$PREFIX"

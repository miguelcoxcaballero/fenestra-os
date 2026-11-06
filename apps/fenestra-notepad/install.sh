#!/bin/sh
# Install Fenestra Notepad.
#   PREFIX  (default /usr)   installation prefix (PREFIX=$HOME/.local works for a per-user install)
#   DESTDIR (default empty)  staging root for packaging
# Example: DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh
# Runtime dependencies: python3, python3-gobject, gtk4, gtksourceview5.
set -eu
PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
SRC="$(cd "$(dirname "$0")" && pwd)"
SHARE="$DESTDIR$PREFIX/share/fenestra-notepad"

install -d "$SHARE/data/icons/ui" "$SHARE/data/icons/hicolor/scalable/apps" "$SHARE/data/styles" \
    "$DESTDIR$PREFIX/bin" \
    "$DESTDIR$PREFIX/share/applications" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-notepad"

rm -rf "$SHARE/fenestra_notepad"
cp -r "$SRC/fenestra_notepad" "$SHARE/"
find "$SHARE/fenestra_notepad" -name '__pycache__' -type d -prune -exec rm -rf {} +
python3 -m compileall -q "$SHARE/fenestra_notepad" >/dev/null 2>&1 || true

install -m 0644 "$SRC/data/style.css" "$SHARE/data/style.css"
install -m 0644 "$SRC"/data/icons/ui/*.svg "$SHARE/data/icons/ui/"
install -m 0644 "$SRC"/data/styles/*.xml "$SHARE/data/styles/"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.Notepad.svg" \
    "$SHARE/data/icons/hicolor/scalable/apps/org.fenestra.Notepad.svg"

install -m 0755 "$SRC/bin/fenestra-notepad" "$DESTDIR$PREFIX/bin/fenestra-notepad"
install -m 0644 "$SRC/data/org.fenestra.Notepad.desktop" \
    "$DESTDIR$PREFIX/share/applications/org.fenestra.Notepad.desktop"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.Notepad.svg" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps/org.fenestra.Notepad.svg"
install -m 0644 "$SRC/LICENSES/fluentui-system-icons-MIT.txt" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-notepad/fluentui-system-icons-MIT.txt"

if [ -z "$DESTDIR" ]; then
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$PREFIX/share/applications" 2>/dev/null || true
fi
echo "Fenestra Notepad installed to $DESTDIR$PREFIX"

#!/bin/sh
# Install Fenestra Paint.
#   PREFIX  (default /usr)   installation prefix (PREFIX=$HOME/.local works for a per-user install)
#   DESTDIR (default empty)  staging root for packaging
# Example: DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh
set -eu
PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
SRC="$(cd "$(dirname "$0")" && pwd)"
SHARE="$DESTDIR$PREFIX/share/fenestra-paint"

install -d "$SHARE/data/icons/ui" "$SHARE/data/icons/hicolor/scalable/apps" "$DESTDIR$PREFIX/bin" \
    "$DESTDIR$PREFIX/share/applications" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-paint"

rm -rf "$SHARE/fenestra_paint"
cp -r "$SRC/fenestra_paint" "$SHARE/"
find "$SHARE/fenestra_paint" -name '__pycache__' -type d -prune -exec rm -rf {} +
python3 -m compileall -q "$SHARE/fenestra_paint" >/dev/null 2>&1 || true

install -m 0644 "$SRC/data/style.css" "$SHARE/data/style.css"
install -m 0644 "$SRC"/data/icons/ui/*.svg "$SHARE/data/icons/ui/"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.Paint.svg" \
    "$SHARE/data/icons/hicolor/scalable/apps/org.fenestra.Paint.svg"

install -m 0755 "$SRC/bin/fenestra-paint" "$DESTDIR$PREFIX/bin/fenestra-paint"
install -m 0644 "$SRC/data/org.fenestra.Paint.desktop" \
    "$DESTDIR$PREFIX/share/applications/org.fenestra.Paint.desktop"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.Paint.svg" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps/org.fenestra.Paint.svg"
install -m 0644 "$SRC/LICENSES/fluentui-system-icons-MIT.txt" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-paint/fluentui-system-icons-MIT.txt"

if [ -z "$DESTDIR" ]; then
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$PREFIX/share/applications" 2>/dev/null || true
fi
echo "Fenestra Paint installed to $DESTDIR$PREFIX"

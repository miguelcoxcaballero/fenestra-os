#!/bin/sh
# Install Fenestra Store.
#   PREFIX  (default /usr)   installation prefix (PREFIX=$HOME/.local works for a per-user install)
#   DESTDIR (default empty)  staging root for packaging
# Example: DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh
# Runtime: python3-gobject, gtk4, python3-cairo; optional: flatpak-libs (Flathub),
# PackageKit-glib + PackageKit (Fedora RPMs), appstream (AppStream reader), appstream-data.
set -eu
PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
SRC="$(cd "$(dirname "$0")" && pwd)"
SHARE="$DESTDIR$PREFIX/share/fenestra-store"

install -d "$SHARE/data/icons/ui" "$SHARE/data/icons/hicolor/scalable/apps" "$DESTDIR$PREFIX/bin" \
    "$DESTDIR$PREFIX/share/applications" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-store"

rm -rf "$SHARE/fenestra_store"
cp -r "$SRC/fenestra_store" "$SHARE/"
find "$SHARE/fenestra_store" -name '__pycache__' -type d -prune -exec rm -rf {} +
python3 -m compileall -q "$SHARE/fenestra_store" >/dev/null 2>&1 || true

install -m 0644 "$SRC/data/style.css" "$SHARE/data/style.css"
install -m 0644 "$SRC"/data/icons/ui/*.svg "$SHARE/data/icons/ui/"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.Store.svg" \
    "$SHARE/data/icons/hicolor/scalable/apps/org.fenestra.Store.svg"

install -m 0755 "$SRC/bin/fenestra-store" "$DESTDIR$PREFIX/bin/fenestra-store"
install -m 0644 "$SRC/data/org.fenestra.Store.desktop" \
    "$DESTDIR$PREFIX/share/applications/org.fenestra.Store.desktop"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/org.fenestra.Store.svg" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps/org.fenestra.Store.svg"
install -m 0644 "$SRC/LICENSES/GPL-3.0-or-later.txt" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-store/GPL-3.0-or-later.txt"

if [ -z "$DESTDIR" ]; then
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$PREFIX/share/applications" 2>/dev/null || true
fi
echo "Fenestra Store installed to $DESTDIR$PREFIX"

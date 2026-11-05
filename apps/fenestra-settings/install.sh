#!/bin/sh
# Install Fenestra Settings.
#   PREFIX  (default /usr)   installation prefix
#   DESTDIR (default empty)  staging root for packaging
# Example: DESTDIR=/tmp/pkg PREFIX=/usr ./install.sh
set -eu
PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
SRC="$(cd "$(dirname "$0")" && pwd)"
SHARE="$DESTDIR$PREFIX/share/fenestra-settings"

install -d "$SHARE" "$DESTDIR$PREFIX/bin" \
    "$DESTDIR$PREFIX/share/applications" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-settings"

# Python package (without caches)
rm -rf "$SHARE/fenestra_settings"
cp -r "$SRC/fenestra_settings" "$SHARE/"
find "$SHARE/fenestra_settings" -name '__pycache__' -type d -prune -exec rm -rf {} +

# Data: stylesheet + bundled icons
install -d "$SHARE/data/icons/fluent"
install -m 0644 "$SRC/data/style.css" "$SHARE/data/style.css"
install -m 0644 "$SRC"/data/icons/fluent/*.svg "$SHARE/data/icons/fluent/"

# Launcher, desktop entry, app icon, licenses
install -m 0755 "$SRC/bin/fenestra-settings" "$DESTDIR$PREFIX/bin/fenestra-settings"
install -m 0644 "$SRC/data/fenestra-settings.desktop" "$DESTDIR$PREFIX/share/applications/fenestra-settings.desktop"
install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/fenestra-settings.svg" \
    "$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps/fenestra-settings.svg"
install -m 0644 "$SRC/LICENSES/fluentui-system-icons-MIT.txt" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-settings/fluentui-system-icons-MIT.txt"

if [ -z "$DESTDIR" ]; then
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$PREFIX/share/applications" || true
fi
echo "Fenestra Settings installed to $DESTDIR$PREFIX"

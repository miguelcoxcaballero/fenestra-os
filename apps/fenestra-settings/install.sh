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
install -m 0644 "$SRC/data/org.gnome.Settings.desktop" "$SHARE/data/org.gnome.Settings.desktop"
install -d "$SHARE/bin"
install -m 0755 "$SRC/bin/gnome-control-center" "$SHARE/bin/gnome-control-center"
install -m 0644 "$SRC"/data/icons/fluent/*.svg "$SHARE/data/icons/fluent/"

# Launcher, desktop entry, app icon, licenses
install -m 0755 "$SRC/bin/fenestra-settings" "$DESTDIR$PREFIX/bin/fenestra-settings"
install -m 0644 "$SRC/data/fenestra-settings.desktop" "$DESTDIR$PREFIX/share/applications/fenestra-settings.desktop"
ICON="$DESTDIR$PREFIX/share/icons/hicolor/scalable/apps/fenestra-settings.svg"
# Keep a user-imported icon (fenestra-import-windows-assets) instead of overwriting it.
if ! grep -q "fenestra-imported-icon" "$ICON" 2>/dev/null; then
    install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/fenestra-settings.svg" "$ICON"
fi
install -m 0644 "$SRC/LICENSES/fluentui-system-icons-MIT.txt" \
    "$DESTDIR$PREFIX/share/licenses/fenestra-settings/fluentui-system-icons-MIT.txt"

# Replace GNOME Settings entry points (set REPLACE_GNOME_SETTINGS=0 to skip).
# The real /usr/bin/gnome-control-center is never touched: the wrapper goes to a bin
# directory that comes first in PATH (/usr/local/bin for PREFIX=/usr).
if [ "${REPLACE_GNOME_SETTINGS:-1}" = "1" ]; then
    if [ "$PREFIX" = "/usr" ]; then
        WRAP_BIN="$DESTDIR/usr/local/bin"; WRAP_APPS="$DESTDIR/usr/local/share/applications"
    else
        WRAP_BIN="$DESTDIR$PREFIX/bin"; WRAP_APPS="$DESTDIR$PREFIX/share/applications"
    fi
    install -d "$WRAP_BIN" "$WRAP_APPS"
    install -m 0755 "$SRC/bin/gnome-control-center" "$WRAP_BIN/gnome-control-center"
    install -m 0644 "$SRC/data/org.gnome.Settings.desktop" "$WRAP_APPS/org.gnome.Settings.desktop"
fi

if [ -z "$DESTDIR" ]; then
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$PREFIX/share/applications" || true
fi
echo "Fenestra Settings installed to $DESTDIR$PREFIX"

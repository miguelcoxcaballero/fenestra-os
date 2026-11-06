#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Install the Fenestra xdg-desktop-portal backend (Print).
#   PREFIX  (default /usr)   installation prefix
#   DESTDIR (default empty)  staging root (build/build-overlay.sh passes the overlay root)
# Runtime dependencies: python3, python3-gobject, python3-cairo, gtk4, poppler-glib,
# xdg-desktop-portal. Printing goes through GTK's CUPS backend.
set -eu
PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"
SRC="$(cd "$(dirname "$0")" && pwd)"
SHARE="$DESTDIR$PREFIX/share/fenestra/portal"

install -d "$SHARE" "$DESTDIR$PREFIX/libexec"
rm -rf "$SHARE/fenestra_portal"
cp -r "$SRC/fenestra_portal" "$SHARE/"
find "$SHARE/fenestra_portal" -name '__pycache__' -type d -prune -exec rm -rf {} +
python3 -m compileall -q "$SHARE/fenestra_portal" >/dev/null 2>&1 || true

install -m 0755 "$SRC/xdg-desktop-portal-fenestra" "$DESTDIR$PREFIX/libexec/xdg-desktop-portal-fenestra"
install -Dm 0644 "$SRC/fenestra.portal" "$DESTDIR$PREFIX/share/xdg-desktop-portal/portals/fenestra.portal"
install -Dm 0644 "$SRC/org.freedesktop.impl.portal.desktop.fenestra.service" \
    "$DESTDIR$PREFIX/share/dbus-1/services/org.freedesktop.impl.portal.desktop.fenestra.service"
install -Dm 0644 "$SRC/xdg-desktop-portal-fenestra.service" \
    "$DESTDIR$PREFIX/lib/systemd/user/xdg-desktop-portal-fenestra.service"
echo "Fenestra portal backend installed to $DESTDIR$PREFIX"

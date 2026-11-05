#!/bin/sh
# Install Fenestra OOBE.
#
#   ./install.sh                     # into /usr (needs root)
#   DESTDIR=/tmp/root ./install.sh   # staged install for packaging
#   PREFIX=/usr/local ./install.sh
#   ./install.sh --uninstall
#
# Honors DESTDIR, PREFIX, LIBEXECDIR, DATADIR and SYSTEMDUSERDIR.
set -eu

SRC=$(cd "$(dirname "$0")" && pwd)
DESTDIR=${DESTDIR:-}
PREFIX=${PREFIX:-/usr}
LIBEXECDIR=${LIBEXECDIR:-$PREFIX/libexec}
DATADIR=${DATADIR:-$PREFIX/share}
PKGDATADIR=$DATADIR/fenestra-oobe
SYSTEMDUSERDIR=${SYSTEMDUSERDIR:-$PREFIX/lib/systemd/user}
APPSDIR=$DATADIR/applications

UNITS="gnome-initial-setup.service gnome-initial-setup-first-login.service"

if [ "${1:-}" = "--uninstall" ]; then
    rm -rf "$DESTDIR$PKGDATADIR"
    rm -f "$DESTDIR$LIBEXECDIR/fenestra-oobe" "$DESTDIR$APPSDIR/org.fenestra.Oobe.desktop"
    for unit in $UNITS; do
        rm -f "$DESTDIR$SYSTEMDUSERDIR/$unit.d/fenestra.conf"
        rmdir "$DESTDIR$SYSTEMDUSERDIR/$unit.d" 2>/dev/null || true
    done
    echo "Fenestra OOBE removed from $DESTDIR$PREFIX"
    exit 0
fi

install -d "$DESTDIR$PKGDATADIR" "$DESTDIR$LIBEXECDIR" "$DESTDIR$APPSDIR"

# Python package (no bytecode caches).
( cd "$SRC" && find fenestra_oobe -type f -name '*.py' ) | while read -r f; do
    install -D -m 0644 "$SRC/$f" "$DESTDIR$PKGDATADIR/$f"
done

# Stylesheet and illustrations.
install -m 0644 "$SRC/data/style.css" "$DESTDIR$PKGDATADIR/style.css"
install -d "$DESTDIR$PKGDATADIR/illustrations"
for svg in "$SRC"/data/illustrations/*.svg; do
    install -m 0644 "$svg" "$DESTDIR$PKGDATADIR/illustrations/"
done
# UI glyphs (back arrow, accessibility button).
install -d "$DESTDIR$PKGDATADIR/icons"
for svg in "$SRC"/data/icons/*.svg; do
    install -m 0644 "$svg" "$DESTDIR$PKGDATADIR/icons/"
done

# Launcher.
sed "s|@PKGDATADIR@|$PKGDATADIR|g" "$SRC/bin/fenestra-oobe" > "$DESTDIR$LIBEXECDIR/fenestra-oobe"
chmod 0755 "$DESTDIR$LIBEXECDIR/fenestra-oobe"

# systemd user drop-ins that replace gnome-initial-setup's ExecStart.
for unit in $UNITS; do
    install -d "$DESTDIR$SYSTEMDUSERDIR/$unit.d"
    sed "s|/usr/libexec/fenestra-oobe|$LIBEXECDIR/fenestra-oobe|g" \
        "$SRC/data/systemd/$unit.d/fenestra.conf" > "$DESTDIR$SYSTEMDUSERDIR/$unit.d/fenestra.conf"
    chmod 0644 "$DESTDIR$SYSTEMDUSERDIR/$unit.d/fenestra.conf"
done

sed "s|/usr/libexec/fenestra-oobe|$LIBEXECDIR/fenestra-oobe|g" \
    "$SRC/data/org.fenestra.Oobe.desktop" > "$DESTDIR$APPSDIR/org.fenestra.Oobe.desktop"
chmod 0644 "$DESTDIR$APPSDIR/org.fenestra.Oobe.desktop"

echo "Fenestra OOBE installed (DESTDIR=${DESTDIR:-none}, PREFIX=$PREFIX)"

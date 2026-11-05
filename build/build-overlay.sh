#!/usr/bin/env bash
# Assemble the Fenestra root-filesystem overlay: every file Fenestra adds on top
# of a Fedora Workstation install. The kickstart copies this tree into the
# installed system (see kickstart/fenestra.ks, %post --nochroot).
#
# Usage: build/build-overlay.sh [OUT_DIR]   (default: build/out/rootfs)
# Needs network for pinned third-party downloads (cached in ~/.cache/fenestra-build).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$REPO/build/out/rootfs}"
CACHE="${FENESTRA_CACHE:-$HOME/.cache/fenestra-build}"
D="$REPO/desktop"

WIN11_ICONS_COMMIT=a5b460a407da143b32f19a503d7fcebb3edf2371   # GPL-3.0, yeyushengfan258/Win11-icon-theme
BIBATA_VERSION=v2.0.7                                         # GPL-3.0, ful1e5/Bibata_Cursor
SELAWIK_VERSION=1.01                                          # OFL-1.1, microsoft/Selawik

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
rm -rf "$OUT"
mkdir -p "$OUT" "$CACHE"

log "GNOME Shell extensions"
install -d "$OUT/usr/share/gnome-shell/extensions"
cp -a "$D/extensions/." "$OUT/usr/share/gnome-shell/extensions/"
for s in "$OUT"/usr/share/gnome-shell/extensions/*/schemas; do
    [ -d "$s" ] && glib-compile-schemas "$s"
done

log "Fenestra assets, libraries and helpers"
install -d "$OUT/usr/share/fenestra/assets" "$OUT/usr/share/fenestra/lib" "$OUT/usr/libexec/fenestra"
cp -a "$REPO/assets/generated/." "$OUT/usr/share/fenestra/assets/"
cp -a "$D/lib/folder-icons/folder_icons.py" "$OUT/usr/share/fenestra/lib/"
install -m755 "$D/libexec/fenestra-patch-nautilus" "$D/libexec/fenestra-nautilus" "$OUT/usr/libexec/fenestra/"
install -Dm755 "$REPO/tools/fenestra-import-windows-assets" "$OUT/usr/bin/fenestra-import-windows-assets"
install -Dm644 "$D/systemd/fenestra-patch-nautilus.service" "$OUT/usr/lib/systemd/system/fenestra-patch-nautilus.service"

log "Files (Nautilus) Explorer layer"
install -d "$OUT/usr/share/nautilus-python/extensions" "$OUT/usr/share/fenestra/nautilus"
cp -a "$D/nautilus/python/"*.py "$OUT/usr/share/nautilus-python/extensions/"
cp -a "$D/nautilus/overlay" "$OUT/usr/share/fenestra/nautilus/overlay"
cp "$D/nautilus/VERSION" "$OUT/usr/share/fenestra/nautilus/VERSION"
install -Dm644 "$D/applications/org.gnome.Nautilus.dbus.service" "$OUT/usr/local/share/dbus-1/services/org.gnome.Nautilus.service"

log "Desktop entries, backgrounds, skeleton"
install -Dm644 "$D/applications/fenestra-search.desktop" "$OUT/usr/share/applications/fenestra-search.desktop"
install -d "$OUT/usr/share/backgrounds/fenestra"
cp "$REPO/assets/generated/wallpapers/"*.jpg "$OUT/usr/share/backgrounds/fenestra/"
install -Dm644 "$D/backgrounds/fenestra.xml" "$OUT/usr/share/gnome-background-properties/fenestra.xml"
install -d "$OUT/etc/skel"
cp -a "$D/skel/." "$OUT/etc/skel/"

install -Dm644 "$D/spotlight/current.json" "$OUT/var/lib/fenestra-spotlight/current.json"

log "dconf defaults and fontconfig"
install -d "$OUT/etc/dconf/db/local.d" "$OUT/etc/dconf/db/gdm.d"
cp "$D/dconf/local.d/"* "$OUT/etc/dconf/db/local.d/"
cp "$D/dconf/gdm.d/"* "$OUT/etc/dconf/db/gdm.d/"
install -Dm644 "$D/fontconfig/60-fenestra.conf" "$OUT/etc/fonts/conf.d/60-fenestra.conf"

log "GTK theme"
install -d "$OUT/usr/share/themes"
cp -a "$D/themes/Fenestra-Dark" "$OUT/usr/share/themes/"

log "Icon theme (Win11 by yeyushengfan258 + Fenestra aliases)"
if [ ! -d "$CACHE/Win11-icon-theme/.git" ]; then
    git clone -q https://github.com/yeyushengfan258/Win11-icon-theme.git "$CACHE/Win11-icon-theme"
fi
git -C "$CACHE/Win11-icon-theme" fetch -q --depth 1 origin "$WIN11_ICONS_COMMIT" 2>/dev/null || true
git -C "$CACHE/Win11-icon-theme" checkout -q "$WIN11_ICONS_COMMIT"
install -d "$OUT/usr/share/icons"
(cd "$CACHE/Win11-icon-theme" && ./install.sh -d "$OUT/usr/share/icons" -t default >/dev/null)
python3 "$REPO/tools/build-fenestra-icons.py" "$OUT/usr/share/icons"

log "Cursor theme (Bibata Original Classic)"
if [ ! -f "$CACHE/Bibata-Original-Classic-$BIBATA_VERSION.tar.xz" ]; then
    curl -sSL -o "$CACHE/Bibata-Original-Classic-$BIBATA_VERSION.tar.xz" \
        "https://github.com/ful1e5/Bibata_Cursor/releases/download/$BIBATA_VERSION/Bibata-Original-Classic.tar.xz"
fi
tar -xJf "$CACHE/Bibata-Original-Classic-$BIBATA_VERSION.tar.xz" -C "$OUT/usr/share/icons"

log "Fonts (Selawik, OFL)"
if [ ! -f "$CACHE/Selawik-$SELAWIK_VERSION.zip" ]; then
    curl -sSL -o "$CACHE/Selawik-$SELAWIK_VERSION.zip" \
        "https://github.com/microsoft/Selawik/releases/download/$SELAWIK_VERSION/Selawik_Release.zip"
fi
install -d "$OUT/usr/share/fonts/selawik"
python3 - "$CACHE/Selawik-$SELAWIK_VERSION.zip" "$OUT/usr/share/fonts/selawik" <<'PY'
import sys, zipfile, os
z = zipfile.ZipFile(sys.argv[1])
for n in z.namelist():
    base = os.path.basename(n)
    if base.lower().endswith('.ttf') or base.upper().startswith(('LICENSE', 'OFL')):
        open(os.path.join(sys.argv[2], base), 'wb').write(z.read(n))
PY

log "Fenestra apps"
for app in "$REPO"/apps/*/; do
    if [ -x "$app/install.sh" ]; then
        (cd "$app" && DESTDIR="$OUT" PREFIX=/usr ./install.sh >/dev/null)
        log "  installed $(basename "$app")"
    fi
done

log "Licenses"
install -d "$OUT/usr/share/licenses/fenestra"
cp -a "$REPO/LICENSE" "$REPO/THIRD-PARTY.md" "$OUT/usr/share/licenses/fenestra/" 2>/dev/null || true
cp -a "$REPO/assets/LICENSES/." "$OUT/usr/share/licenses/fenestra/" 2>/dev/null || true

du -sh "$OUT"
log "Overlay ready: $OUT"

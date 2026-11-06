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
# org.fenestra.desktop (accent colour) is read by Fenestra Settings and GTK apps too.
install -Dm644 "$D/extensions/fenestra-tray@fenestra-os.github.io/schemas/org.fenestra.desktop.gschema.xml" \
    "$OUT/usr/share/glib-2.0/schemas/org.fenestra.desktop.gschema.xml"

log "Fenestra assets, libraries and helpers"
install -d "$OUT/usr/share/fenestra/assets" "$OUT/usr/share/fenestra/lib" "$OUT/usr/libexec/fenestra"
cp -a "$REPO/assets/generated/." "$OUT/usr/share/fenestra/assets/"
cp -a "$D/lib/folder-icons/folder_icons.py" "$OUT/usr/share/fenestra/lib/"
install -m755 "$D/libexec/fenestra-patch-nautilus" "$D/libexec/fenestra-nautilus" "$D/libexec/fenestra-release-upgrade" \
    "$D/libexec/fenestra-release-upgrade-user" "$D/libexec/fenestra-plymouth-theme" "$OUT/usr/libexec/fenestra/"
# Re-run by the release upgrade after every upgrade (Python / GDM PAM paths of local services).
install -m755 "$REPO/extras/fedora-upgrade/fix-local-services.sh" "$OUT/usr/libexec/fenestra/fenestra-fix-local-services"
# Login screen safety net: compatibility matrix + greeter guard (see docs/login-safety.md).
install -m755 "$D/libexec/fenestra-login-guard" "$OUT/usr/libexec/fenestra/"
install -Dm644 "$D/systemd/fenestra-greeter-guard.service" "$OUT/usr/lib/systemd/system/fenestra-greeter-guard.service"
install -Dm644 "$REPO/extras/compat/login-extensions.json" "$OUT/usr/share/fenestra/compat/login-extensions.json"
install -Dm644 "$D/systemd/fenestra-post-upgrade.service" "$OUT/usr/lib/systemd/system/fenestra-post-upgrade.service"
install -Dm644 "$D/autostart/fenestra-release-upgrade-user.desktop" "$OUT/etc/xdg/autostart/fenestra-release-upgrade-user.desktop"
install -d "$OUT/usr/share/fenestra/upgrade"
cp "$REPO/extras/fedora-upgrade/check.sh" "$REPO/extras/fedora-upgrade/nautilus-user-refresh.sh" "$OUT/usr/share/fenestra/upgrade/"
install -Dm755 "$REPO/tools/fenestra-import-windows-assets" "$OUT/usr/bin/fenestra-import-windows-assets"
install -Dm644 "$D/systemd/fenestra-patch-nautilus.service" "$OUT/usr/lib/systemd/system/fenestra-patch-nautilus.service"
# Settings > System > Recovery > Reset this PC (runs at the next boot, before GDM).
install -m755 "$D/libexec/fenestra-reset" "$OUT/usr/libexec/fenestra/"
# Settings > Fenestra Update: newer Fenestra builds from GitHub (fenestra-update),
# and the steps every install and update ends with (fenestra-post-install).
install -m755 "$D/libexec/fenestra-update" "$D/libexec/fenestra-post-install" "$OUT/usr/libexec/fenestra/"
install -Dm644 "$D/polkit/org.fenestra.update.policy" "$OUT/usr/share/polkit-1/actions/org.fenestra.update.policy"
install -Dm644 "$D/systemd/fenestra-reset.service" "$OUT/usr/lib/systemd/system/fenestra-reset.service"
install -Dm644 "$D/polkit/org.fenestra.reset.policy" "$OUT/usr/share/polkit-1/actions/org.fenestra.reset.policy"
install -d "$OUT/usr/lib/systemd/user"
cp -a "$D/systemd/user/." "$OUT/usr/lib/systemd/user/"   # e.g. gnome-shell CPU/IO priority drop-in

log "Files (Nautilus) Explorer layer"
install -d "$OUT/usr/share/nautilus-python/extensions" "$OUT/usr/share/fenestra/nautilus"
cp -a "$D/nautilus/python/"*.py "$OUT/usr/share/nautilus-python/extensions/"
# One UI overlay per supported Nautilus major version (overlay/<major>/{ui,menu}/);
# fenestra-nautilus picks the one matching the installed Nautilus, else runs it stock.
cp -a "$D/nautilus/overlay" "$OUT/usr/share/fenestra/nautilus/overlay"
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
# Windows 11 caption buttons for every GTK 3/4 window (imported by the user CSS).
install -Dm644 "$D/gtk/caption-buttons-gtk4.css" "$OUT/usr/share/fenestra/gtk-4.0/caption-buttons.css"
install -Dm644 "$D/gtk/caption-buttons-gtk3.css" "$OUT/usr/share/fenestra/gtk-3.0/caption-buttons.css"
for v in 3 4; do
    # Per-user copy (Flatpak apps cannot read /usr/share/fenestra); fenestra-tray refreshes it at login.
    install -Dm644 "$D/gtk/caption-buttons-gtk$v.css" "$OUT/etc/skel/.config/gtk-$v.0/fenestra-caption-buttons.css"
    # Fallback for every account and session: three caption buttons on the right.
    install -Dm644 "$D/gtk/settings-gtk$v.ini" "$OUT/etc/gtk-$v.0/settings.ini"
done
# Qt apps: XWayland first, so mutter draws Windows 11 caption buttons for them
# (Qt's own Wayland decorations cannot be themed). Wayland stays as fallback.
install -Dm644 "$D/gtk/60-fenestra-qt.conf" "$OUT/usr/lib/environment.d/60-fenestra-qt.conf"
install -d "$OUT/usr/share/themes"
cp -a "$D/themes/Fenestra-Dark" "$D/themes/Fenestra-Light" "$OUT/usr/share/themes/"

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

install -Dm755 "$D/bin/gnome-system-monitor" "$OUT/usr/local/bin/gnome-system-monitor"

log "Fenestra apps"
for app in "$REPO"/apps/*/; do
    if [ -x "$app/install.sh" ]; then
        (cd "$app" && DESTDIR="$OUT" PREFIX=/usr ./install.sh >/dev/null)
        log "  installed $(basename "$app")"
    fi
done

log "Release stamp"
# Which Fenestra build this is; Settings > Fenestra Update compares it with GitHub.
COMMIT="${FENESTRA_COMMIT:-$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)}"
COMMIT_DATE="${FENESTRA_COMMIT_DATE:-$(git -C "$REPO" log -1 --format=%cI 2>/dev/null || date -u +%FT%TZ)}"
python3 - "$OUT/usr/share/fenestra/release.json" "$COMMIT" "$COMMIT_DATE" <<'PY'
import json, sys
json.dump({"repo": "miguelcoxcaballero/fenestra-os", "branch": "main",
           "commit": sys.argv[2], "date": sys.argv[3]}, open(sys.argv[1], "w"), indent=1)
PY

log "Licenses"
install -d "$OUT/usr/share/licenses/fenestra"
cp -a "$REPO/LICENSE" "$REPO/THIRD-PARTY.md" "$OUT/usr/share/licenses/fenestra/" 2>/dev/null || true
cp -a "$REPO/assets/LICENSES/." "$OUT/usr/share/licenses/fenestra/" 2>/dev/null || true

# cp -a keeps the working tree's modes; some vendored files (e.g. third-party
# extensions' metadata.json) are 0600 there, which would make them unreadable for
# every user on the installed system. Everything in the overlay is world-readable.
chmod -R u+rwX,go+rX,go-w "$OUT"

du -sh "$OUT"
log "Overlay ready: $OUT"

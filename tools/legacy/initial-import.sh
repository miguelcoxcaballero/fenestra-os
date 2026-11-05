#!/usr/bin/env bash
# HISTORICAL: one-time import used to bootstrap this repository from the
# development laptop. The repository is now the source of truth; running this
# again would overwrite later changes (renames, i18n, asset lookups).
# Maintainer helper: copy the Fenestra desktop pieces from the reference
# machine (where they were developed) into the repository tree.
#
# It renames the machine-local "windows-*@local" components to "fenestra-*",
# drops caches and NEVER copies Microsoft-proprietary assets (fonts, glyph
# derived icons, images extracted from Windows). Those are regenerated as
# open replacements by tools/generate-assets.py, or imported on the end user's
# machine by fenestra-import-windows-assets.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
EXT_USER="${EXT_USER:-$HOME/.local/share/gnome-shell/extensions}"
EXT_SYS="${EXT_SYS:-/usr/share/gnome-shell/extensions}"
DEST="$REPO/desktop/extensions"

copy_ext() { # src uuid newuuid
    local src="$1" new="$2"
    rm -rf "$DEST/$new"
    rsync -a --exclude '__pycache__' --exclude '*.bak' --exclude '*.orig' --exclude '*.before*' \
        --exclude 'hello-assets/' --exclude 'status-assets/' --exclude 'battery/' \
        --exclude 'power-icons/' --exclude 'ChromeClose.svg' --exclude 'Shield.svg' \
        "$src/" "$DEST/$new/"
}

mkdir -p "$DEST"
# Upstream extensions shipped with Fenestra modifications (GPL, keep UUIDs).
for uuid in arcmenu@arcmenu.com dash-to-panel@jderose9.github.com ding@rastersoft.com \
            blur-my-shell@aunetx rounded-window-corners@fxgn tiling-assistant@leleat-on-github \
            notification-banner@VitalyOstanin no-screenshot-box@screenshot; do
    copy_ext "$EXT_USER/$uuid" "$uuid"
done
# Fenestra's own extensions (renamed from the development names).
declare -A OWN=(
    [windows-tray@local]=fenestra-tray@fenestra-os.github.io
    [windows-consent@local]=fenestra-consent@fenestra-os.github.io
    [windows-lock-clock@local]=fenestra-lock-clock@fenestra-os.github.io
    [direct-unlock@local]=fenestra-direct-unlock@fenestra-os.github.io
    [user-lock-prompt@local]=fenestra-user-lock-prompt@fenestra-os.github.io
)
for old in "${!OWN[@]}"; do copy_ext "$EXT_USER/$old" "${OWN[$old]}"; done
declare -A OWN_SYS=(
    [windows-spotlight@local]=fenestra-spotlight@fenestra-os.github.io
    [single-user-gdm@local]=fenestra-login@fenestra-os.github.io
)
for old in "${!OWN_SYS[@]}"; do copy_ext "$EXT_SYS/$old" "${OWN_SYS[$old]}"; done

# Rewrite UUIDs inside metadata.
for old in "${!OWN[@]}" "${!OWN_SYS[@]}"; do
    new="${OWN[$old]:-${OWN_SYS[$old]}}"
    sed -i "s/\"$old\"/\"$new\"/" "$DEST/$new/metadata.json"
done

# Nautilus (Files) Windows-Explorer layer.
mkdir -p "$REPO/desktop/nautilus/python" "$REPO/desktop/nautilus/overlay"
rsync -a --exclude '__pycache__' "$HOME/.local/share/nautilus-python/extensions/" "$REPO/desktop/nautilus/python/"
rsync -a "$HOME/.local/share/nautilus-sidebar-win11/overlay/" "$REPO/desktop/nautilus/overlay/"
mkdir -p "$REPO/desktop/lib/folder-icons"
cp "$HOME/.local/lib/windows-folder-icons/folder_icons.py" "$REPO/desktop/lib/folder-icons/"

# GTK theme (Fluent based, GPL-3 — COPYING kept).
mkdir -p "$REPO/desktop/themes"
rsync -a "$HOME/.local/share/themes/Windows11-Miguel-Dark/" "$REPO/desktop/themes/Fenestra-Dark/"
sed -i 's/Windows11-Miguel-Dark/Fenestra-Dark/g' "$REPO/desktop/themes/Fenestra-Dark/index.theme"

# User GTK overrides (window decorations etc.) -> /etc/skel.
mkdir -p "$REPO/desktop/skel/.config"
for d in gtk-3.0 gtk-4.0; do
    mkdir -p "$REPO/desktop/skel/.config/$d"
    for f in gtk.css colors.css window_decorations.css settings.ini; do
        [ -f "$HOME/.config/$d/$f" ] && cp "$HOME/.config/$d/$f" "$REPO/desktop/skel/.config/$d/"
    done
    [ -d "$HOME/.config/$d/assets" ] && rsync -a "$HOME/.config/$d/assets/" "$REPO/desktop/skel/.config/$d/assets/"
done
# "New" context-menu templates (empty documents, Windows names).
mkdir -p "$REPO/desktop/skel/Templates"
rsync -a "$HOME/Templates/" "$REPO/desktop/skel/Templates/"

echo "Synced into $REPO/desktop"

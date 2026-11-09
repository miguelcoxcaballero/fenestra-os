#!/bin/bash
# Builds Fenestra Shell from this checkout in the KWin lab image (same Fedora as the PC) and
# installs it for the current user only, without root:
#   ~/.local/opt/fenestra-shell/{bin,share}   + a systemd user drop-in that runs it.
# Assets: the shell asks for /usr/share/fenestra/assets/X; this build also looks in
#   ~/.local/share/fenestra/shell-assets/X first, which this script fills from assets/generated.
# Undo: tools/install-shell-user.sh --remove   (back to /usr/bin/fenestra-shell from the RPM)
#   env: IMAGE (default fenestra-kwinlab), ENGINE (default podman), JOBS (default 2)
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
PREFIX=$HOME/.local/opt/fenestra-shell
DROPIN=$HOME/.config/systemd/user/fenestra-shell.service.d/50-user-build.conf
ENGINE=${ENGINE:-podman}
IMAGE=${IMAGE:-fenestra-kwinlab}

if [ "${1:-}" = --remove ]; then
    rm -f "$DROPIN" "$HOME/.local/share/applications/org.fenestra.Shell-user.desktop"; systemctl --user daemon-reload
    echo "removed; restart the shell: systemctl --user restart fenestra-shell"
    exit 0
fi

BUILD=$HOME/.cache/fenestra-shell-user-build
STAGE=$(mktemp -d)
mkdir -p "$BUILD"
$ENGINE run --rm --security-opt label=disable -e JOBS="${JOBS:-2}" -v "$REPO:/src:ro" -v "$BUILD:/build" -v "$STAGE:/stage" "$IMAGE" bash -c '
    set -e
    cmake -S /src/shell -B /build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr >/dev/null
    ninja -j${JOBS} -C /build >/dev/null
    DESTDIR=/stage cmake --install /build >/dev/null'
rm -rf "$PREFIX.new"; mkdir -p "$PREFIX.new"
cp -a "$STAGE/usr/." "$PREFIX.new/"
rm -rf "$STAGE"
rm -rf "$PREFIX.old"; [ -d "$PREFIX" ] && mv "$PREFIX" "$PREFIX.old"; mv "$PREFIX.new" "$PREFIX"

SA=$HOME/.local/share/fenestra/shell-assets
rm -rf "$SA.new"; mkdir -p "$SA.new"
for d in "$REPO"/assets/generated/*/; do
    n=$(basename "$d"); [ "$n" = wallpapers ] && continue
    mkdir -p "$SA.new/$n"; cp -a "$d". "$SA.new/$n/"
done
rm -rf "$SA"; mv "$SA.new" "$SA"

# KWin grants window management / screenshots only to the executable named in a .desktop
# file's Exec (X-KDE-Wayland-Interfaces): give this build its own entry.
APPS=$HOME/.local/share/applications
mkdir -p "$APPS"
sed "s|^Exec=.*|Exec=$PREFIX/bin/fenestra-shell|" "$REPO/shell/data/org.fenestra.Shell.desktop" > "$APPS/org.fenestra.Shell-user.desktop"

# KWin looks the entry up in the KService cache: refresh it (a running KWin picks it up).
kbuildsycoca6 >/dev/null 2>&1 || true

# Fenestra's scripted KWin effects (the unlock fade, window motion): KWin reads per-user ones from
# ~/.local/share/kwin/effects. The unlock fade is on by default; load it in the running KWin.
KFX=$HOME/.local/share/kwin/effects
mkdir -p "$KFX"
for d in "$REPO"/kwin/effects/*/; do
    n=$(basename "$d"); rm -rf "$KFX/$n.new"; cp -a "$d" "$KFX/$n.new"; rm -rf "${KFX:?}/$n"; mv "$KFX/$n.new" "$KFX/$n"
done
# The preview shown while a window is dragged to a screen edge: found here by kwinintegration.cpp.
mkdir -p "$HOME/.local/share/kwin/outline"; rm -rf "$HOME/.local/share/kwin/outline/fenestra"; cp -a "$REPO/kwin/outline/fenestra" "$HOME/.local/share/kwin/outline/"
kwriteconfig6 --file kwinrc --group Plugins --key fenestra-unlockEnabled true
busctl --user call org.kde.KWin /Effects org.kde.kwin.Effects loadEffect s fenestra-unlock >/dev/null 2>&1 || true

mkdir -p "$(dirname "$DROPIN")"
cat > "$DROPIN" <<EOF
# Written by tools/install-shell-user.sh ($(git -C "$REPO" rev-parse --short HEAD)); remove with --remove
[Service]
ExecStart=
ExecStart=$PREFIX/bin/fenestra-shell
EOF
systemctl --user daemon-reload
echo "installed $(git -C "$REPO" rev-parse --short HEAD) in $PREFIX; restart: systemctl --user restart fenestra-shell"

#!/bin/bash
# Builds Fenestra Shell from this checkout in the KWin lab image (same Fedora as the PC) and
# installs it for the current user only, without root:
#   ~/.local/opt/fenestra-shell/{bin,share}   + a systemd user drop-in that runs it.
# Assets stay those of the RPM in /usr/share/fenestra/assets (the shell reads that path).
# Undo: tools/install-shell-user.sh --remove   (back to /usr/bin/fenestra-shell from the RPM)
#   env: IMAGE (default fenestra-kwinlab), ENGINE (default podman), JOBS (default 2)
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
PREFIX=$HOME/.local/opt/fenestra-shell
DROPIN=$HOME/.config/systemd/user/fenestra-shell.service.d/50-user-build.conf
ENGINE=${ENGINE:-podman}
IMAGE=${IMAGE:-fenestra-kwinlab}

if [ "${1:-}" = --remove ]; then
    rm -f "$DROPIN"; systemctl --user daemon-reload
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

mkdir -p "$(dirname "$DROPIN")"
cat > "$DROPIN" <<EOF
# Written by tools/install-shell-user.sh ($(git -C "$REPO" rev-parse --short HEAD)); remove with --remove
[Service]
ExecStart=
ExecStart=$PREFIX/bin/fenestra-shell
EOF
systemctl --user daemon-reload
echo "installed $(git -C "$REPO" rev-parse --short HEAD) in $PREFIX; restart: systemctl --user restart fenestra-shell"

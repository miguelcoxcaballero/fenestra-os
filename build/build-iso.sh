#!/usr/bin/env bash
# Build a Fenestra installer ISO from the official Fedora Everything netinstall ISO.
#
#   build/build-iso.sh [--test] [FEDORA_NETINST_ISO] [OUTPUT_ISO]
#
# --test builds the unattended variant used by tests/vm (WIPES the target disk).
# Runs mkksiso (lorax) inside a rootless Podman Fedora container (or directly
# with FENESTRA_NO_CONTAINER=1, e.g. in CI which already runs in Fedora as root).
# The ISO keeps Fedora's signed boot chain; it only adds the kickstart and the
# Fenestra overlay tarball.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TEST=0
if [ "${1:-}" = "--test" ]; then TEST=1; shift; fi
FEDORA_ISO="${1:-$HOME/.local/share/fenestra-vm/Fedora-Everything-netinst-x86_64-43-1.6.iso}"
OUT_ISO="${2:-$REPO/build/out/Fenestra-43-$( [ $TEST = 1 ] && echo test || echo netinst )-x86_64.iso}"
WORK="$REPO/build/out/iso-work"

[ -f "$FEDORA_ISO" ] || { echo "Fedora netinstall ISO not found: $FEDORA_ISO" >&2; exit 1; }
rm -f "$OUT_ISO"

bash "$REPO/build/build-overlay.sh" "$REPO/build/out/rootfs"

rm -rf "$WORK"
mkdir -p "$WORK/add/fenestra"
tar -C "$REPO/build/out/rootfs" --owner=0 --group=0 -czf "$WORK/add/fenestra/rootfs.tar.gz" .
cp "$REPO/kickstart/fenestra-base.ks" "$WORK/add/fenestra/"
if [ $TEST = 1 ]; then
    cat "$REPO/kickstart/fenestra-test.ks" "$REPO/kickstart/fenestra-base.ks" > "$WORK/ks.cfg"
    # Test builds only: root SSH with a local key so tests/vm can collect logs.
    KEY="${FENESTRA_TEST_SSHKEY:-$HOME/.local/share/fenestra-vm/test_key.pub}"
    if [ -f "$KEY" ]; then
        printf 'sshkey --username=root "%s"\nservices --enabled=sshd\n' "$(cat "$KEY")" >> "$WORK/ks.cfg"
    fi
    EXTRA_ARGS="inst.text console=tty0 console=ttyS0,115200"
else
    cp "$REPO/kickstart/fenestra-base.ks" "$WORK/ks.cfg"
    EXTRA_ARGS=""
fi

MKKSISO_ARGS=(--ks "$WORK/ks.cfg" --add "$WORK/add/fenestra" --rm rd.live.check
    -R 'Install Fedora 43' 'Install Fenestra 43'
    -R 'Test this media & install Fedora 43' 'Test this media & install Fenestra 43'
    -R 'set default="1"' 'set default="0"' -R 'set timeout=60' 'set timeout=5')
[ -n "$EXTRA_ARGS" ] && MKKSISO_ARGS+=(-c "$EXTRA_ARGS")
# Rebuilding the EFI boot image needs loop devices (root). Rootless local builds
# skip it: the kickstart then boots via BIOS only (fine for tests/vm).
# FENESTRA_SKIP_MKEFIBOOT=1 forces this (containers where loop mounts fail).
if [ "${FENESTRA_SKIP_MKEFIBOOT:-}" = 1 ] || [ "$(id -u)" != 0 ] || ! losetup -f >/dev/null 2>&1; then MKKSISO_ARGS+=(--skip-mkefiboot); fi

if [ "${FENESTRA_NO_CONTAINER:-}" = 1 ]; then
    mkksiso "${MKKSISO_ARGS[@]}" "$FEDORA_ISO" "$OUT_ISO"
else
    # Same paths inside the container, so the argument list can be reused as is.
    podman run --rm --security-opt label=disable \
        -v "$WORK:$WORK" -v "$(dirname "$FEDORA_ISO"):$(dirname "$FEDORA_ISO"):ro" -v "$(dirname "$OUT_ISO"):$(dirname "$OUT_ISO")" \
        registry.fedoraproject.org/fedora:43 bash -c 'dnf -y -q install lorax xorriso isomd5sum >/dev/null && mkksiso "$@"' _ \
        "${MKKSISO_ARGS[@]}" "$FEDORA_ISO" "$OUT_ISO"
fi
ls -lh "$OUT_ISO"

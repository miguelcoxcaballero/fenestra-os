#!/usr/bin/env bash
# Fenestra VM test harness (rootless QEMU/KVM).
#   tests/vm/vm.sh install ISO   - fresh disk, unattended install (powers off when done)
#   tests/vm/vm.sh boot          - boot the installed disk (first boot -> OOBE)
#   tests/vm/vm.sh shot NAME     - screenshot via QMP into tests/vm/shots/NAME.png
#   tests/vm/vm.sh key KEYS...   - send keys (QMP send-key names, e.g. ret, tab, shift-tab, a)
#   tests/vm/vm.sh type TEXT     - type text
#   tests/vm/vm.sh click X Y     - absolute click (screen pixels)
#   tests/vm/vm.sh ssh CMD...    - run a command as root (test ISOs only)
#   tests/vm/vm.sh stop          - power off
set -euo pipefail
# Laptop has 16 GB: allow only one VM at a time and keep it inside fenestra-tests.slice.
if [ "${1:-}" = install ] || [ "${1:-}" = boot ]; then
    if pgrep -f qemu-system-x86_64 >/dev/null; then echo "only one VM at a time: stop the running one first" >&2; exit 1; fi
    if [ -z "${FENESTRA_IN_SLICE:-}" ] && command -v systemd-run >/dev/null; then
        exec systemd-run --user --scope --quiet --slice=fenestra-tests.slice -E FENESTRA_IN_SLICE=1 "$0" "$@"
    fi
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
VM="${FENESTRA_VM_DIR:-$HOME/.local/share/fenestra-vm}"
DISK="$VM/fenestra.qcow2"
QMP="$VM/qmp.sock"
SHOTS="$HERE/shots"
W=1920; H=1080
mkdir -p "$VM" "$SHOTS"

qmp() { python3 "$HERE/qmp.py" "$QMP" "$@"; }

# KVM when available; otherwise multi-threaded TCG (slow, but works in CI/containers).
if [ -w /dev/kvm ]; then accel=(-enable-kvm -cpu host -smp "${FENESTRA_VM_CPUS:-6}")
else accel=(-accel tcg,thread=multi,tb-size=1024 -cpu max -smp "${FENESTRA_VM_CPUS:-$(nproc)}"); fi
common=("${accel[@]}" -m "${FENESTRA_VM_MEM:-3584}" -machine q35
        -drive "file=$DISK,if=virtio,format=qcow2"
        -device virtio-vga,xres=$W,yres=$H -display none
        -device qemu-xhci -device usb-tablet -device usb-kbd
        -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=n0
        -audiodev none,id=snd0 -device ich9-intel-hda -device hda-output,audiodev=snd0
        -qmp "unix:$QMP,server,nowait" -serial "file:$VM/serial.log")

case "${1:-}" in
  install)
    ISO="$2"; rm -f "$DISK"; qemu-img create -q -f qcow2 "$DISK" 48G
    exec qemu-system-x86_64 "${common[@]}" -cdrom "$ISO" -boot d -no-reboot ;;
  boot)
    exec qemu-system-x86_64 "${common[@]}" -boot c ;;
  shot) qmp shot "$SHOTS/$2.png" ;;
  key) shift; qmp key "$@" ;;
  type) shift; qmp type "$*" ;;
  click) qmp click "$2" "$3" $W $H ;;
  rclick) qmp rclick "$2" "$3" $W $H ;;
  move) qmp move "$2" "$3" $W $H ;;
  ssh) shift; exec ssh -q -i "$VM/test_key" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 2222 root@127.0.0.1 "$@" ;;
  stop) qmp quit ;;
  *) sed -n 2,10p "$0"; exit 1 ;;
esac

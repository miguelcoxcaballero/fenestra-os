#!/usr/bin/env bash
# Windows 11 (Enterprise Evaluation) reference VM for side-by-side comparison.
#   tests/vm/win11.sh install ISO | boot | shot NAME | key ... | type TEXT | click X Y | stop
set -euo pipefail
# Laptop has 16 GB: allow only one VM at a time and keep it inside fenestra-tests.slice.
if [ "${1:-}" = install ] || [ "${1:-}" = boot ]; then
    if [ -z "${FENESTRA_ALLOW_SECOND_VM:-}" ] && pgrep -f qemu-system-x86_64 >/dev/null; then echo "only one VM at a time: stop the running one first" >&2; exit 1; fi
    if [ -z "${FENESTRA_IN_SLICE:-}" ] && command -v systemd-run >/dev/null; then
        exec systemd-run --user --scope --quiet --slice=fenestra-tests.slice -E FENESTRA_IN_SLICE=1 "$0" "$@"
    fi
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
VM="${FENESTRA_VM_DIR:-$HOME/.local/share/fenestra-vm}/win11"
QMP="$VM/qmp.sock"; W=1920; H=1080
mkdir -p "$VM" "$HERE/shots/win11"
qmp() { python3 "$HERE/qmp.py" "$QMP" "$@"; }
start_tpm() {
    mkdir -p "$VM/tpm"
    [ -f "$VM/tpm/pid" ] && kill "$(cat "$VM/tpm/pid")" 2>/dev/null || true
    swtpm socket --tpm2 --tpmstate dir="$VM/tpm" --ctrl type=unixio,path="$VM/tpm/sock" --pid file="$VM/tpm/pid" --daemon
}
run() {
    start_tpm
    exec qemu-system-x86_64 -enable-kvm -cpu host -smp 4 -m ${FENESTRA_WIN_MEM:-4096} -machine q35,smm=on \
        -global driver=cfi.pflash01,property=secure,value=on \
        -drive if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/edk2/ovmf/OVMF_CODE.secboot.fd \
        -drive if=pflash,format=raw,unit=1,file="$VM/OVMF_VARS.fd" \
        -chardev socket,id=chrtpm,path="$VM/tpm/sock" -tpmdev emulator,id=tpm0,chardev=chrtpm -device tpm-tis,tpmdev=tpm0 \
        -drive file="$VM/win11.qcow2",if=none,id=d0,format=qcow2 -device ahci,id=ahci -device ide-hd,drive=d0,bus=ahci.0 \
        -device VGA,xres=$W,yres=$H,vgamem_mb=64 -display none \
        -device qemu-xhci -device usb-tablet -device usb-kbd \
        -netdev user,id=n0 -device e1000e,netdev=n0 \
        -audiodev none,id=snd0 -device ich9-intel-hda -device hda-output,audiodev=snd0 \
        -qmp "unix:$QMP,server,nowait" "$@"
}
case "${1:-}" in
  install)
    rm -f "$VM/win11.qcow2"; qemu-img create -q -f qcow2 "$VM/win11.qcow2" 64G
    cp /usr/share/edk2/ovmf/OVMF_VARS.secboot.fd "$VM/OVMF_VARS.fd"; rm -rf "$VM/tpm"
    genisoimage -quiet -J -r -V UNATTEND -o "$VM/unattend.iso" "$HERE/win11/autounattend.xml"
    run -drive file="$2",media=cdrom,if=none,id=cd0 -device ide-cd,drive=cd0,bus=ahci.1,bootindex=0 \
        -drive file="$VM/unattend.iso",media=cdrom,if=none,id=cd1 -device ide-cd,drive=cd1,bus=ahci.2 ;;
  boot) run ;;
  shot) qmp shot "$HERE/shots/win11/$2.png" ;;
  key) shift; qmp key "$@" ;;
  type) shift; qmp type "$*" ;;
  click) qmp click "$2" "$3" $W $H ;;
  rclick) qmp rclick "$2" "$3" $W $H ;;
  link) qmp link "$2" ;;
  stop) qmp quit ;;
  *) sed -n 2,3p "$0"; exit 1 ;;
esac

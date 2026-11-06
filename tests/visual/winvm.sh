#!/usr/bin/env bash
# Windows 11 reference VM for the visual measurements (a copy of tests/vm/win11.sh's VM in ~/VMs).
#   tests/visual/winvm.sh boot | stop | shot FILE | key K... | type TEXT | move X Y | click X Y | rclick X Y
#                        serve        (http://10.0.2.2:8765 for the guest = ~/fenestra-ref/guest, PUT saves there)
# Screenshots go wherever FILE says; keep them in ~/fenestra-ref, never in the repo.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VM="${FENESTRA_REF_VM:-$HOME/VMs/win11-ref}"
QMP="$VM/qmp.sock"; W=1920; H=1080
qmp() { python3 "$HERE/../vm/qmp.py" "$QMP" "$@"; }
case "${1:-}" in
  boot)
    if pgrep -f qemu-system-x86_64 >/dev/null; then echo "another VM is running (16 GB laptop: one at a time)" >&2; exit 1; fi
    if [ -z "${FENESTRA_IN_SLICE:-}" ] && command -v systemd-run >/dev/null; then
        exec systemd-run --user --scope --quiet --slice=fenestra-tests.slice -E FENESTRA_IN_SLICE=1 "$0" "$@"
    fi
    [ -f "$VM/tpm/pid" ] && kill "$(cat "$VM/tpm/pid")" 2>/dev/null || true
    swtpm socket --tpm2 --tpmstate dir="$VM/tpm" --ctrl type=unixio,path="$VM/tpm/sock" --pid file="$VM/tpm/pid" --daemon
    exec qemu-system-x86_64 -enable-kvm -cpu host -smp 4 -m "${FENESTRA_WIN_MEM:-4096}" -machine q35,smm=on \
        -global driver=cfi.pflash01,property=secure,value=on \
        -drive if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/edk2/ovmf/OVMF_CODE.secboot.fd \
        -drive if=pflash,format=raw,unit=1,file="$VM/OVMF_VARS.fd" \
        -chardev socket,id=chrtpm,path="$VM/tpm/sock" -tpmdev emulator,id=tpm0,chardev=chrtpm -device tpm-tis,tpmdev=tpm0 \
        -drive file="$VM/win11-ref.qcow2",if=none,id=d0,format=qcow2 -device ahci,id=ahci -device ide-hd,drive=d0,bus=ahci.0 \
        -device VGA,xres=$W,yres=$H,vgamem_mb=64 -display none \
        -device qemu-xhci -device usb-tablet -device usb-kbd \
        -netdev user,id=n0 -device e1000e,netdev=n0 \
        -audiodev none,id=snd0 -device ich9-intel-hda -device hda-output,audiodev=snd0 \
        -qmp "unix:$QMP,server,nowait" -qmp "unix:$VM/qmp2.sock,server,nowait" ;;
  stop) python3 -c "import sys;sys.path.insert(0,'$HERE/../vm');import qmp;s,f=qmp.connect('$QMP');qmp.cmd(f,'system_powerdown')" ;;
  shot) qmp shot "$2" ;;
  key) shift; qmp key "$@" ;;
  type) shift; qmp type "$*" ;;
  move) qmp move "$2" "$3" $W $H ;;
  click) qmp click "$2" "$3" $W $H ;;
  rclick) qmp rclick "$2" "$3" $W $H ;;
  serve) exec python3 "$HERE/guestserve.py" "$HOME/fenestra-ref/guest" 8765 ;;
  *) sed -n 2,4p "$0"; exit 1 ;;
esac

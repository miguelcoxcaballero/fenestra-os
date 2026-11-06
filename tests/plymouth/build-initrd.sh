#!/usr/bin/env bash
# Test initramfs for the Fenestra Plymouth theme. Run as root inside a Fedora container
# (any release) with kernel-core, dracut, plymouth, plymouth-scripts, plymouth-plugin-script
# and the Fenestra overlay (Selawik font) installed; the repo mounted at /src.
#   LANGX=es tests/plymouth/build-initrd.sh OUT_DIR
# OUT_DIR gets vmlinuz + initrd.img; boot them with tests/plymouth/run.py.
set -euo pipefail
OUT=${1:?OUT_DIR}; mkdir -p "$OUT"
HERE=$(cd "$(dirname "$0")" && pwd)
K=$(ls /lib/modules | sort -V | tail -1)
rm -rf /usr/share/plymouth/themes/fenestra
python3 "$HERE/../../desktop/libexec/fenestra-plymouth-theme" /usr/share/plymouth/themes/fenestra \
    --lang "${LANGX:-en}" --dracut >/dev/null
# Stand-in for the firmware (BGRT) logo: Fenestra's own logo.
python3 -c "from PIL import Image; Image.open('$HERE/../../assets/generated/branding/fenestra-logo-256.png').convert('RGBA').save('/usr/share/plymouth/themes/fenestra/oem.png')"
plymouth-set-default-theme fenestra
rm -rf /usr/lib/dracut/modules.d/99fentest; cp -r "$HERE/99fentest" /usr/lib/dracut/modules.d/
dracut -q -f --no-hostonly --add "plymouth fenestra-plymouth fentest" \
    --add-drivers "bochs drm_kms_helper virtio_gpu" "$OUT/initrd.img" "$K"
cp "/lib/modules/$K/vmlinuz" "$OUT/vmlinuz"

#!/usr/bin/env bash
# Step 3: first login on Fedora 45. Run as root:
#   sudo bash extras/fedora-upgrade/post-upgrade-f45.sh
# Makes sure the drivers, Hello and the Fenestra desktop are in place for the new
# release, then runs the user-level refresh and check.sh.
set -uo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
U=${SUDO_USER:-miguelcoxcaballero}
H=$(getent passwd "$U" | cut -d: -f6)
HERE=$(cd "$(dirname "$0")" && pwd)
K=$(uname -r)
log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
asuser() { runuser -u "$U" -- env HOME="$H" XDG_RUNTIME_DIR=/run/user/$(id -u "$U") DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u "$U")/bus "$@"; }

log "Fedora $(rpm -E %fedora), kernel $K"
log "Drivers for $K"
rpm -q "kernel-devel-$K" >/dev/null 2>&1 || dnf -y install "kernel-devel-$K"
dkms autoinstall -k "$K"
akmods --force --kernels "$K" || true
depmod -a "$K"
for m in ov02c10 ipu_bridge snd_hda_scodec_max98390 snd_hda_scodec_max98390_i2c v4l2loopback; do modprobe "$m" 2>/dev/null || true; done
systemctl restart camera-relay-login.service camera-relay-watchdog.service 2>/dev/null || true

log "Face sign-in (howdy + dlib for this Python)"
py=$(python3 -c 'import sys;print(f"python{sys.version_info[0]}.{sys.version_info[1]}")')
if ! rpm -ql howdy 2>/dev/null | grep -q "$py"; then
    dnf -y --repo=fenestra-local install howdy howdy-data python3-dlib || dnf -y install /var/local/fenestra-repo/45/*.rpm
fi
python3 -c 'import dlib, cv2; print("  dlib + OpenCV OK")' || echo "  dlib/OpenCV FAILED"
systemctl restart howdy-preload.service 2>/dev/null || true

log "GNOME extensions"
asuser gsettings set org.gnome.shell disable-user-extensions false
rm -f "/run/user/$(id -u "$U")/gnome-shell-disable-extensions"

log "Explorer layer for the new Nautilus"
if [ -f "$HERE/nautilus-user-refresh.sh" ]; then asuser bash "$HERE/nautilus-user-refresh.sh"; fi

log "Check"
asuser bash "$HERE/check.sh"
echo
echo "If the desktop looked like stock GNOME after logging in: log out and back in once."

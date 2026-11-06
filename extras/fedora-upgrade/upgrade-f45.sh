#!/usr/bin/env bash
# Step 2: upgrade Fedora 43 -> 45. Run as root only after prepare-f45.sh, a reboot into
# kernel 7.2.x, and a clean check.sh:
#   sudo bash extras/fedora-upgrade/upgrade-f45.sh
# Downloads everything first (the system keeps working), then reboots into the offline
# upgrade. The previous Fedora 43 kernels stay installed and selectable in GRUB.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
case "$(uname -r)" in 7.*) ;; *) echo "Boot the 7.2 kernel installed by prepare-f45.sh first and run check.sh." >&2; exit 1 ;; esac
[ -f /etc/yum.repos.d/fenestra-local.repo ] || { echo "Run prepare-f45.sh first." >&2; exit 1; }
U=${SUDO_USER:-miguelcoxcaballero}
if ! runuser -u "$U" -- env XDG_RUNTIME_DIR=/run/user/$(id -u "$U") DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u "$U")/bus \
        bash "$(dirname "$0")/check.sh" >/tmp/fenestra-precheck.txt 2>&1; then
    grep -E "FAIL" /tmp/fenestra-precheck.txt || true
    read -r -p "check.sh reported failures (above). Continue anyway? [y/N] " a
    [ "${a,,}" = y ] || exit 1
fi
dnf -y upgrade --refresh
dnf -y system-upgrade download --releasever=45
echo
echo "Download complete. Rebooting into the offline upgrade (20-40 minutes, do not power off)."
echo "After it finishes and you log in, run:"
echo "  sudo bash $(cd "$(dirname "$0")" && pwd)/post-upgrade-f45.sh"
read -r -p "Reboot now? [Y/n] " a
[ "${a,,}" = n ] || dnf offline reboot -y

#!/bin/bash
# Fenestra OS - system-level performance and battery tuning
# (Samsung Galaxy Book4 Pro / Meteor Lake, Fedora 43, GNOME 49).
#
# Run once as root from the repository:
#     sudo bash extras/performance/apply-system-tuning.sh
# Undo:
#     sudo bash extras/performance/apply-system-tuning.sh --revert
#
# Everything here is idempotent, backs up what it changes (*.fenestra-bak) and
# only touches settings that were measured as worth it on this machine.
# Already optimal on the stock install, therefore NOT changed here:
#   - NVMe APST (nvme_core.default_ps_max_latency_us=100000, on)
#   - Wi-Fi power save (iwlwifi: on), USB autosuspend (auto on every device)
#   - HDA audio power_save (tuned sets 10 s), PSR (i915 default, enabled)
#   - PAM: gdm-password runs Howdy then password; gdm-fingerprint is a separate
#     conversation, so face and fingerprint already run in parallel.
#   - tuned-ppd already maps "balanced" to balanced-battery on battery
#     (EPP balance_power); this script extends that battery profile.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 1; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
backup() { [ -e "$1" ] && cp -a "$1" "$1.fenestra-bak-$STAMP" || true; }
latest_backup() { ls -1t "$1".fenestra-bak-* 2>/dev/null | head -1 || true; }

SPOTLIGHT=/usr/share/gnome-shell/extensions/windows-spotlight@local
HOWDY=/etc/howdy/config.ini
PROFILE_DIR=/etc/tuned/profiles/fenestra-battery
PPD=/etc/tuned/ppd.conf

if [ "${1:-}" = "--revert" ]; then
    for f in "$SPOTLIGHT/hello.js" "$SPOTLIGHT/lockStatus.js" "$HOWDY" "$PPD"; do
        b="$(latest_backup "$f")"; [ -n "$b" ] && cp -a "$b" "$f" && echo "restored $f"
    done
    rm -rf "$PROFILE_DIR"
    systemctl enable --now ModemManager.service 2>/dev/null || true
    systemctl restart tuned-ppd.service
    echo "Reverted. Log out and back in for the lock-screen extension."
    exit 0
fi

# 1. Lock/login screen extension (system copy, needs root) ------------------
# hello.js: the 122 Windows Hello PNG frames were decoded at every session
#   start; now they are warmed only when the lock/login screen activates.
# lockStatus.js: the 5 s status refresh ran forever on the desktop; now it only
#   ticks while the lock screen shows the Wi-Fi/battery glyphs.
# Both files are path-neutral, so the repo copy installs as-is.
if [ -d "$SPOTLIGHT" ]; then
    for f in hello.js lockStatus.js; do
        src="$REPO/desktop/extensions/fenestra-spotlight@fenestra-os.github.io/$f"
        if ! cmp -s "$src" "$SPOTLIGHT/$f"; then
            backup "$SPOTLIGHT/$f"; install -m 0644 "$src" "$SPOTLIGHT/$f"; echo "updated $SPOTLIGHT/$f"
        fi
    done
fi

# 2. Howdy: give up sooner when no face is found ----------------------------
# A match takes ~0.5 s after the camera starts (measured from the journal), but
# while Howdy runs, the password field is not offered. timeout 8 -> 4 s cuts the
# wait (and the camera's on-time) in half when the face is not seen.
# Kept: use_cnn=false, max_height=320, snapshots off, end_report off.
if [ -f "$HOWDY" ] && grep -qE '^timeout *= *([5-9]|[1-9][0-9])' "$HOWDY"; then
    backup "$HOWDY"
    sed -i -E 's/^timeout *= *[0-9]+/timeout = 4/' "$HOWDY"
    echo "howdy: timeout = 4"
fi

# 3. Battery profile for tuned-ppd -------------------------------------------
# On battery, "Balanced" becomes fenestra-battery = balanced-battery plus:
#   - PCIe ASPM powersupersave (L1 substates for NVMe / Wi-Fi / Thunderbolt),
#   - no NMI watchdog (one timer interrupt per CPU per 10 s less),
#   - lazier dirty-page writeback (fewer NVMe wakeups).
# On AC tuned switches back to "balanced", which restores all of these.
# "Power saver" (manual) still maps to tuned's powersave profile.
mkdir -p "$PROFILE_DIR"
cat > "$PROFILE_DIR/tuned.conf" <<'CONF'
[main]
summary=Fenestra: balanced-battery plus ASPM/watchdog/writeback savings
include=balanced-battery

[sysfs]
/sys/module/pcie_aspm/parameters/policy=powersupersave

[sysctl]
kernel.nmi_watchdog=0
vm.dirty_writeback_centisecs=1500
CONF
if [ -f "$PPD" ] && ! grep -q '^balanced=fenestra-battery' "$PPD"; then
    backup "$PPD"
    if grep -q '^\[battery\]' "$PPD"; then
        sed -i -E '/^\[battery\]/,/^\[/{s/^balanced=.*/balanced=fenestra-battery/}' "$PPD"
        grep -q '^balanced=fenestra-battery' "$PPD" || sed -i '/^\[battery\]/a balanced=fenestra-battery' "$PPD"
    else
        printf '\n[battery]\nbalanced=fenestra-battery\n' >> "$PPD"
    fi
    echo "tuned-ppd: battery balanced -> fenestra-battery"
fi
systemctl restart tuned-ppd.service

# 4. Services with nothing to do on this laptop ------------------------------
# No WWAN modem ("mmcli -L": No modems were found).
systemctl disable --now ModemManager.service 2>/dev/null && echo "ModemManager disabled" || true

echo
echo "Done. Verify:"
echo "  tuned-adm active                       # fenestra-battery when unplugged"
echo "  cat /sys/module/pcie_aspm/parameters/policy"
echo "  grep ^timeout $HOWDY"
echo "Log out and back in once so the lock screen loads the new extension files."

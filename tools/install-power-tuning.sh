#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Battery tuning for any laptop running Fenestra; run once as a normal user (asks for sudo).
# Keeps full performance: nothing here limits turbo or the top frequency.
#   - "Balanced" on battery: tuned's balanced-battery plus deeper PCIe link states;
#   - Intel hybrid CPUs: intel_lpmd moves light work to the low-power cores on battery, and leaves
#     them as soon as the load rises (Meteor Lake and later power off the compute tile then);
#   - Fedora's Intel VA-API driver has no H.264/HEVC: RPM Fusion's full one, when that repo is on;
#   - every suspend logs how long the hardware really slept, and what blocked it when it didn't
#     (/var/log/fenestra-power.log), so a bad suspend can be diagnosed afterwards.
# Undo: tools/install-power-tuning.sh --revert
set -u
[ "$(id -u)" = 0 ] || exec sudo bash "$(readlink -f "$0")" "$@"

PROFILE=/etc/tuned/profiles/fenestra-battery
HOOK=/usr/lib/systemd/system-sleep/fenestra-power-log
PPD=/etc/tuned/ppd.conf

if [ "${1:-}" = --revert ]; then
    rm -f "$HOOK"
    command -v intel_lpmd_control >/dev/null && intel_lpmd_control OFF >/dev/null 2>&1
    rm -f "$PROFILE/script.sh"
    sed -i '/^\[script\]/,$d' "$PROFILE/tuned.conf" 2>/dev/null
    systemctl try-restart tuned tuned-ppd
    echo "Reverted."
    exit 0
fi

if [ -f /usr/lib/tuned/profiles/balanced-battery/tuned.conf ] && [ -f "$PPD" ]; then
    mkdir -p "$PROFILE"
    cat > "$PROFILE/tuned.conf" <<'CONF'
[main]
summary=Fenestra: balanced-battery plus ASPM, watchdog, writeback and low-power cores
include=balanced-battery

[sysfs]
/sys/module/pcie_aspm/parameters/policy=powersupersave

[sysctl]
kernel.nmi_watchdog=0
vm.dirty_writeback_centisecs=1500

[script]
script=${i:PROFILE_DIR}/script.sh
CONF
    cat > "$PROFILE/script.sh" <<'SCRIPT'
#!/bin/sh
# Devices that are idle go to sleep by themselves (runtime power management), as powertop's
# tunables: PCI devices, SATA links, I2C adapters. They wake on use; nothing gets slower. Left on
# when the profile ends: it is the kernel's own recommendation for laptops.
if [ "$1" = start ]; then
    for f in /sys/bus/pci/devices/*/power/control /sys/bus/i2c/devices/*/power/control \
             /sys/block/*/device/power/control /sys/class/scsi_host/*/device/power/control; do
        [ -w "$f" ] && echo auto > "$f" 2>/dev/null
    done
fi
# intel_lpmd: AUTO on battery, OFF when this profile ends. Harmless where it doesn't exist.
command -v intel_lpmd_control >/dev/null 2>&1 || exit 0
systemctl -q is-active intel_lpmd || exit 0
case "$1" in
    start) intel_lpmd_control AUTO >/dev/null 2>&1 ;;
    stop) intel_lpmd_control OFF >/dev/null 2>&1 ;;
esac
exit 0
SCRIPT
    chmod 755 "$PROFILE/script.sh"
    grep -q '^\[battery\]' "$PPD" || printf '\n[battery]\n' >> "$PPD"
    sed -i '/^\[battery\]/,$ s/^balanced=.*/balanced=fenestra-battery/' "$PPD"
    sed -n '/^\[battery\]/,$p' "$PPD" | grep -q '^balanced=' || sed -i '/^\[battery\]/a balanced=fenestra-battery' "$PPD"
    systemctl try-restart tuned tuned-ppd
fi

mkdir -p "$(dirname "$HOOK")"
cat > "$HOOK" <<'SLEEP'
#!/bin/bash
# After each suspend: seconds asleep, seconds the hardware really slept, and the blockers if low.
STATE=/run/fenestra-power-suspend; LOG=/var/log/fenestra-power.log
case "$1" in
pre) date +%s > "$STATE"
     cat /proc/interrupts > "$STATE.irq" 2>/dev/null
     grep -H . /sys/firmware/acpi/interrupts/gpe[0-9A-F]* /sys/firmware/acpi/interrupts/sci 2>/dev/null | awk '{print $1, $2}' > "$STATE.gpe" ;;
post)
    [ -r "$STATE" ] || exit 0
    t=$(( $(date +%s) - $(cat "$STATE") )); hw=$(( $(cat /sys/power/suspend_stats/last_hw_sleep 2>/dev/null || echo 0) / 1000000 ))
    pct=$(( t > 0 ? 100 * hw / t : 0 ))
    echo "$(date -Is) $2 slept ${t}s hardware ${hw}s (${pct}%)" >> "$LOG"
    if [ "$t" -gt 120 ] && [ -r "$STATE.irq" ]; then
        # What woke the CPU while asleep: the interrupts and ACPI events that fired most.
        echo "--- interrupts during sleep (count name)" >> "$LOG"
        cat /proc/interrupts | awk 'NR==FNR { k=$1; s=0; for (i=2;i<=NF;i++) if ($i ~ /^[0-9]+$/) s+=$i; a[k]=s; next }
            { k=$1; s=0; n=""; for (i=2;i<=NF;i++) { if ($i ~ /^[0-9]+$/) s+=$i; else n=n" "$i } d=s-a[k]; if (d>0) print d, k n }' "$STATE.irq" - \
            | sort -rn | head -12 >> "$LOG"
        echo "--- ACPI events during sleep (count name)" >> "$LOG"
        grep -H . /sys/firmware/acpi/interrupts/gpe[0-9A-F]* /sys/firmware/acpi/interrupts/sci 2>/dev/null | awk '{print $1, $2}' \
            | awk 'NR==FNR { a[$1]=$2; next } { d=$2-a[$1]; if (d>0) { sub(/.*\//,"",$1); print d, $1 } }' "$STATE.gpe" - | sort -rn | head -8 >> "$LOG"
    fi
    if [ "$t" -gt 120 ] && [ "$pct" -lt 90 ]; then
        d=/sys/kernel/debug/pmc_core
        for f in substate_status_registers substate_live_status_registers package_cstate_show ltr_show pch_ip_power_gating_status; do
            [ -r "$d/$f" ] && { echo "--- $f"; head -c 6000 "$d/$f"; } >> "$LOG"
        done
        echo "--- wakeup sources" >> "$LOG"
        sort -k6 -n -r /sys/kernel/debug/wakeup_sources 2>/dev/null | head -8 >> "$LOG"
    fi
    chmod 644 "$LOG"
    ;;
esac
exit 0
SLEEP
chmod 755 "$HOOK"

if lspci | grep -qE 'VGA.*Intel|Display.*Intel' && rpm -q libva-intel-media-driver >/dev/null 2>&1 \
    && dnf -q repolist 2>/dev/null | grep -qi rpmfusion-nonfree; then
    dnf -y -q swap libva-intel-media-driver intel-media-driver || echo "VA-API driver: kept Fedora's"
fi

R=/var/log/fenestra-power-report.txt
{
    date -Is; uname -r
    cat /sys/power/mem_sleep
    for f in /sys/kernel/debug/pmc_core/{slp_s0_residency_usec,package_cstate_show,substate_residencies,substate_status_registers,ltr_show}; do
        [ -r "$f" ] && { echo "--- $f"; head -c 8000 "$f"; }
    done
    echo "--- i915 psr"; cat /sys/kernel/debug/dri/*/i915_edp_psr_status 2>/dev/null | head -20
    echo "--- i915 dmc"; cat /sys/kernel/debug/dri/*/i915_dmc_info 2>/dev/null | head -14
    echo "--- rapl"; cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null
} > "$R" 2>&1
chmod 644 "$R"
echo "Done. Report in $R"

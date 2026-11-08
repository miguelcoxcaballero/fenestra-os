#!/usr/bin/env bash
# Fenestra / Galaxy Book health check — run it before and after a Fedora upgrade
# (and after booting a new kernel). No sudo needed; it only reads.
#   bash extras/fedora-upgrade/check.sh
set -u
K=$(uname -r)
pass=0 fail=0 warn=0
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$*"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; fail=$((fail+1)); }
note() { printf '  \033[33mWARN\033[0m  %s\n' "$*"; warn=$((warn+1)); }
hdr()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

hdr "System"
echo "  $(cat /etc/fedora-release), kernel $K, GNOME Shell $(gnome-shell --version 2>/dev/null | awk '{print $3}')"

hdr "Out-of-tree drivers (DKMS) for $K"
for m in ov02c10 ipu-bridge-fix max98390-hda; do
    if dkms status 2>/dev/null | grep -E "^$m/" | grep -q "$K.*installed"; then ok "dkms $m built for $K"
    else bad "dkms $m NOT built for $K  ->  sudo dkms autoinstall -k $K"; fi
done
if modinfo -k "$K" v4l2loopback >/dev/null 2>&1; then ok "v4l2loopback module present"
else bad "v4l2loopback missing  ->  sudo akmods --force --kernels $K"; fi

hdr "Loaded modules"
for m in ov02c10 ipu_bridge intel_ipu6_isys snd_hda_scodec_max98390 snd_hda_scodec_max98390_i2c v4l2loopback; do
    if lsmod | awk '{print $1}' | grep -qx "$m"; then ok "$m loaded"; else bad "$m not loaded"; fi
done
for m in ov02c10 ipu_bridge snd_hda_scodec_max98390; do
    p=$(modinfo -n "$m" 2>/dev/null)
    case "$p" in */updates/*|*/extra/*) ok "$m uses the Samsung-fixed DKMS build" ;; "") ;; *) note "$m is the in-kernel module ($p)" ;; esac
done
if journalctl -k -b --no-pager 2>/dev/null | grep -q "Unknown symbol"; then bad "kernel log has 'Unknown symbol' errors (module loaded before its dependencies)"; else ok "no 'Unknown symbol' errors"; fi

hdr "Camera"
for s in camera-relay-login.service camera-relay-watchdog.service; do
    if systemctl is-active -q "$s"; then ok "$s running"; else bad "$s not running"; fi
done
if command -v cam >/dev/null; then
    n=$(cam -l 2>/dev/null | grep -c "^[0-9]*:")
    [ "$n" -gt 0 ] && ok "libcamera sees $n camera(s)" || bad "libcamera sees no camera (cam -l)"
fi
if v4l2-ctl --list-devices 2>/dev/null | grep -qi loopback || ls /sys/devices/virtual/video4linux 2>/dev/null | grep -q video; then ok "loopback video device present"; else bad "no loopback video device"; fi

hdr "Audio"
if command -v pactl >/dev/null; then
    sinks=$(pactl list short sinks 2>/dev/null | grep -vc -i "dummy\|auto_null")
    [ "$sinks" -gt 0 ] && ok "$sinks audio output(s): $(pactl get-default-sink 2>/dev/null)" || bad "no audio outputs"
    pactl list short sources 2>/dev/null | grep -qv monitor && ok "microphone present" || bad "no microphone"
fi

hdr "Face and fingerprint sign-in"
if python3 -c 'import dlib, cv2' 2>/dev/null; then ok "python3 dlib + OpenCV import ($(python3 -c 'import sys;print(sys.version.split()[0])'))"; else bad "dlib/OpenCV do not import for this Python  ->  install the local rebuild (see README)"; fi
if rpm -q howdy >/dev/null 2>&1; then
    v=$(rpm -q --qf '%{version}-%{release}' howdy)
    d=$(rpm -ql howdy | grep -o 'python3\.[0-9]*' | head -1)
    py=$(python3 -c 'import sys;print(f"python{sys.version_info[0]}.{sys.version_info[1]}")')
    [ "$d" = "$py" ] && ok "howdy $v matches $py" || bad "howdy $v is built for $d, system has $py"
else note "howdy not installed"; fi
systemctl is-active -q howdy-preload.service && ok "howdy-preload running" || note "howdy-preload not running"
command -v fprintd-list >/dev/null && { fprintd-list "$USER" 2>/dev/null | grep -q "finger" && ok "fingerprint enrolled" || note "no fingerprint enrolled / reader not found"; }

hdr "GNOME extensions"
for e in $(gsettings get org.gnome.shell enabled-extensions | tr -d "[]',"); do
    st=$(gnome-extensions info "$e" 2>/dev/null | awk -F': ' '/State/{print $2}')
    case "$st" in ACTIVE|ENABLED) ok "$e" ;; "") note "$e not installed" ;; *) bad "$e state=$st $(gdbus call --session --dest org.gnome.Shell.Extensions --object-path /org/gnome/Shell/Extensions --method org.gnome.Shell.Extensions.GetExtensionErrors "$e" 2>/dev/null | head -c 160)" ;; esac
done
[ "$(gsettings get org.gnome.shell disable-user-extensions)" = false ] && ok "user extensions allowed" || bad "user extensions are disabled  ->  gsettings set org.gnome.shell disable-user-extensions false"
[ -e "/run/user/$(id -u)/gnome-shell-disable-extensions" ] && bad "safe-mode flag present (rm /run/user/$(id -u)/gnome-shell-disable-extensions)"

hdr "Fenestra apps and Explorer"
for a in fenestra-settings fenestra-taskmgr fenestra-notepad fenestra-paint; do
    command -v "$a" >/dev/null && ok "$a installed" || note "$a not installed"
done
L=~/.local/share/nautilus-sidebar-win11
if [ -x "$L/nautilus" ]; then
    want=$(rpm -q --qf "%{version}" nautilus 2>/dev/null); want=${want%%.*}
    have=$(strings "$L/nautilus" 2>/dev/null | grep -m1 -oE '^4[0-9]\.[0-9]+(\.[0-9]+)?$' | cut -d. -f1)
    if [ -n "$want" ] && [ "$want" = "$have" ]; then ok "Explorer layer matches Nautilus $want"
    else bad "Explorer layer built for Nautilus ${have:-?}, system has ${want:-?}  ->  bash extras/fedora-upgrade/nautilus-user-refresh.sh"; fi
    # A layer refreshed before the open / save dialog existed has no nautilus-file-chooser.ui: every
    # app's Save as then shows stock Nautilus' chooser instead of the Explorer dialog.
    [ -f "$L/overlay/ui/nautilus-file-chooser.ui" ] && ok "Explorer open / save dialog in the layer" \
        || bad "Explorer layer has no open / save dialog  ->  bash extras/fedora-upgrade/nautilus-user-refresh.sh"
    if [ -f ~/.local/share/nautilus-python/extensions/fenestra-explorer.py ] && [ ! -f ~/.local/share/nautilus-python/extensions/fenestra_chooser.py ]; then
        bad "per-user Explorer modules lack fenestra_chooser.py  ->  bash extras/fedora-upgrade/nautilus-user-refresh.sh"
    fi
fi

hdr "Third-party repositories"

dnf repolist --enabled 2>/dev/null | grep -qi "claude-desktop" && note "claude-desktop COPR has no Fedora 45 build: disable it before upgrading"

printf '\n%s OK, %s warnings, %s failures\n' "$pass" "$warn" "$fail"
[ "$fail" -eq 0 ]

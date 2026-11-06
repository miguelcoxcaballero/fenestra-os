#!/usr/bin/env bash
# Step 1 of the Fedora 43 -> 45 upgrade for the Galaxy Book (Fenestra). Run as root:
#   sudo bash extras/fedora-upgrade/prepare-f45.sh [KIT_DIR]
# KIT_DIR (default ~/Downloads/Fenestra/fedora45-kit) holds the Fedora 45 rebuilds of
# howdy + python3-dlib, the GNOME-51-ready system extensions and the Hello assets.
#
# It does NOT upgrade Fedora. It:
#   1. backs up /etc and the package list to /var/backups/fenestra-pre-f45-*/
#   2. installs the system-wide Fenestra pieces that work on GNOME 49 and 51
#   3. adds a local repo (/var/local/fenestra-repo/$releasever) with the F45 howdy/dlib
#   4. disables COPRs without a usable Fedora 45 build (claude-desktop, howdy-beta)
#   5. shows the GRUB menu at boot, so an older kernel can always be picked
#   6. updates Fedora 43 fully — this installs kernel 7.2.15, the same kernel Fedora 45
#      ships, and rebuilds the camera/speaker DKMS drivers for it.
# Then reboot (the new kernel is the default), run check.sh, and only if it passes run
# upgrade-f45.sh.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
U=${SUDO_USER:-miguelcoxcaballero}
H=$(getent passwd "$U" | cut -d: -f6)
KIT=${1:-$H/Downloads/Fenestra/fedora45-kit}
[ -d "$KIT/rpms" ] || { echo "kit not found: $KIT" >&2; exit 1; }
log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

log "Backup"
B=/var/backups/fenestra-pre-f45-$(date +%Y%m%d-%H%M)
mkdir -p "$B"
tar -czf "$B/etc.tar.gz" -C / etc 2>/dev/null || true
rpm -qa --qf '%{name}-%{version}-%{release}.%{arch} %{vendor}\n' | sort > "$B/packages.txt"
dkms status > "$B/dkms.txt" 2>&1 || true
cp -a /usr/src/ipu-bridge-fix-* /usr/src/max98390-hda-* /usr/src/ov02c10-* "$B/" 2>/dev/null || true
cp -a /usr/local/bin "$B/usr-local-bin" 2>/dev/null || true
cp -a /usr/share/gnome-shell/extensions/windows-spotlight@local /usr/share/gnome-shell/extensions/single-user-gdm@local "$B/" 2>/dev/null || true
echo "  $B"

log "System-wide Fenestra pieces (GNOME 49 + 51)"
for e in windows-spotlight@local single-user-gdm@local; do
    [ -d "$KIT/system-extensions/$e" ] || continue
    rm -rf "/usr/share/gnome-shell/extensions/$e"
    cp -a "$KIT/system-extensions/$e" /usr/share/gnome-shell/extensions/
done
install -d /usr/share/fenestra/assets
rm -rf /usr/share/fenestra/assets/hello
cp -a "$KIT/assets/hello" /usr/share/fenestra/assets/hello
chmod -R a+rX /usr/share/gnome-shell/extensions /usr/share/fenestra
restorecon -R /usr/share/gnome-shell/extensions /usr/share/fenestra 2>/dev/null || true

log "Local repository for the Fedora 45 rebuilds (howdy, python3-dlib)"
dnf -y -q install createrepo_c
for v in 43 45; do install -d "/var/local/fenestra-repo/$v"; done
cp -f "$KIT"/rpms/*.fc45.*.rpm /var/local/fenestra-repo/45/
createrepo_c -q /var/local/fenestra-repo/43
createrepo_c -q /var/local/fenestra-repo/45
cat > /etc/yum.repos.d/fenestra-local.repo <<'EOF'
[fenestra-local]
name=Fenestra local rebuilds for Fedora $releasever
baseurl=file:///var/local/fenestra-repo/$releasever
enabled=1
gpgcheck=0
priority=10
skip_if_unavailable=True
EOF
restorecon -R /var/local/fenestra-repo 2>/dev/null || true

log "COPRs without a working Fedora 45 build"
dnf copr disable -y dewzor/claude-desktop 2>/dev/null || true   # no fedora-45 chroot; the installed app keeps working
dnf copr disable -y principis/howdy-beta 2>/dev/null || true    # the local rebuild replaces it

log "Keep the fingerprint driver this laptop uses (egismoc + SDCP, COPR tenseventy7)"
# Fedora 45's own libfprint 1.94.100 drives the ETU905A80 with a different driver
# (egis_etu905, no SDCP): enrolled prints could stop matching. Keep the COPR build.
dnf config-manager setopt fedora.excludepkgs=libfprint updates.excludepkgs=libfprint
# The ChatGPT repo metadata signature currently fails to verify; never let it block the upgrade.
dnf config-manager setopt openai-chatgpt.skip_if_unavailable=True || true

log "Fenestra Notepad replaces GNOME Text Editor"
dnf -y remove gnome-text-editor || true

log "Show the GRUB menu (pick the previous kernel if a new one misbehaves)"
grub2-editenv - unset menu_auto_hide || true

log "Update Fedora 43 (kernel 7.2.15 + DKMS drivers)"
dnf -y upgrade --refresh
NEWK=$(rpm -q --last kernel-core | head -1 | sed -E 's/^kernel-core-([^ ]+).*/\1/')
echo "  newest kernel: $NEWK"
dkms autoinstall -k "$NEWK" || true
akmods --force --kernels "$NEWK" || true
dkms status | sed 's/^/  /'
missing=0
for m in ov02c10 ipu-bridge-fix max98390-hda; do
    dkms status | grep -E "^$m/.*$NEWK.*installed" >/dev/null || { echo "  MISSING: $m for $NEWK"; missing=1; }
done
modinfo -k "$NEWK" v4l2loopback >/dev/null 2>&1 || { echo "  MISSING: v4l2loopback for $NEWK"; missing=1; }
dracut -f --kver "$NEWK"

if [ "$missing" = 0 ]; then
    log "Done. Reboot now; Fedora 43 starts with kernel $NEWK."
    echo "  After logging in run:  bash $H/Projects/fenestra-os/extras/fedora-upgrade/check.sh"
    echo "  Check the camera (Meet), speakers, microphone, Hello and fingerprint, Wi-Fi and Bluetooth."
    echo "  If anything fails: reboot and pick 6.17.1 in the GRUB menu — nothing is lost."
else
    log "Some drivers did not build for $NEWK. Do NOT upgrade Fedora yet; send this output to Claude."
    exit 2
fi

# Fenestra — shared kickstart (included by fenestra.ks and fenestra-test.ks).
# Fedora 43 Workstation + the Fenestra desktop overlay. No user is created:
# the Windows-style first-boot setup (fenestra-oobe) creates it on first boot.

url --mirrorlist="https://mirrors.fedoraproject.org/mirrorlist?repo=fedora-43&arch=x86_64"
repo --name=updates --mirrorlist="https://mirrors.fedoraproject.org/mirrorlist?repo=updates-released-f43&arch=x86_64"

lang en_US.UTF-8
keyboard us
timezone Etc/UTC --utc
network --bootproto=dhcp --activate --hostname=fenestra
rootpw --lock
selinux --enforcing
firewall --enabled --service=mdns
# Must stay enabled: "--disable" makes Anaconda write post_install_tools_disabled=1
# to /etc/sysconfig/anaconda, and Fedora's GDM then never starts the initial-setup
# session, so the OOBE never appears (straight to the login screen, no users).
firstboot --enable
xconfig --startxonboot
bootloader --timeout=1

%packages
@^workstation-product-environment
nautilus-python
# ArcMenu (Start) needs the GMenu typelib.
gnome-menus
python3-gobject
python3-pillow
python3-fonttools
python3-cairo
# Fenestra OOBE icon-pack mini browser (WebKitGTK 6 GI typelib).
webkitgtk6.0
icoutils
cascadia-mono-fonts
cascadia-code-fonts
gnome-tweaks
gnome-extensions-app
rsync
# Fedora remix guidelines: no Fedora logos (generic-logos provides system-logos).
-fedora-logos
-fedora-logos-httpd
generic-logos
generic-logos-httpd
# Not part of the Windows-like experience.
-gnome-tour
-initial-setup
-initial-setup-gui
-gnome-shell-extension-background-logo
%end

%post --nochroot --log=/mnt/sysroot/root/fenestra-overlay.log
set -x
SRC=""
for d in /run/install/repo /run/install/isodir /run/install/sources/mount-0000-cdrom /run/install/source; do
    [ -f "$d/fenestra/rootfs.tar.gz" ] && SRC="$d/fenestra" && break
done
if [ -z "$SRC" ]; then
    mkdir -p /tmp/fenestra-media
    for dev in /dev/disk/by-label/* /dev/sr0 /dev/sr1; do
        mount -o ro "$dev" /tmp/fenestra-media 2>/dev/null || continue
        [ -f /tmp/fenestra-media/fenestra/rootfs.tar.gz ] && SRC=/tmp/fenestra-media/fenestra && break
        umount /tmp/fenestra-media
    done
fi
[ -n "$SRC" ] || { echo "Fenestra overlay not found on install media"; exit 1; }
tar -xzf "$SRC/rootfs.tar.gz" -C /mnt/sysroot --no-same-owner
%end

%post --log=/root/fenestra-post.log
set -x
# The overlay was unpacked from the installer environment: give it the
# target's SELinux labels (bin_t for /usr/libexec/fenestra-oobe etc.), or the
# confined GDM/initial-setup session cannot execute it.
restorecon -RF /usr /etc /var/lib/fenestra-spotlight || true
# GDM skips initial setup when this is set (see the note on firstboot above); belt and braces.
if [ -f /etc/sysconfig/anaconda ]; then
    sed -i 's/^post_install_tools_disabled *=.*/post_install_tools_disabled = 0/' /etc/sysconfig/anaconda
fi
# Branding (Fenestra is a Fedora remix).
rm -f /etc/os-release
sed -e 's/^NAME=.*/NAME="Fenestra"/' \
    -e 's/^PRETTY_NAME=.*/PRETTY_NAME="Fenestra 43 (based on Fedora Linux)"/' \
    -e 's/^ID=.*/ID=fenestra\nID_LIKE=fedora/' \
    -e 's|^HOME_URL=.*|HOME_URL="https://github.com/miguelcoxcaballero/fenestra-os"|' \
    -e 's/^LOGO=.*/LOGO=fenestra-logo/' \
    -e 's/^VARIANT=.*/VARIANT="Fenestra Desktop"/' \
    /usr/lib/os-release > /etc/os-release
install -Dm644 /usr/share/fenestra/assets/branding/fenestra-logo.svg /usr/share/icons/hicolor/scalable/apps/fenestra-logo.svg
# Boot entries written before os-release changed still say "Fedora Linux";
# later kernels take PRETTY_NAME from the new os-release.
. /etc/os-release
for e in /boot/loader/entries/*.conf; do
    [ -f "$e" ] || continue
    v=$(sed -n 's/^version //p' "$e")
    sed -i "s|^title .*|title $PRETTY_NAME ($v)|" "$e"
done

# Files: Explorer layer (patched sidebar icons + UI overlay), launched via a wrapper.
/usr/libexec/fenestra/fenestra-patch-nautilus
systemctl enable fenestra-patch-nautilus.service
install -d /usr/local/share/applications
sed -e 's|^Exec=nautilus|Exec=/usr/libexec/fenestra/fenestra-nautilus|' \
    -e 's|^Exec=/usr/bin/nautilus|Exec=/usr/libexec/fenestra/fenestra-nautilus|' \
    /usr/share/applications/org.gnome.Nautilus.desktop > /usr/local/share/applications/org.gnome.Nautilus.desktop

# Settings: anything that opens "Settings" (quick settings gear, app menus) gets
# Fenestra Settings; GNOME Settings stays installed for the "Advanced" buttons.
if [ -f /usr/share/applications/fenestra-settings.desktop ]; then
    install -d /usr/local/share/applications /usr/local/bin
    if [ -f /usr/share/fenestra-settings/data/org.gnome.Settings.desktop ]; then
        install -m644 /usr/share/fenestra-settings/data/org.gnome.Settings.desktop /usr/local/share/applications/org.gnome.Settings.desktop
    else
        sed -e 's|^Exec=.*|Exec=fenestra-settings|' -e 's|^NoDisplay=.*||' -e '/^DBusActivatable/d' \
            -e '/^\[Desktop Action/,$d' /usr/share/applications/org.gnome.Settings.desktop > /usr/local/share/applications/org.gnome.Settings.desktop
        echo 'NoDisplay=true' >> /usr/local/share/applications/org.gnome.Settings.desktop
    fi
    # "gnome-control-center <panel>" (quick settings, notifications, other apps) -> Fenestra Settings;
    # /usr/local/bin comes before /usr/bin, the real binary stays for "Advanced (GNOME Settings)".
    if [ -f /usr/share/fenestra-settings/bin/gnome-control-center ]; then
        install -m755 /usr/share/fenestra-settings/bin/gnome-control-center /usr/local/bin/gnome-control-center
    fi
fi

# Task Manager: Fenestra Task Manager replaces GNOME System Monitor in menus/search.
if [ -x /usr/bin/fenestra-taskmgr ] && [ -f /usr/share/applications/org.gnome.SystemMonitor.desktop ]; then
    install -d /usr/local/share/applications
    sed -e '/^NoDisplay=/d' -e 's|^Exec=.*|Exec=fenestra-taskmgr|' -e '/^DBusActivatable/d' -e '/^\[Desktop Action/,$d' \
        /usr/share/applications/org.gnome.SystemMonitor.desktop \
        > /usr/local/share/applications/org.gnome.SystemMonitor.desktop
    sed -i '/^\[Desktop Entry\]/a NoDisplay=true' /usr/local/share/applications/org.gnome.SystemMonitor.desktop
fi

# System defaults.
grep -q "system-db:local" /etc/dconf/profile/user 2>/dev/null || printf 'user-db:user\nsystem-db:local\nsystem-db:site\nsystem-db:distro\n' > /etc/dconf/profile/user
dconf update
glib-compile-schemas /usr/share/glib-2.0/schemas
fc-cache -f
for t in /usr/share/icons/*/; do [ -f "$t/index.theme" ] && gtk-update-icon-cache -qf "$t" || true; done
ln -sf ../../../usr/share/fenestra/assets/branding/fenestra-logo-256.png /usr/share/pixmaps/fenestra-logo.png 2>/dev/null || true

# Quiet, Windows-like boot: firmware logo + spinner, hidden boot menu.
plymouth-set-default-theme bgrt 2>/dev/null || true
grub2-editenv - set menu_auto_hide=1 || true
%end

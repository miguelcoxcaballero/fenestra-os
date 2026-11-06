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
# Taskbar weather: GNOME Shell's WeatherClient needs the Weather app (locations, provider).
gnome-weather
git-core
# Fenestra Hello: live camera preview (v4l2src, gtk4paintablesink)
gstreamer1-plugins-good
gstreamer1-plugin-gtk4
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
# Fenestra Notepad replaces GNOME Text Editor.
-gnome-text-editor
# Windows-style boot/restart/update screens (theme built by fenestra-plymouth-theme).
plymouth-plugin-script
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
# SELinux labels, branding, Settings/Files/Task Manager hooks, dconf, caches.
# The same script runs after every Fenestra update (fenestra-update).
/usr/libexec/fenestra/fenestra-post-install
# GDM skips initial setup when this is set (see the note on firstboot above); belt and braces.
if [ -f /etc/sysconfig/anaconda ]; then
    sed -i 's/^post_install_tools_disabled *=.*/post_install_tools_disabled = 0/' /etc/sysconfig/anaconda
fi

# Quiet, Windows-like boot: firmware logo + spinner, hidden boot menu.
python3 /usr/libexec/fenestra/fenestra-plymouth-theme /usr/share/plymouth/themes/fenestra --lang en >/dev/null 2>&1 \
    && plymouth-set-default-theme fenestra || plymouth-set-default-theme bgrt 2>/dev/null || true
for k in /lib/modules/*/; do dracut -f --kver "$(basename "$k")" >/dev/null 2>&1 || true; done
grub2-editenv - set menu_auto_hide=1 || true
%end

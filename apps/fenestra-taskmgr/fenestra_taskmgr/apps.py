"""Map processes to desktop applications and friendly names.

GNOME starts every launched application in its own systemd scope,
``app-gnome-<desktop id>-<pid>.scope`` (or ``app-flatpak-<id>-<n>.scope``,
``app-<launcher>-<id>@<x>.service``), so /proc/PID/cgroup tells us reliably
which .desktop application a process belongs to.  GIO_LAUNCHED_DESKTOP_FILE in
/proc/PID/environ is used as a fallback for processes outside such a scope.
"""
from __future__ import annotations

import os
import re
import threading

from .i18n import _

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio
except (ImportError, ValueError):  # pragma: no cover
    Gio = None

_lock = threading.Lock()
_info_cache: dict[str, tuple | None] = {}
_exec_index: dict[str, str] | None = None



def unescape(s: str) -> str:
    """systemd unit name unescaping (\\x2d -> '-')."""
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)


KNOWN_LAUNCHERS = {"gnome", "flatpak", "kde", "xfce", "snap", "dbus", "systemd", "gnome-launched"}


def desktop_id_from_unit(unit: str) -> str | None:
    if not unit.startswith("app-"):
        return None
    if unit.endswith(".scope"):
        body = re.sub(r"-\d+$", "", unit[4:-6])
    elif unit.endswith(".service"):
        body = unit[4:-8].split("@", 1)[0]
    else:
        return None
    if "-" in body:
        launcher, rest = body.split("-", 1)
        if launcher in KNOWN_LAUNCHERS or "." not in launcher:
            body = rest
    did = unescape(body)
    if did.endswith(".desktop"):
        did = did[:-8]
    return did or None


def app_info(desktop_id: str):
    """(name, icon string, displayable, publisher) or None."""
    with _lock:
        if desktop_id in _info_cache:
            return _info_cache[desktop_id]
    res = None
    if Gio is not None:
        info = None
        for cand in (desktop_id + ".desktop", desktop_id.lower() + ".desktop"):
            try:
                info = Gio.DesktopAppInfo.new(cand)
            except TypeError:
                info = None
            if info is not None:
                break
        if info is not None:
            icon = info.get_icon()
            publisher = info.get_string("X-Publisher") or ""
            res = (info.get_name() or desktop_id, icon.to_string() if icon else None,
                   not info.get_nodisplay() and info.should_show(), publisher)
    with _lock:
        _info_cache[desktop_id] = res
    return res


def _build_exec_index():
    """basename(Exec) -> desktop id for displayable apps (used for icons of background helpers)."""
    idx = {}
    if Gio is None:
        return idx
    try:
        for info in Gio.AppInfo.get_all():
            exe = info.get_executable() or ""
            base = os.path.basename(exe)
            if base and base not in ("env", "sh", "bash", "flatpak", "python3", "gjs") and info.get_id():
                idx.setdefault(base, info.get_id()[:-8] if info.get_id().endswith(".desktop") else info.get_id())
    except Exception:  # noqa: BLE001 - best effort
        pass
    return idx


def desktop_for_exec(name: str) -> str | None:
    global _exec_index
    if _exec_index is None:
        _exec_index = _build_exec_index()
    return _exec_index.get(name)


# Friendly descriptions for common Linux processes (shown like Windows' file descriptions).
FRIENDLY = {
    "systemd": "systemd (System and Service Manager)",
    "gnome-shell": "GNOME Shell",
    "fenestra-shell": "Fenestra Shell",
    "kwin_wayland": "Window Manager (KWin)",
    "kwin_wayland_wrapper": "Window Manager (KWin)",
    "kscreenlocker_greet": "Lock Screen",
    "xdg-desktop-portal-kde": "Desktop Portal (KWin)",
    "gnome-session-binary": "GNOME Session Manager",
    "gnome-session-ctl": "GNOME Session Control",
    "gnome-session-service": "GNOME Session Manager",
    "Xwayland": "Xwayland",
    "pipewire": "PipeWire Multimedia Service",
    "pipewire-pulse": "PipeWire PulseAudio Service",
    "wireplumber": "WirePlumber Session Manager",
    "dbus-broker": "D-Bus Message Broker",
    "dbus-broker-launch": "D-Bus Broker Launcher",
    "dbus-daemon": "D-Bus Message Bus",
    "NetworkManager": "Network Manager",
    "polkitd": "Authorization Manager (polkit)",
    "ibus-daemon": "IBus Input Method Framework",
    "ibus-portal": "IBus Portal",
    "ibus-extension-gtk3": "IBus Extension",
    "ibus-engine-simple": "IBus Simple Engine",
    "xdg-desktop-portal": "Desktop Portal Service",
    "xdg-desktop-portal-gnome": "Desktop Portal (GNOME)",
    "xdg-desktop-portal-gtk": "Desktop Portal (GTK)",
    "xdg-document-portal": "Document Portal",
    "xdg-permission-store": "Permission Store",
    "gvfsd": "Virtual File System Service",
    "gvfsd-fuse": "Virtual File System (FUSE)",
    "gvfsd-metadata": "Virtual File System Metadata",
    "gvfsd-trash": "Recycle Bin Service",
    "gvfs-udisks2-volume-monitor": "Volume Monitor",
    "at-spi-bus-launcher": "Accessibility Bus",
    "at-spi2-registryd": "Accessibility Registry",
    "firewalld": "Firewall Service",
    "chronyd": "Time Synchronization (chrony)",
    "systemd-journald": "Journal Service",
    "systemd-logind": "Login Manager",
    "systemd-udevd": "Device Manager (udev)",
    "systemd-resolved": "Network Name Resolution",
    "systemd-oomd": "Out-of-Memory Monitor",
    "systemd-userdbd": "User Database Service",
    "systemd-homed": "Home Area Manager",
    "systemd-machined": "Virtual Machine Registration",
    "systemd-timesyncd": "Time Synchronization",
    "gdm": "GNOME Display Manager",
    "gdm-session-worker": "GNOME Display Manager Session",
    "gdm-wayland-session": "GNOME Display Manager Wayland Session",
    "bluetoothd": "Bluetooth Support Service",
    "cupsd": "Print Spooler (CUPS)",
    "cups-browsed": "Printer Discovery",
    "accounts-daemon": "Accounts Service",
    "upowerd": "Power Management Service",
    "udisksd": "Disk Management Service",
    "rtkit-daemon": "Realtime Policy Service",
    "ModemManager": "Mobile Broadband Service",
    "avahi-daemon": "Network Discovery (Avahi)",
    "fwupd": "Firmware Update Service",
    "packagekitd": "Package Management Service",
    "gnome-keyring-daemon": "Credential Manager (GNOME Keyring)",
    "colord": "Color Management Service",
    "power-profiles-daemon": "Power Profiles Service",
    "tuned": "System Tuning Service",
    "tuned-ppd": "Power Profiles Service",
    "sshd": "OpenSSH Server",
    "crond": "Task Scheduler (cron)",
    "auditd": "Security Audit Service",
    "abrtd": "Problem Reporting Service",
    "thermald": "Thermal Management Service",
    "irqbalance": "Interrupt Balancer",
    "switcheroo-control": "Graphics Switching Service",
    "localsearch-3": "File Indexer",
    "tracker-miner-fs-3": "File Indexer",
    "evolution-source-registry": "Evolution Data Source Registry",
    "evolution-calendar-factory": "Evolution Calendar Service",
    "evolution-addressbook-factory": "Evolution Contacts Service",
    "evolution-alarm-notify": "Calendar Reminders",
    "goa-daemon": "Online Accounts Service",
    "goa-identity-service": "Online Accounts Identity Service",
    "gsd-color": "Settings Daemon (Color)",
    "gsd-datetime": "Settings Daemon (Date & Time)",
    "gsd-housekeeping": "Settings Daemon (Housekeeping)",
    "gsd-keyboard": "Settings Daemon (Keyboard)",
    "gsd-media-keys": "Settings Daemon (Media Keys)",
    "gsd-power": "Settings Daemon (Power)",
    "gsd-print-notifications": "Settings Daemon (Printers)",
    "gsd-rfkill": "Settings Daemon (Airplane Mode)",
    "gsd-screensaver-proxy": "Settings Daemon (Screen Saver)",
    "gsd-sharing": "Settings Daemon (Sharing)",
    "gsd-smartcard": "Settings Daemon (Smart Card)",
    "gsd-sound": "Settings Daemon (Sound)",
    "gsd-usb-protection": "Settings Daemon (USB Protection)",
    "gsd-wacom": "Settings Daemon (Tablet)",
    "gsd-xsettings": "Settings Daemon (X Settings)",
    "gsd-a11y-settings": "Settings Daemon (Accessibility)",
    "gsd-disk-utility-notify": "Settings Daemon (Disk Notifications)",
    "gsd-printer": "Settings Daemon (Printers)",
    "gnome-shell-calendar-server": "Shell Calendar Service",
    "mutter-x11-frames": "Window Frames (X11)",
    "dconf-service": "Configuration Database",
    "flatpak-session-helper": "Flatpak Session Helper",
    "flatpak-portal": "Flatpak Portal",
    "gjs": "JavaScript Host",
    "snapd": "Snap Service",
    "wpa_supplicant": "Wi-Fi Security Service",
    "iwd": "Wireless Service",
    "smartd": "Disk Health Monitor",
    "mcelog": "Hardware Error Logging",
    "low-memory-monitor": "Low Memory Monitor",
    "uresourced": "Resource Allocation Service",
    "geoclue": "Location Service",
    "boltd": "Thunderbolt Service",
    "iio-sensor-proxy": "Sensor Service",
    "rsyslogd": "System Logging Service",
    "kthreadd": "System",
    "sh": "Command Shell",
    "bash": "Bash",
    "fenestra-taskmgr": "Task Manager",
}


def friendly(name: str) -> str:
    v = FRIENDLY.get(name)
    if v is None and name.startswith("gsd-"):
        v = "Settings Daemon (%s)" % name[4:].replace("-", " ").title()
    return _(v) if v else name

"""Device / OS information and hostname handling (hostnamed)."""
from __future__ import annotations

import os
import platform
import re
import socket

from gi.repository import Gio, GLib

from .. import util
from . import demo

HOSTNAMED = "org.freedesktop.hostname1"


def hostname() -> str:
    if util.DEMO:
        return demo.HOSTNAME
    p = util.dbus_proxy_sync(Gio.BusType.SYSTEM, HOSTNAMED, "/org/freedesktop/hostname1", HOSTNAMED)
    for key in ("PrettyHostname", "StaticHostname", "Hostname"):
        v = util.prop(p, key)
        if v:
            return v
    return socket.gethostname() or "fenestra-pc"


def chassis() -> str:
    p = util.dbus_proxy_sync(Gio.BusType.SYSTEM, HOSTNAMED, "/org/freedesktop/hostname1", HOSTNAMED)
    return util.prop(p, "Chassis", "") or ""


def model() -> str:
    if util.DEMO:
        return demo.MODEL
    vendor = util.read_file("/sys/class/dmi/id/sys_vendor")
    name = util.read_file("/sys/class/dmi/id/product_name")
    version = util.read_file("/sys/class/dmi/id/product_version")
    junk = {"", "To be filled by O.E.M.", "System Product Name", "Default string", "None"}
    if name in junk:
        name = util.read_file("/sys/class/dmi/id/board_name")
    if name in junk:
        return ""
    if vendor and vendor not in junk and not name.lower().startswith(vendor.lower().split()[0]):
        vendor_short = vendor.split()[0].title() if vendor.isupper() else vendor.split()[0]
        name = f"{vendor_short} {name}"
    if version and version not in junk and len(version) < 20 and version not in name and \
            not version.lower().startswith("not"):
        name = f"{name} {version}" if version.isalpha() else name
    return name


def cpu() -> str:
    if util.DEMO:
        return demo.CPU
    txt = util.read_file("/proc/cpuinfo")
    m = re.search(r"^model name\s*:\s*(.+)$", txt, re.M)
    name = m.group(1).strip() if m else platform.processor() or platform.machine()
    name = re.sub(r"\s+", " ", name)
    mhz = None
    try:
        mhz = int(util.read_file("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "0")) / 1e6
    except ValueError:
        pass
    if mhz and "GHz" not in name:
        name = f"{name}   {mhz:.2f} GHz"
    return name


def cpu_count() -> int:
    return os.cpu_count() or 1


def ram_total() -> int:
    txt = util.read_file("/proc/meminfo")
    m = re.search(r"MemTotal:\s+(\d+)", txt)
    return int(m.group(1)) * 1024 if m else 0


def ram_usable_str() -> str:
    if util.DEMO:
        return demo.RAM
    total = ram_total()
    gb = total / 1024 ** 3
    nominal = 2 ** round(__import__("math").log2(gb)) if gb > 1 else gb
    if abs(nominal - gb) / nominal < 0.15:
        return f"{nominal:.0f} GB ({gb:.1f} GB usable)"
    return f"{gb:.1f} GB"


def gpu(callback):
    if util.DEMO:
        demo.later(callback, demo.GPU)
        return
    def done(ok, out, _err):
        names = []
        for line in out.splitlines():
            if re.search(r"VGA compatible controller|3D controller|Display controller", line):
                n = line.split(": ", 1)[-1]
                n = re.sub(r"\s*\(rev [0-9a-f]+\)$", "", n)
                n = n.replace("Corporation ", "").replace("[AMD/ATI] ", "")
                names.append(n.strip())
        callback(names)
    util.run_async(["lspci"], done)


def os_release() -> dict:
    data = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        txt = util.read_file(path)
        if txt:
            for line in txt.splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    data[k] = v.strip().strip('"')
            break
    return data


def os_info() -> dict:
    if util.DEMO:
        return demo.os_info()
    r = os_release()
    name = r.get("NAME", "Fenestra")
    pretty = r.get("PRETTY_NAME", name)
    # This is the Fenestra settings app: present the product as Fenestra and keep the
    # base distribution as extra information.
    edition = r.get("VARIANT") or r.get("VARIANT_ID", "").title() or "Workstation"
    is_fenestra = "fenestra" in (r.get("ID", "") + name).lower()
    return {
        "product": name if is_fenestra else "Fenestra",
        "edition": f"Fenestra {edition}" if not is_fenestra else f"{name} {edition}",
        "version": r.get("FENESTRA_VERSION") or r.get("VERSION_ID") or "1.0",
        "base": pretty,
        "build": r.get("BUILD_ID") or platform.release(),
        "kernel": platform.release(),
        "home_url": r.get("HOME_URL", ""),
        "support_url": r.get("SUPPORT_URL", ""),
        "installed": install_date(),
    }


def install_date() -> str:
    for p in ("/etc/machine-id", "/var/log/anaconda", "/lost+found"):
        try:
            st = os.stat(p)
            return GLib.DateTime.new_from_unix_local(int(st.st_mtime)).format("%x")
        except OSError:
            continue
    return ""


def system_type() -> str:
    arch = platform.machine()
    bits = "64-bit" if arch in ("x86_64", "aarch64", "ppc64le", "s390x", "riscv64") else "32-bit"
    proc = "x64-based processor" if arch == "x86_64" else f"{arch} processor"
    return f"{bits} operating system, {proc}"


def pen_touch() -> str:
    if util.DEMO:
        return "No pen or touch input is available for this display"
    try:
        devs = util.read_file("/proc/bus/input/devices").lower()
    except OSError:
        devs = ""
    touch = "touchscreen" in devs or "touch screen" in devs
    pen = "stylus" in devs or " pen" in devs
    if touch and pen:
        return "Pen and touch support"
    if touch:
        return "Touch support"
    return "No pen or touch input is available for this display"


def uptime() -> str:
    if util.DEMO:
        return "2h 14m"
    try:
        secs = float(util.read_file("/proc/uptime").split()[0])
    except (ValueError, IndexError):
        return ""
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return (f"{d}d " if d else "") + f"{h}h {m}m"


def device_id() -> str:
    if util.DEMO:
        return demo.DEVICE_ID
    mid = util.read_file("/etc/machine-id")
    if len(mid) == 32:
        return f"{mid[:8]}-{mid[8:12]}-{mid[12:16]}-{mid[16:20]}-{mid[20:]}".upper()
    return ""


def product_id() -> str:
    if util.DEMO:
        return ""
    pid = util.read_file("/sys/class/dmi/id/product_uuid") or util.read_file("/sys/class/dmi/id/product_serial")
    return pid.upper() if pid else ""


def rename(name: str, callback=None):
    """Set pretty + static hostname through hostnamed (polkit will prompt)."""
    static = re.sub(r"[^a-zA-Z0-9-]", "-", name).strip("-").lower()[:63] or "fenestra"

    def after_pretty(ok, res):
        if not ok:
            if callback:
                callback(False, res)
            return
        util.dbus_call(Gio.BusType.SYSTEM, HOSTNAMED, "/org/freedesktop/hostname1", HOSTNAMED,
                       "SetStaticHostname", GLib.Variant("(sb)", (static, True)), callback)
    util.dbus_call(Gio.BusType.SYSTEM, HOSTNAMED, "/org/freedesktop/hostname1", HOSTNAMED,
                   "SetPrettyHostname", GLib.Variant("(sb)", (name, True)), after_pretty)


def wallpaper_path(dark: bool) -> str | None:
    """Desktop picture shown in previews (the session's wallpaper backend decides)."""
    if util.DEMO:
        return demo.wallpaper(dark)
    from . import appearance
    return appearance.wallpaper(dark)


def gnome_wallpaper_path(dark: bool) -> str | None:
    """Picture from org.gnome.desktop.background (GNOME session, and the mirror in Fenestra)."""
    key = "picture-uri-dark" if dark else "picture-uri"
    uri = util.gget("org.gnome.desktop.background", key) or util.gget(
        "org.gnome.desktop.background", "picture-uri")
    if not uri:
        return None
    path = Gio.File.new_for_uri(uri).get_path() if "://" in uri else uri
    if path and path.endswith(".xml"):
        # GNOME slideshow / day-night XML: pick the first image
        txt = util.read_file(path)
        m = re.search(r"<file>([^<]+)</file>", txt) or re.search(r"<from>([^<]+)</from>", txt)
        path = m.group(1).strip() if m else None
    return path if path and os.path.isfile(path) else None

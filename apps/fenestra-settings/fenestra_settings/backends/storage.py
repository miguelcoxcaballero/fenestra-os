"""Disk usage and temporary files cleanup."""
from __future__ import annotations

import os
import shutil
import threading

from gi.repository import GLib

from .. import util

REAL_FS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "vfat", "exfat", "ntfs", "ntfs3", "f2fs",
           "fuseblk", "zfs", "bcachefs"}


class Volume:
    def __init__(self, mount, device, fstype, total, used, free):
        self.mount, self.device, self.fstype = mount, device, fstype
        self.total, self.used, self.free = total, used, free

    @property
    def fraction(self):
        return self.used / self.total if self.total else 0.0

    @property
    def label(self):
        if self.mount == "/":
            return "System (/)"
        if self.mount == "/home":
            return "Home (/home)"
        return os.path.basename(self.mount) + f" ({self.mount})"


def volumes():
    if util.DEMO:
        from . import demo
        return demo.volumes()
    seen_dev = set()
    out = []
    try:
        with open("/proc/self/mounts") as f:
            lines = f.read().splitlines()
    except OSError:
        return out
    for line in lines:
        p = line.split()
        if len(p) < 3:
            continue
        dev, mnt, fs = p[0], p[1].replace("\\040", " "), p[2]
        if fs not in REAL_FS or mnt.startswith(("/boot", "/snap", "/var/lib", "/sysroot/ostree")):
            continue
        if mnt.startswith("/run/media") is False and mnt.startswith("/run"):
            continue
        if dev in seen_dev:
            continue
        try:
            st = os.statvfs(mnt)
        except OSError:
            continue
        total = st.f_blocks * st.f_frsize
        if total < 512 * 1024 * 1024:
            continue
        free = st.f_bavail * st.f_frsize
        used = total - st.f_bfree * st.f_frsize
        seen_dev.add(dev)
        out.append(Volume(mnt, dev, fs, total, used, free))
    out.sort(key=lambda v: (v.mount != "/", v.mount))
    return out


def dir_size(path, callback):
    """Async `du -sb`; callback(bytes or 0)."""
    if util.DEMO:
        from . import demo
        demo.later(callback, 650 * 1024 * 1024)
        return
    if not os.path.exists(path):
        GLib.idle_add(lambda: (callback(0), False)[1])
        return

    def done(ok, out, _e):
        try:
            callback(int(out.split()[0]))
        except (ValueError, IndexError):
            callback(0)
    util.run_async(["du", "-sb", path], done)


def trash_dir():
    return os.path.join(GLib.get_user_data_dir(), "Trash")


def thumbnails_dir():
    return os.path.join(GLib.get_user_cache_dir(), "thumbnails")


def categories(callback):
    """Approximate breakdown of the home folder: callback({key: bytes})."""
    if util.DEMO:
        from . import demo
        demo.later(callback, demo.categories())
        return
    home = os.path.expanduser("~")
    targets = {
        "documents": GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS),
        "pictures": GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES),
        "videos": GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS),
        "music": GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC),
        "downloads": GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD),
        "temp": None,
        "apps_user": os.path.join(home, ".local/share/flatpak"),
        "apps_system": "/var/lib/flatpak",
    }
    result = {}
    pending = [len(targets)]

    def put(key, val):
        result[key] = val
        pending[0] -= 1
        if pending[0] == 0:
            callback(result)

    for key, path in targets.items():
        if key == "temp":
            temp_size(lambda n: put("temp", n))
        elif path and path != home:
            dir_size(path, lambda n, k=key: put(k, n))
        else:
            GLib.idle_add(lambda k=key: (put(k, 0), False)[1])


def temp_size(callback):
    total = [0, 2]

    def add(n):
        total[0] += n
        total[1] -= 1
        if total[1] == 0:
            callback(total[0])
    dir_size(trash_dir(), add)
    dir_size(thumbnails_dir(), add)


def clean_temp(trash: bool, thumbnails: bool, callback):
    """Empty trash and/or delete thumbnail cache (refused in read-only mode)."""
    if util.READ_ONLY:
        GLib.idle_add(lambda: (callback(False), False)[1])
        return

    def work():
        ok = True
        if thumbnails:
            try:
                shutil.rmtree(thumbnails_dir(), ignore_errors=True)
            except OSError:
                ok = False
        GLib.idle_add(lambda: (after_thumbs(ok), False)[1])

    def after_thumbs(ok):
        if trash:
            util.run_async(["gio", "trash", "--empty"], lambda o, *_: callback(ok and o), mutating=True)
        else:
            callback(ok)
    threading.Thread(target=work, daemon=True).start()

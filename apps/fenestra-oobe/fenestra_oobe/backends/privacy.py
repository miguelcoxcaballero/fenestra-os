"""Privacy settings and the optional import of assets from another system."""

import glob
import json
import os
import shutil
import subprocess
import sys
import time

from gi.repository import Gio

from . import log
from .. import paths


def _settings(schema_id: str):
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(schema_id, True) is None:
        return None
    return Gio.Settings.new(schema_id)


# id -> (schema, key)
PRIVACY_KEYS = {
    "location": ("org.gnome.system.location", "enabled"),
    "auto-timezone": ("org.gnome.desktop.datetime", "automatic-timezone"),
    "diagnostics": ("org.gnome.desktop.privacy", "report-technical-problems"),
    "tailored": ("org.gnome.desktop.privacy", "remember-recent-files"),
}

ABRT_USER_CONF = os.path.join(os.path.expanduser("~"), ".config", "abrt", "settings", "abrt-applet.conf")


def abrt_available() -> bool:
    return bool(shutil.which("abrt-applet") or shutil.which("abrt-auto-reporting")
                or os.path.exists("/usr/bin/abrt-applet"))


class PrivacyBackend:
    def __init__(self, demo: bool):
        self.demo = demo

    def defaults(self) -> dict[str, bool]:
        """Current values, used as the initial toggle state.

        Like the reference OOBE every option starts as "Yes" unless the
        system default says otherwise.
        """
        out = {}
        for key, (schema, k) in PRIVACY_KEYS.items():
            s = _settings(schema)
            out[key] = bool(s.get_boolean(k)) if s is not None else True
        out["location"] = True
        out["auto-timezone"] = True
        return out

    def apply(self, values: dict[str, bool]):
        if self.demo:
            log.info("[demo] would apply privacy settings %s", values)
            return
        for key, val in values.items():
            schema, k = PRIVACY_KEYS.get(key, (None, None))
            s = _settings(schema) if schema else None
            if s is not None:
                s.set_boolean(k, bool(val))
        # Location must be on for automatic time zone to work.
        if values.get("auto-timezone") and not values.get("location"):
            s = _settings("org.gnome.desktop.datetime")
            if s is not None:
                s.set_boolean("automatic-timezone", False)
        Gio.Settings.sync()
        if "diagnostics" in values and abrt_available():
            self._set_abrt_autoreport(values["diagnostics"])

    @staticmethod
    def _set_abrt_autoreport(enabled: bool):
        os.makedirs(os.path.dirname(ABRT_USER_CONF), exist_ok=True)
        lines = []
        if os.path.exists(ABRT_USER_CONF):
            with open(ABRT_USER_CONF, encoding="utf-8") as fh:
                lines = [l for l in fh.read().splitlines() if not l.startswith("AutoreportingEnabled")]
        lines.append(f"AutoreportingEnabled = {'yes' if enabled else 'no'}")
        with open(ABRT_USER_CONF, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    # -- other-system import ---------------------------------------------
    @staticmethod
    def _find_ci(root: str, *parts: str) -> str | None:
        """Case-insensitive path lookup (NTFS mounts may be case sensitive)."""
        cur = root
        for part in parts:
            try:
                names = os.listdir(cur)
            except OSError:
                return None
            match = next((n for n in names if n.lower() == part.lower()), None)
            if match is None:
                return None
            cur = os.path.join(cur, match)
        return cur

    def find_other_system(self) -> str | None:
        """Return the mount point of a partition with ``Windows/Fonts/segoeui.ttf``."""
        if self.demo:
            return "/run/media/demo/OS"
        user = os.environ.get("USER") or os.path.basename(os.path.expanduser("~"))
        candidates = glob.glob(f"/run/media/{user}/*") + glob.glob("/mnt/*") + glob.glob("/media/*")
        for root in candidates:
            if self._find_ci(root, "Windows", "Fonts", "segoeui.ttf"):
                return root
        # Try to mount unmounted NTFS partitions read-only without prompting.
        for dev in self._unmounted_ntfs():
            mnt = self._mount_readonly(dev)
            if mnt and self._find_ci(mnt, "Windows", "Fonts", "segoeui.ttf"):
                return mnt
        return None

    @staticmethod
    def _unmounted_ntfs() -> list[str]:
        try:
            res = subprocess.run(["lsblk", "-J", "-o", "PATH,FSTYPE,MOUNTPOINTS"], capture_output=True,
                                 text=True, timeout=5)
            data = json.loads(res.stdout or "{}")
        except (OSError, ValueError, subprocess.SubprocessError):
            return []
        out = []

        def walk(nodes):
            for n in nodes or []:
                mps = [m for m in (n.get("mountpoints") or []) if m]
                if (n.get("fstype") or "").lower() in ("ntfs", "ntfs3") and not mps:
                    out.append(n["path"])
                walk(n.get("children"))
        walk(data.get("blockdevices"))
        return out

    @staticmethod
    def _mount_readonly(dev: str) -> str | None:
        if not shutil.which("udisksctl"):
            return None
        try:
            res = subprocess.run(["udisksctl", "mount", "-b", dev, "-o", "ro", "--no-user-interaction"],
                                 capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None
        # "Mounted /dev/sda3 at /run/media/user/OS"
        if res.returncode == 0 and " at " in res.stdout:
            return res.stdout.strip().split(" at ", 1)[1].rstrip(".")
        return None

    @staticmethod
    def import_helper_available() -> bool:
        return paths.importer() is not None

    def _run_helper(self, args, what):
        helper = paths.importer()
        if self.demo:
            time.sleep(2.0)
            log.info("[demo] would run %s %s", helper or paths.IMPORT_HELPER, " ".join(args))
            return "ok"
        if helper is None:
            log.warning("%s is not installed", paths.IMPORT_HELPER)
            return "missing-helper"
        res = subprocess.run([sys.executable, helper, *args] if not os.access(helper, os.X_OK)
                             else [helper, *args], capture_output=True, text=True, timeout=900)
        log.info("%s: %s", what, res.stdout.strip())
        if res.returncode != 0:
            lines = (res.stdout + res.stderr).strip().splitlines()
            raise RuntimeError(lines[-1] if lines else f"import helper exited with {res.returncode}")
        return "ok"

    def reset_icon_theme(self):
        """Back to Fenestra's own icons (standalone --icons mode)."""
        if self.demo:
            log.info("[demo] would reset icon-theme to Fenestra")
            return
        s = _settings("org.gnome.desktop.interface")
        if s is not None:
            s.set_string("icon-theme", "Fenestra")
            Gio.Settings.sync()

    def run_import(self, root: str) -> str:
        """Import fonts/cursors/glyphs from a Windows partition mounted at ``root``."""
        return self._run_helper(["--windows", root], "windows import")

    def run_pack_import(self, zip_path: str) -> str:
        """Install an icon pack zip for the current user."""
        return self._run_helper(["--pack", zip_path], "icon pack import")

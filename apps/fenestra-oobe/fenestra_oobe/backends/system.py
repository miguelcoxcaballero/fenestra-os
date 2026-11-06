"""Accessibility toggles, volume (wpctl) and OOBE bookkeeping files."""

import json
import os
import re
import shutil
import subprocess

from gi.repository import Gio

from . import log
from .. import paths


def _settings(schema_id):
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(schema_id, True) is None:
        return None
    return Gio.Settings.new(schema_id)


A11Y = {
    "large-text": ("org.gnome.desktop.interface", "text-scaling-factor"),
    "high-contrast": ("org.gnome.desktop.a11y.interface", "high-contrast"),
    "screen-reader": ("org.gnome.desktop.a11y.applications", "screen-reader-enabled"),
    "screen-keyboard": ("org.gnome.desktop.a11y.applications", "screen-keyboard-enabled"),
}


class SystemBackend:
    def __init__(self, demo: bool):
        self.demo = demo
        self._demo_volume = 0.6

    # -- accessibility ---------------------------------------------------
    def get_a11y(self, key: str) -> bool:
        if self.demo:
            return False
        schema, k = A11Y[key]
        s = _settings(schema)
        if s is None:
            return False
        if key == "large-text":
            return s.get_double(k) > 1.05
        return s.get_boolean(k)

    def set_a11y(self, key: str, value: bool):
        if self.demo:
            log.info("[demo] a11y %s=%s (app only)", key, value)
            return
        schema, k = A11Y[key]
        s = _settings(schema)
        if s is None:
            return
        if key == "large-text":
            s.set_double(k, 1.25 if value else 1.0)
        else:
            s.set_boolean(k, value)

    # -- volume ----------------------------------------------------------
    def get_volume(self) -> float | None:
        if self.demo:
            return self._demo_volume
        if not shutil.which("wpctl"):
            return None
        try:
            out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True,
                                 text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        m = re.search(r"Volume:\s*([0-9.]+)", out)
        return float(m.group(1)) if m else None

    def set_volume(self, value: float):
        value = max(0.0, min(1.0, value))
        if self.demo:
            self._demo_volume = value
            return
        try:
            subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{value:.2f}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    # -- bookkeeping -----------------------------------------------------
    def save_user_choices(self, data: dict):
        path = paths.fenestra_state_file()
        if self.demo:
            log.info("[demo] would write %s: %s", path, data)
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        existing = {}
        try:
            with open(path, encoding="utf-8") as fh:
                existing = json.load(fh)
        except (OSError, ValueError):
            pass
        existing.update(data)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2, sort_keys=True)

    def mark_done(self):
        path = paths.done_file()
        if self.demo:
            log.info("[demo] would create %s", path)
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("yes")

    def write_handoff(self, data: dict):
        """System mode: leave region/keyboard choices for the user's first login."""
        path = os.path.join(os.path.expanduser("~"), paths.HANDOFF_RELPATH)
        if self.demo:
            log.info("[demo] would write handoff %s: %s", path, data)
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except OSError as exc:
            log.warning("could not write handoff file: %s", exc)

    @staticmethod
    def read_handoff() -> dict:
        """Existing-user mode: read the system-mode choices.

        GDM chowns the gnome-initial-setup home to the new user after the
        automatic login, so the file is readable from there.
        """
        import pwd
        # GDM >= 49 runs initial setup as a dynamic user whose home is
        # /run/gdm/gnome-initial-setup (same default as the copy worker).
        homes = ["/run/gdm/gnome-initial-setup", os.path.expanduser("~")]
        try:
            homes.insert(1, pwd.getpwnam("gnome-initial-setup").pw_dir)
        except KeyError:
            pass
        for home in homes:
            try:
                with open(os.path.join(home, paths.HANDOFF_RELPATH), encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                continue
        return {}

    def apply_user_region(self, formats: str, layouts: list):
        """Existing-user mode: per-user formats and input sources."""
        if self.demo:
            log.info("[demo] would set formats %s and input sources %s", formats, layouts)
            return
        if formats:
            s = _settings("org.gnome.system.locale")
            if s is not None and not s.get_string("region"):
                s.set_string("region", formats)
        if layouts:
            s = _settings("org.gnome.desktop.input-sources")
            if s is not None and not s.get_value("sources").unpack():
                from gi.repository import GLib
                src = [("xkb", f"{l}+{v}" if v else l) for l, v in layouts]
                s.set_value("sources", GLib.Variant("a(ss)", src))
            # The Fenestra session (KWin) reads its layouts from kxkbrc, not from gsettings.
            _write_kxkbrc(layouts)
        Gio.Settings.sync()

    def set_session_input_sources(self, layouts: list):
        """System mode: switch the running setup session to the chosen layouts
        so passwords are typed with the right keyboard."""
        if self.demo:
            log.info("[demo] would switch session keyboard to %s", layouts)
            return
        s = _settings("org.gnome.desktop.input-sources")
        if s is None:
            return
        from gi.repository import GLib
        src = [("xkb", f"{l}+{v}" if v else l) for l, v in layouts]
        s.set_value("sources", GLib.Variant("a(ss)", src))
        s.set_value("current", GLib.Variant("u", 0))
        Gio.Settings.sync()


def _write_kxkbrc(layouts: list) -> None:
    """~/.config/kxkbrc [Layout] for KWin, unless the user already has layouts there."""
    import os
    path = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "kxkbrc")
    try:
        if os.path.exists(path) and "LayoutList=" in open(path, encoding="utf-8").read():
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("[Layout]\nUse=true\n")
            f.write("LayoutList=" + ",".join(l for l, _v in layouts) + "\n")
            f.write("VariantList=" + ",".join(v or "" for _l, v in layouts) + "\n")
        os.replace(tmp, path)
    except OSError as e:
        log.warning("kxkbrc: %s", e)

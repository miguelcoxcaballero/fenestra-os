"""Device name through systemd-hostnamed (org.freedesktop.hostname1)."""

import random
import re
import socket
import string
import time

from gi.repository import GLib

from . import dbus, log

HOSTNAMED = "org.freedesktop.hostname1"
HOSTNAMED_PATH = "/org/freedesktop/hostname1"

MAX_LEN = 15
_ALLOWED = re.compile(r"^[A-Za-z0-9-]+$")


def validate_hostname(name: str) -> str | None:
    """Validate a device name using the same rules as the reference OOBE.

    Returns None when valid, otherwise one of: "empty", "spaces", "too-long",
    "invalid-chars", "only-numbers", "hyphen-edge".
    """
    if not name:
        return "empty"
    if " " in name or "\t" in name:
        return "spaces"
    if len(name) > MAX_LEN:
        return "too-long"
    if not _ALLOWED.match(name):
        return "invalid-chars"
    if name.isdigit():
        return "only-numbers"
    if name.startswith("-") or name.endswith("-"):
        return "hyphen-edge"
    return None


def suggest_hostname() -> str:
    suffix = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(7))
    return f"PC-{suffix}"


class HostnameBackend:
    def __init__(self, demo: bool):
        self.demo = demo

    def current(self) -> str:
        try:
            name = dbus.get_property(HOSTNAMED, HOSTNAMED_PATH, HOSTNAMED, "StaticHostname")
            if name:
                return name
        except GLib.Error:
            pass
        return socket.gethostname()

    def set_hostname(self, name: str):
        """Set the static hostname (lower-case) and keep the typed case as pretty name."""
        if self.demo:
            time.sleep(0.3)
            log.info("[demo] would set hostname %s", name)
            return
        dbus.call(HOSTNAMED, HOSTNAMED_PATH, HOSTNAMED, "SetStaticHostname",
                  GLib.Variant("(sb)", (name.lower(), True)))
        dbus.call(HOSTNAMED, HOSTNAMED_PATH, HOSTNAMED, "SetPrettyHostname",
                  GLib.Variant("(sb)", (name, True)))

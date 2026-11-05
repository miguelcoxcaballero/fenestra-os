"""System backends used by the OOBE.

Every backend takes a ``demo`` flag.  In demo mode nothing on the system is
changed: reads are allowed (so the UI shows realistic data) but writes are
simulated with a short delay.
"""

import logging
import threading
import traceback

from gi.repository import GLib

log = logging.getLogger("fenestra-oobe")


def run_async(func, *args, callback=None, **kwargs):
    """Run ``func`` in a worker thread; deliver ``callback(result, error)`` on
    the GLib main loop."""

    def worker():
        result, error = None, None
        try:
            result = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            log.warning("background task %s failed: %s", getattr(func, "__name__", func), exc)
            log.debug("%s", traceback.format_exc())
            error = exc
        if callback is not None:
            GLib.idle_add(lambda: (callback(result, error), False)[1])

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


class Backends:
    """Container that wires every backend with the same demo flag."""

    def __init__(self, demo: bool):
        from . import accounts, gdm, hostname, locale, network, privacy, system

        self.demo = demo
        self.accounts = accounts.AccountsBackend(demo)
        self.locale = locale.LocaleBackend(demo)
        self.hostname = hostname.HostnameBackend(demo)
        self.network = network.NetworkBackend(demo)
        self.gdm = gdm.GdmLogin(demo)
        self.privacy = privacy.PrivacyBackend(demo)
        self.system = system.SystemBackend(demo)

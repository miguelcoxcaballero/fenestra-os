#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Records every colour temperature KWin's Night light commits to the outputs
(org.kde.KWin.NightLight currentTemperature, announced on each 50 K step) with a timestamp,
plus the scene label the bench writes to /tmp/scene: TSV on stdout."""
import sys
import time

from gi.repository import Gio, GLib

t0 = time.monotonic()
bus = Gio.bus_get_sync(Gio.BusType.SESSION)


def scene():
    try:
        with open("/tmp/scene") as f:
            return f.read().strip()
    except OSError:
        return ""


def emit(kind, value):
    print(f"{time.monotonic() - t0:.3f}\t{kind}\t{value}\t{scene()}", flush=True)


def on_signal(_c, _s, _p, _i, _n, params):
    iface, changed, _inv = params.unpack()
    if iface != "org.kde.KWin.NightLight":
        return
    for k in ("currentTemperature", "running", "daylight", "inhibited"):
        if k in changed:
            emit(k, changed[k])


bus.signal_subscribe("org.kde.KWin", "org.freedesktop.DBus.Properties", "PropertiesChanged",
                     "/org/kde/KWin/NightLight", None, Gio.DBusSignalFlags.NONE, on_signal)
v = bus.call_sync("org.kde.KWin", "/org/kde/KWin/NightLight", "org.freedesktop.DBus.Properties", "Get",
                  GLib.Variant("(ss)", ("org.kde.KWin.NightLight", "currentTemperature")),
                  None, Gio.DBusCallFlags.NONE, 2000, None)
emit("currentTemperature", v.unpack()[0])
GLib.timeout_add_seconds(int(sys.argv[1]) if len(sys.argv) > 1 else 600, lambda: sys.exit(0))
GLib.MainLoop().run()

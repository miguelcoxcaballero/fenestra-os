"""BlueZ over D-Bus (ObjectManager), with bluetoothctl for discovery/pairing."""
from __future__ import annotations

from gi.repository import Gio, GLib

from .. import util

BLUEZ = "org.bluez"


class BtDevice:
    def __init__(self, path, props):
        self.path = path
        self.address = props.get("Address", "")
        self.name = props.get("Alias") or props.get("Name") or self.address
        self.paired = bool(props.get("Paired"))
        self.connected = bool(props.get("Connected"))
        self.icon = props.get("Icon", "")
        self.battery = None

    @property
    def kind_icon(self):
        i = self.icon
        if "audio" in i or "head" in i:
            return "fs-headphones-symbolic"
        if "phone" in i:
            return "fs-phone-symbolic"
        if "keyboard" in i:
            return "fs-keyboard-symbolic"
        if "mouse" in i or "input" in i:
            return "fs-cursor-symbolic"
        if "computer" in i:
            return "fs-laptop-symbolic"
        if "game" in i:
            return "fs-games-symbolic"
        return "fs-bluetooth-symbolic"


def state(callback):
    """callback(adapter_path or None, powered: bool, devices: [BtDevice])"""
    if util.DEMO:
        from . import demo
        demo.later(callback, *demo.bluetooth())
        return
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except GLib.Error:
        GLib.idle_add(lambda: (callback(None, False, []), False)[1])
        return

    def done(conn, res):
        try:
            objs = conn.call_finish(res).unpack()[0]
        except GLib.Error:
            callback(None, False, [])
            return
        adapter, powered, devs = None, False, []
        for path, ifaces in objs.items():
            if "org.bluez.Adapter1" in ifaces and adapter is None:
                adapter = path
                powered = bool(ifaces["org.bluez.Adapter1"].get("Powered"))
            if "org.bluez.Device1" in ifaces:
                d = BtDevice(path, ifaces["org.bluez.Device1"])
                if "org.bluez.Battery1" in ifaces:
                    d.battery = ifaces["org.bluez.Battery1"].get("Percentage")
                devs.append(d)
        devs.sort(key=lambda d: (not d.connected, not d.paired, d.name.lower()))
        callback(adapter, powered, devs)
    bus.call(BLUEZ, "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None, None,
             Gio.DBusCallFlags.NONE, 3000, None, done)


def set_powered(adapter, on, callback=None):
    if adapter:
        util.dbus_set_prop(Gio.BusType.SYSTEM, BLUEZ, adapter, "org.bluez.Adapter1", "Powered",
                           GLib.Variant("b", on), callback)
    else:
        util.run_async(["bluetoothctl", "power", "on" if on else "off"], callback, mutating=True)


def connect(dev: BtDevice, callback=None):
    util.dbus_call(Gio.BusType.SYSTEM, BLUEZ, dev.path, "org.bluez.Device1", "Connect", None, callback)


def disconnect(dev: BtDevice, callback=None):
    util.dbus_call(Gio.BusType.SYSTEM, BLUEZ, dev.path, "org.bluez.Device1", "Disconnect", None, callback)


def pair(dev: BtDevice, callback=None):
    util.run_async(["bluetoothctl", "--timeout", "30", "pair", dev.address], callback, mutating=True)


def remove(adapter, dev: BtDevice, callback=None):
    util.dbus_call(Gio.BusType.SYSTEM, BLUEZ, adapter, "org.bluez.Adapter1", "RemoveDevice",
                   GLib.Variant("(o)", (dev.path,)), callback)


def scan(seconds, callback=None):
    """Discover for a few seconds (bluetoothctl handles the discovery session)."""
    util.run_async(["bluetoothctl", "--timeout", str(seconds), "scan", "on"], callback, mutating=True)

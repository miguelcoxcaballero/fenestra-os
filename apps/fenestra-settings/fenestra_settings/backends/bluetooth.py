"""BlueZ over D-Bus (ObjectManager); bluetoothctl for the timed discovery."""
from __future__ import annotations

from gi.repository import Gio, GLib

from .. import util

BLUEZ = "org.bluez"


class BtDevice:
    def __init__(self, path, props):
        self.path = path
        self.address = props.get("Address", "")
        self.name = props.get("Alias") or props.get("Name") or self.address
        self.named = bool(props.get("Name"))   # nameless BLE beacons are not offered, as in Windows
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


AGENT_PATH = "/org/fenestra/settings/btagent"
AGENT_XML = """<node><interface name="org.bluez.Agent1">
  <method name="Release"/>
  <method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
  <method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
  <method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
  <method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
  <method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
  <method name="RequestAuthorization"><arg type="o" direction="in"/></method>
  <method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
  <method name="Cancel"/>
</interface></node>"""


class _Pairing:
    """Pair, trust and connect one device, as Windows' "Add a device" does in one go.

    Discovery stays on while pairing: BlueZ drops a device it has not seen for 30 s, so a
    controller found by the earlier search was often gone by the time Pair was pressed (Xbox
    Wireless Controller: nothing happened). A device must also be trusted and connected after
    pairing, or controllers and headsets drop off straight away. An agent answers "just works"
    confirmations (controllers, headsets, mice) for the length of the pairing.
    """

    def __init__(self, dev: BtDevice, callback):
        self.dev, self.callback = dev, callback
        self.adapter = dev.path.rsplit("/", 1)[0]
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.agent_id = 0
        self.discovering = False
        self.finished = False
        self.attempt = 0

    # ---- agent: accept the pairing the user asked for
    def _agent_call(self, conn, sender, path, iface, method, params, inv):
        if method == "RequestPinCode":
            inv.return_value(GLib.Variant("(s)", ("0000",)))
        elif method == "RequestPasskey":
            inv.return_value(GLib.Variant("(u)", (0,)))
        else:
            inv.return_value(None)

    def start(self):
        try:
            node = Gio.DBusNodeInfo.new_for_xml(AGENT_XML)
            self.agent_id = self.bus.register_object(AGENT_PATH, node.interfaces[0], self._agent_call, None, None)
            self._call("/org/bluez", "org.bluez.AgentManager1", "RegisterAgent",
                       GLib.Variant("(os)", (AGENT_PATH, "KeyboardDisplay")), lambda ok, r: self._discover())
        except GLib.Error as e:
            util.log("bluetooth agent", e.message)
            self._discover()

    def _call(self, path, iface, method, args, done, timeout=30000):
        def fin(conn, res):
            try:
                r = conn.call_finish(res)
                done(True, r)
            except GLib.Error as e:
                done(False, e)
        self.bus.call(BLUEZ, path, iface, method, args, None, Gio.DBusCallFlags.NONE, timeout, None, fin)

    def _discover(self):
        def started(ok, r):
            self.discovering = ok
            self._wait_for_device(0)
        self._call(self.adapter, "org.bluez.Adapter1", "StartDiscovery", None, started)

    def _wait_for_device(self, tries):
        # the device object comes back once discovery sees it again (it must be in pairing mode)
        def got(ok, r):
            if ok:
                self._pair(self.attempt)
            elif tries < 20:
                GLib.timeout_add(1000, lambda: (self._wait_for_device(tries + 1), False)[1])
            else:
                self._finish(False, "device not found: is it still in pairing mode?")
        self._call(self.dev.path, "org.freedesktop.DBus.Properties", "Get",
                   GLib.Variant("(ss)", ("org.bluez.Device1", "Address")), got, 2000)

    def _pair(self, attempt):
        def paired(ok, r):
            if not ok and "AlreadyExists" not in str(r):
                # a controller that has just appeared sometimes fails the first attempt
                # (page timeout, connection attempt failed): one more try
                util.log("bluetooth pair attempt", attempt + 1, str(r))
                if attempt < 1 and "AuthenticationRejected" not in str(r):
                    # a failed attempt can make BlueZ forget the device: wait to see it again
                    self.attempt = attempt + 1
                    GLib.timeout_add(1500, lambda: (self._wait_for_device(0), False)[1])
                    return
                self._finish(False, str(r))
                return
            self._call(self.dev.path, "org.freedesktop.DBus.Properties", "Set",
                       GLib.Variant("(ssv)", ("org.bluez.Device1", "Trusted", GLib.Variant("b", True))),
                       lambda ok, r: self._connect(0))
        self._call(self.dev.path, "org.bluez.Device1", "Pair", None, paired, 60000)

    def _connect(self, attempt):
        def connected(ok, r):
            # HID devices (controllers, keyboards) often connect themselves right after pairing,
            # and Connect then fails with "In Progress" or "AlreadyConnected"
            if ok or any(k in str(r) for k in ("AlreadyConnected", "InProgress", "In Progress")):
                self._finish(True, "")
            elif attempt < 2:
                GLib.timeout_add(2000, lambda: (self._connect(attempt + 1), False)[1])
            else:
                self._finish(True, "paired; connect: " + str(r))   # paired and trusted: it reconnects
        self._call(self.dev.path, "org.bluez.Device1", "Connect", None, connected, 30000)

    def _finish(self, ok, err):
        if self.finished:
            return
        self.finished = True
        if self.discovering:
            self._call(self.adapter, "org.bluez.Adapter1", "StopDiscovery", None, lambda *a: None)
        if self.agent_id:
            self._call("/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent",
                       GLib.Variant("(o)", (AGENT_PATH,)), lambda *a: None)
            self.bus.unregister_object(self.agent_id)
            self.agent_id = 0
        util.log("bluetooth pair", self.dev.address, "ok" if ok else "failed", err)
        if self.callback:
            self.callback(ok, "", err)


def pair(dev: BtDevice, callback=None):
    if util._blocked("dbus", f"org.bluez Device1.Pair {dev.address}"):
        if callback:
            GLib.idle_add(lambda: (callback(False, "", "read-only mode"), False)[1])
        return
    _Pairing(dev, callback).start()


def remove(adapter, dev: BtDevice, callback=None):
    util.dbus_call(Gio.BusType.SYSTEM, BLUEZ, adapter, "org.bluez.Adapter1", "RemoveDevice",
                   GLib.Variant("(o)", (dev.path,)), callback)


def scan(seconds, callback=None):
    """Discover for a few seconds (bluetoothctl handles the discovery session)."""
    util.run_async(["bluetoothctl", "--timeout", str(seconds), "scan", "on"], callback, mutating=True)

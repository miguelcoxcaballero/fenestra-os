#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A small, scriptable NetworkManager for tests (libnm-compatible).

Runs on whatever bus DBUS_SYSTEM_BUS_ADDRESS points to. NEVER run it on the real system
bus: it refuses unless the address is a private socket given by the caller.

    dbus-daemon --session --address=unix:path=$DIR/sys --nofork &
    DBUS_SYSTEM_BUS_ADDRESS=unix:path=$DIR/sys python3 tests/mock_networkmanager.py

It implements what libnm's NMClient needs (ObjectManager at /org/freedesktop, the manager,
settings, settings connections, a Wi-Fi device, access points, active connections and
IP4Config) and simulates activation the way NetworkManager 1.5x does with no secret agent:

* correct key        prepare → config → ip-config → activated
* wrong / no key     prepare → config → need-auth → failed (no-secrets), the profile stays
* out of range       failed (ssid-not-found)
* new activation     the previous one is deactivated (reason new-activation)

Scenario: the access points below; their keys live in AP_KEYS. The private interface
org.fenestra.MockNM (same path as the manager) lets a test add/remove access points,
change signal strength, make activation slow and read a call log.
"""
from __future__ import annotations

import os
import sys
import uuid as uuidlib

from gi.repository import Gio, GLib

if "DBUS_SYSTEM_BUS_ADDRESS" not in os.environ or "/run/dbus" in os.environ["DBUS_SYSTEM_BUS_ADDRESS"]:
    sys.exit("refusing to run: set DBUS_SYSTEM_BUS_ADDRESS to a private test bus")

NM = "org.freedesktop.NetworkManager"
P = "/org/freedesktop/NetworkManager"

# security flags
PSK, EAP, SAE = 0x100, 0x200, 0x400
CCMP = 0x8 | 0x80
PRIVACY = 0x1

# name, strength, flags, wpa, rsn, freq, hidden-ssid-for-hidden-AP
APS = [
    ("HomeNetwork", 82, PRIVACY, 0, PSK | CCMP, 5180),
    ("HomeNetwork", 40, PRIVACY, 0, PSK | CCMP, 2437),
    ("Office-5G", 64, PRIVACY, 0, PSK | SAE | CCMP, 5500),
    ("Cafe-Guest", 48, 0, 0, 0, 2412),
    ("WPA3-Only", 55, PRIVACY, 0, SAE | CCMP, 5745),
    ("Campus", 51, PRIVACY, 0, EAP | CCMP, 5240),
    ("Old-WEP", 22, PRIVACY, 0, 0, 2462),
    ("", 45, PRIVACY, 0, PSK | CCMP, 2462),          # hidden network "Secret-Lab"
    ("Ca:fé \"quoted\"", 30, PRIVACY, 0, PSK | CCMP, 2412),
]
HIDDEN = {"": "Secret-Lab"}
AP_KEYS = {"HomeNetwork": "correct-horse", "Office-5G": "office-pass", "WPA3-Only": "sae-password",
           "Secret-Lab": "lab-password", "Old-WEP": "abcde", "Ca:fé \"quoted\"": "unicode-pass",
           "Campus": ("student", "campus-pass")}

IFACES = {
    "org.freedesktop.NetworkManager": {
        "props": {"Devices": "ao", "AllDevices": "ao", "Checkpoints": "ao", "NetworkingEnabled": "b",
                  "WirelessEnabled": "b", "WirelessHardwareEnabled": "b", "WwanEnabled": "b",
                  "WwanHardwareEnabled": "b", "ActiveConnections": "ao", "PrimaryConnection": "o",
                  "PrimaryConnectionType": "s", "Metered": "u", "ActivatingConnection": "o",
                  "Startup": "b", "Version": "s", "VersionInfo": "au", "Capabilities": "au", "State": "u",
                  "Connectivity": "u", "ConnectivityCheckAvailable": "b", "ConnectivityCheckEnabled": "b",
                  "ConnectivityCheckUri": "s", "GlobalDnsConfiguration": "a{sv}", "RadioFlags": "u"},
        "methods": {"GetDevices": ("", "ao"), "GetAllDevices": ("", "ao"),
                    "ActivateConnection": ("ooo", "o"),
                    "AddAndActivateConnection": ("a{sa{sv}}oo", "oo"),
                    "AddAndActivateConnection2": ("a{sa{sv}}ooa{sv}", "ooa{sv}"),
                    "DeactivateConnection": ("o", ""), "Enable": ("b", ""), "Sleep": ("b", ""),
                    "GetPermissions": ("", "a{ss}"), "CheckConnectivity": ("", "u"), "state": ("", "u"),
                    "GetDeviceByIpIface": ("s", "o")},
        "signals": {"CheckPermissions": "", "StateChanged": "u", "DeviceAdded": "o", "DeviceRemoved": "o"},
    },
    "org.freedesktop.NetworkManager.Settings": {
        "props": {"Connections": "ao", "Hostname": "s", "CanModify": "b", "VersionId": "t"},
        "methods": {"ListConnections": ("", "ao"), "GetConnectionByUuid": ("s", "o"),
                    "AddConnection": ("a{sa{sv}}", "o"), "AddConnectionUnsaved": ("a{sa{sv}}", "o"),
                    "AddConnection2": ("a{sa{sv}}ua{sv}", "oa{sv}"), "ReloadConnections": ("", "b")},
        "signals": {"NewConnection": "o", "ConnectionRemoved": "o"},
    },
    "org.freedesktop.NetworkManager.Settings.Connection": {
        "props": {"Unsaved": "b", "Flags": "u", "Filename": "s", "VersionId": "t"},
        "methods": {"Update": ("a{sa{sv}}", ""), "UpdateUnsaved": ("a{sa{sv}}", ""), "Delete": ("", ""),
                    "GetSettings": ("", "a{sa{sv}}"), "GetSecrets": ("s", "a{sa{sv}}"),
                    "ClearSecrets": ("", ""), "Save": ("", ""), "Update2": ("a{sa{sv}}ua{sv}", "a{sv}")},
        "signals": {"Updated": "", "Removed": ""},
    },
    "org.freedesktop.NetworkManager.Device": {
        "props": {"Udi": "s", "Path": "s", "Interface": "s", "IpInterface": "s", "Driver": "s",
                  "DriverVersion": "s", "FirmwareVersion": "s", "Capabilities": "u", "State": "u",
                  "StateReason": "(uu)", "ActiveConnection": "o", "Ip4Config": "o", "Dhcp4Config": "o",
                  "Ip6Config": "o", "Dhcp6Config": "o", "Managed": "b", "Autoconnect": "b",
                  "FirmwareMissing": "b", "NmPluginMissing": "b", "DeviceType": "u",
                  "AvailableConnections": "ao", "PhysicalPortId": "s", "Mtu": "u", "Metered": "u",
                  "Real": "b", "Ip4Connectivity": "u", "Ip6Connectivity": "u", "InterfaceFlags": "u",
                  "HwAddress": "s", "Ports": "ao"},
        "methods": {"Disconnect": ("", ""), "Delete": ("", "")},
        "signals": {"StateChanged": "uuu"},
    },
    "org.freedesktop.NetworkManager.Device.Wireless": {
        "props": {"HwAddress": "s", "PermHwAddress": "s", "Mode": "u", "Bitrate": "u",
                  "AccessPoints": "ao", "ActiveAccessPoint": "o", "WirelessCapabilities": "u",
                  "LastScan": "x"},
        "methods": {"GetAccessPoints": ("", "ao"), "GetAllAccessPoints": ("", "ao"),
                    "RequestScan": ("a{sv}", "")},
        "signals": {"AccessPointAdded": "o", "AccessPointRemoved": "o"},
    },
    "org.freedesktop.NetworkManager.AccessPoint": {
        "props": {"Flags": "u", "WpaFlags": "u", "RsnFlags": "u", "Ssid": "ay", "Frequency": "u",
                  "HwAddress": "s", "Mode": "u", "MaxBitrate": "u", "Bandwidth": "u", "Strength": "y",
                  "LastSeen": "i"},
        "methods": {}, "signals": {},
    },
    "org.freedesktop.NetworkManager.Connection.Active": {
        "props": {"Connection": "o", "SpecificObject": "o", "Id": "s", "Uuid": "s", "Type": "s",
                  "Devices": "ao", "State": "u", "StateFlags": "u", "Default": "b", "Ip4Config": "o",
                  "Dhcp4Config": "o", "Default6": "b", "Ip6Config": "o", "Dhcp6Config": "o", "Vpn": "b",
                  "Controller": "o", "Master": "o"},
        "methods": {}, "signals": {"StateChanged": "uu"},
    },
    "org.freedesktop.NetworkManager.IP4Config": {
        "props": {"AddressData": "aa{sv}", "Gateway": "s", "NameserverData": "aa{sv}", "Domains": "as",
                  "Searches": "as", "DnsOptions": "as", "DnsPriority": "i", "RouteData": "aa{sv}",
                  "WinsServerData": "as"},
        "methods": {}, "signals": {},
    },
    "org.fenestra.MockNM": {
        "props": {},
        "methods": {"SetStrength": ("si", ""), "RemoveNetwork": ("s", ""),
                    "AddNetwork": ("siuuu", ""), "SetDelay": ("u", ""), "Log": ("", "as"),
                    "Reset": ("", "")},
        "signals": {},
    },
}


def _xml(name):
    d = IFACES[name]
    out = [f'<interface name="{name}">']
    for p, s in d["props"].items():
        acc = "readwrite" if p == "WirelessEnabled" else "read"
        out.append(f'<property name="{p}" type="{s}" access="{acc}"/>')
    for m, (i, o) in d["methods"].items():
        out.append(f'<method name="{m}">')
        for n, sig in enumerate(_split_sig(i)):
            out.append(f'<arg direction="in" type="{sig}" name="a{n}"/>')
        for n, sig in enumerate(_split_sig(o)):
            out.append(f'<arg direction="out" type="{sig}" name="r{n}"/>')
        out.append("</method>")
    for sname, sig in d["signals"].items():
        out.append(f'<signal name="{sname}">')
        for n, s in enumerate(_split_sig(sig)):
            out.append(f'<arg type="{s}" name="a{n}"/>')
        out.append("</signal>")
    out.append("</interface>")
    return "".join(out)


def _split_sig(sig):
    return GLib.Variant.split_signature(f"({sig})") if sig else []

NODE = Gio.DBusNodeInfo.new_for_xml(
    "<node>" + "".join(_xml(n) for n in IFACES) +
    '<interface name="org.freedesktop.DBus.ObjectManager"><method name="GetManagedObjects">'
    '<arg direction="out" type="a{oa{sa{sv}}}" name="r"/></method>'
    '<signal name="InterfacesAdded"><arg type="o"/><arg type="a{sa{sv}}"/></signal>'
    '<signal name="InterfacesRemoved"><arg type="o"/><arg type="as"/></signal></interface></node>')


def iface_info(name):
    return NODE.lookup_interface(name)


class DBusError(Exception):
    def __init__(self, name, msg):
        super().__init__(msg)
        self.name, self.msg = name, msg


class Obj:
    def __init__(self, srv, path, ifaces: dict[str, dict]):
        self.srv, self.path, self.props, self.reg = srv, path, ifaces, []

    def v(self, iface, prop):
        return GLib.Variant(IFACES[iface]["props"][prop], self.props[iface][prop])

    def all_props(self, iface):
        return {k: self.v(iface, k) for k in self.props[iface]}

    def set(self, iface, **kw):
        changed = {}
        for k, val in kw.items():
            if self.props[iface].get(k) != val:
                self.props[iface][k] = val
                changed[k] = self.v(iface, k)
        if changed and self.reg:
            self.srv.bus.emit_signal(None, self.path, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                                     GLib.Variant("(sa{sv}as)", (iface, changed, [])))

    def emit(self, iface, name, *args):
        sig = IFACES[iface]["signals"][name]
        self.srv.bus.emit_signal(None, self.path, iface, name, GLib.Variant(f"({sig})", args) if sig else None)


def _unpack_settings(v):
    return v.unpack() if isinstance(v, GLib.Variant) else v


SETTING_SIGS = {
    "connection": {"id": "s", "uuid": "s", "type": "s", "autoconnect": "b", "timestamp": "t",
                   "metered": "i", "interface-name": "s", "permissions": "as", "autoconnect-priority": "i"},
    "802-11-wireless": {"ssid": "ay", "mode": "s", "hidden": "b", "seen-bssids": "as",
                        "cloned-mac-address": "s", "band": "s", "mac-address-randomization": "u"},
    "802-11-wireless-security": {"key-mgmt": "s", "psk": "s", "wep-key0": "s", "wep-key-type": "u",
                                 "auth-alg": "s", "psk-flags": "u", "wep-key-flags": "u",
                                 "wep-tx-keyidx": "u", "pmf": "i"},
    "802-1x": {"eap": "as", "identity": "s", "password": "s", "phase2-auth": "s",
               "anonymous-identity": "s", "domain-suffix-match": "s", "password-flags": "u",
               "system-ca-certs": "b"},
    "ipv4": {"method": "s", "address-data": "aa{sv}", "gateway": "s", "dns": "au", "ignore-auto-dns": "b",
             "dns-search": "as"},
    "ipv6": {"method": "s", "addr-gen-mode": "i", "ip6-privacy": "i", "address-data": "aa{sv}",
             "dns": "aay"},
    "proxy": {},
}
SECRETS = {"802-11-wireless-security": ("psk", "wep-key0"), "802-1x": ("password",)}


def _pack_settings(d, secrets=False):
    out = {}
    for sname, vals in d.items():
        sig = SETTING_SIGS.get(sname, {})
        sec = {}
        for k, val in vals.items():
            if k in SECRETS.get(sname, ()) and not secrets:
                continue
            t = sig.get(k)
            if t is None:
                continue
            if t == "ay" and isinstance(val, str):
                val = val.encode()
            sec[k] = GLib.Variant(t, val)
        out[sname] = sec
    return GLib.Variant("a{sa{sv}}", out)


def _secrets_only(d, setting):
    vals = d.get(setting, {})
    return GLib.Variant("a{sa{sv}}", {setting: {k: GLib.Variant("s", vals[k]) for k in SECRETS.get(setting, ())
                                                if k in vals}})


class MockNM:
    def __init__(self, bus):
        self.bus = bus
        self.objs: dict[str, Obj] = {}
        self.counter = 0
        self.log: list[str] = []
        self.delay = 400  # ms per activation stage
        self.timers = []

    # ------------------------------------------------------------ object registry
    def path(self, kind):
        self.counter += 1
        return f"{P}/{kind}/{self.counter}"

    def add(self, path, ifaces, announce=True):
        o = Obj(self, path, ifaces)
        self.objs[path] = o
        for name in ifaces:
            rid = self.bus.register_object(path, iface_info(name), self._call, self._get, self._set)
            o.reg.append(rid)
        if announce:
            self.bus.emit_signal(None, "/org/freedesktop", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded",
                                 GLib.Variant("(oa{sa{sv}})", (path, {i: o.all_props(i) for i in ifaces
                                                                       if i != "org.fenestra.MockNM"})))
        return o

    def remove(self, path):
        o = self.objs.pop(path, None)
        if not o:
            return
        for rid in o.reg:
            self.bus.unregister_object(rid)
        self.bus.emit_signal(None, "/org/freedesktop", "org.freedesktop.DBus.ObjectManager", "InterfacesRemoved",
                             GLib.Variant("(oas)", (path, list(o.props))))

    def _get(self, _conn, _sender, path, iface, prop):
        o = self.objs.get(path)
        return o.v(iface, prop) if o and prop in o.props.get(iface, {}) else None

    def _set(self, _conn, _sender, path, iface, prop, value):
        if path == P and prop == "WirelessEnabled":
            self.set_wireless(value.unpack())
            return True
        return False

    def managed_objects(self):
        return GLib.Variant("(a{oa{sa{sv}}})", ({p: {i: o.all_props(i) for i in o.props if i != "org.fenestra.MockNM"}
                                                for p, o in self.objs.items()},))

    # ------------------------------------------------------------ setup
    def setup(self):
        self.mgr = self.add(P, {
            "org.freedesktop.NetworkManager": {
                "Devices": [], "AllDevices": [], "Checkpoints": [], "NetworkingEnabled": True,
                "WirelessEnabled": True, "WirelessHardwareEnabled": True, "WwanEnabled": False,
                "WwanHardwareEnabled": False, "ActiveConnections": [], "PrimaryConnection": "/",
                "PrimaryConnectionType": "", "Metered": 0, "ActivatingConnection": "/", "Startup": False,
                "Version": "1.58.1", "VersionInfo": [0x013a01, 0], "Capabilities": [], "State": 20,
                "Connectivity": 1, "ConnectivityCheckAvailable": False, "ConnectivityCheckEnabled": False,
                "ConnectivityCheckUri": "", "GlobalDnsConfiguration": {}, "RadioFlags": 1},
            "org.fenestra.MockNM": {}}, announce=False)
        self.settings = self.add(f"{P}/Settings", {"org.freedesktop.NetworkManager.Settings": {
            "Connections": [], "Hostname": "mock", "CanModify": True, "VersionId": 1}}, announce=False)
        self.ip4 = self.add(f"{P}/IP4Config/1", {"org.freedesktop.NetworkManager.IP4Config": {
            "AddressData": [{"address": GLib.Variant("s", "192.168.1.23"), "prefix": GLib.Variant("u", 24)}],
            "Gateway": "192.168.1.1",
            "NameserverData": [{"address": GLib.Variant("s", "192.168.1.1")}],
            "Domains": [], "Searches": [], "DnsOptions": [], "DnsPriority": 0, "RouteData": [],
            "WinsServerData": []}}, announce=False)
        self.dev = self.add(f"{P}/Devices/1", {
            "org.freedesktop.NetworkManager.Device": {
                "Udi": "/sys/devices/wlan0", "Path": "", "Interface": "wlan0", "IpInterface": "",
                "Driver": "iwlwifi", "DriverVersion": "6.17.1", "FirmwareVersion": "89.1", "Capabilities": 1,
                "State": 30, "StateReason": (30, 0), "ActiveConnection": "/", "Ip4Config": "/",
                "Dhcp4Config": "/", "Ip6Config": "/", "Dhcp6Config": "/", "Managed": True, "Autoconnect": True,
                "FirmwareMissing": False, "NmPluginMissing": False, "DeviceType": 2,
                "AvailableConnections": [], "PhysicalPortId": "", "Mtu": 1500, "Metered": 0, "Real": True,
                "Ip4Connectivity": 1, "Ip6Connectivity": 1, "InterfaceFlags": 1,
                "HwAddress": "00:11:22:33:44:55", "Ports": []},
            "org.freedesktop.NetworkManager.Device.Wireless": {
                "HwAddress": "00:11:22:33:44:55", "PermHwAddress": "00:11:22:33:44:55", "Mode": 2,
                "Bitrate": 0, "AccessPoints": [], "ActiveAccessPoint": "/", "WirelessCapabilities": 0x7ff,
                "LastScan": 1000}}, announce=False)
        self.mgr.props[NM]["Devices"] = [self.dev.path]
        self.mgr.props[NM]["AllDevices"] = [self.dev.path]
        for i, ap in enumerate(APS):
            self.add_ap(*ap, bssid=f"02:00:00:00:00:{i:02x}", announce=False)
        # one saved profile: HomeNetwork (right key), Old-Office (out of range)
        self.add_conn(self._wifi_settings("HomeNetwork", "wpa-psk", "correct-horse"), announce=False)
        self.add_conn(self._wifi_settings("Old-Office", "wpa-psk", "whatever"), announce=False)
        self.add_conn(self._wifi_settings("Library", None, None), announce=False)

    def _wifi_settings(self, ssid, key_mgmt, key, autoconnect=True):
        s = {"connection": {"id": ssid, "uuid": str(uuidlib.uuid4()), "type": "802-11-wireless",
                            "autoconnect": autoconnect, "timestamp": 1790000000},
             "802-11-wireless": {"ssid": ssid.encode(), "mode": "infrastructure"},
             "ipv4": {"method": "auto"}, "ipv6": {"method": "auto"}}
        if key_mgmt:
            s["802-11-wireless-security"] = {"key-mgmt": key_mgmt, "psk": key}
        return s

    def add_ap(self, ssid, strength, flags, wpa, rsn, freq, bssid=None, announce=True):
        path = self.path("AccessPoint")
        self.add(path, {"org.freedesktop.NetworkManager.AccessPoint": {
            "Flags": flags, "WpaFlags": wpa, "RsnFlags": rsn, "Ssid": list(ssid.encode()), "Frequency": freq,
            "HwAddress": bssid or "02:00:00:00:01:%02x" % (self.counter % 256), "Mode": 2,
            "MaxBitrate": 866000 if freq > 5000 else 144000, "Bandwidth": 80 if freq > 5000 else 20,
            "Strength": strength, "LastSeen": 100}}, announce=announce)
        w = self.dev.props["org.freedesktop.NetworkManager.Device.Wireless"]
        if announce:
            self.dev.set("org.freedesktop.NetworkManager.Device.Wireless",
                         AccessPoints=w["AccessPoints"] + [path])
            self.dev.emit("org.freedesktop.NetworkManager.Device.Wireless", "AccessPointAdded", path)
        else:
            w["AccessPoints"].append(path)
        return path

    def add_conn(self, settings, announce=True):
        path = self.path("Settings")
        o = self.add(path, {"org.freedesktop.NetworkManager.Settings.Connection": {
            "Unsaved": False, "Flags": 0, "Filename": f"/etc/NetworkManager/system-connections/{path[-2:]}",
            "VersionId": 1}}, announce=announce)
        o.data = settings
        conns = self.settings.props["org.freedesktop.NetworkManager.Settings"]["Connections"]
        if announce:
            self.settings.set("org.freedesktop.NetworkManager.Settings", Connections=conns + [path])
            self.settings.emit("org.freedesktop.NetworkManager.Settings", "NewConnection", path)
        else:
            conns.append(path)
        return o

    # ------------------------------------------------------------ helpers
    def ap_ssid(self, path):
        o = self.objs.get(path)
        if not o:
            return None
        raw = bytes(o.props["org.freedesktop.NetworkManager.AccessPoint"]["Ssid"]).decode("utf-8", "replace")
        return raw

    def aps(self):
        return self.dev.props["org.freedesktop.NetworkManager.Device.Wireless"]["AccessPoints"]

    def find_ap(self, ssid, hidden=False):
        best = None
        for p in self.aps():
            s = self.ap_ssid(p)
            match = s == ssid or (hidden and s == "" and HIDDEN.get("") == ssid)
            if match:
                st = self.objs[p].props["org.freedesktop.NetworkManager.AccessPoint"]["Strength"]
                if best is None or st > best[1]:
                    best = (p, st)
        return best[0] if best else None

    def dev_state(self, state, reason=0):
        d = self.dev.props["org.freedesktop.NetworkManager.Device"]
        old = d["State"]
        if old == state:
            return
        self.dev.set("org.freedesktop.NetworkManager.Device", State=state, StateReason=(state, reason))
        self.dev.emit("org.freedesktop.NetworkManager.Device", "StateChanged", state, old, reason)
        self.log.append(f"device {old}->{state} reason {reason}")

    def later(self, ms, fn):
        def run():
            if tid in self.timers:
                self.timers.remove(tid)
            fn()
            return False
        tid = GLib.timeout_add(ms, run)
        self.timers.append(tid)

    def cancel_timers(self):
        for t in self.timers:
            GLib.source_remove(t)
        self.timers = []

    # ------------------------------------------------------------ activation
    def activate(self, conn_path, specific):
        conn = self.objs.get(conn_path)
        if conn is None:
            raise DBusError("org.freedesktop.NetworkManager.UnknownConnection", "Connection not found")
        if not self.mgr.props[NM]["WirelessEnabled"]:
            raise DBusError("org.freedesktop.NetworkManager.UnknownDevice", "Wi-Fi is disabled")
        cur = self.dev.props["org.freedesktop.NetworkManager.Device"]["ActiveConnection"]
        if cur != "/":
            self.deactivate(cur, reason=60, ac_reason=3, quiet=True)
        s = conn.data
        ssid = bytes(s["802-11-wireless"]["ssid"]).decode("utf-8", "replace")
        hidden = s["802-11-wireless"].get("hidden", False)
        ap = specific if specific not in ("", "/") else self.find_ap(ssid, hidden)
        ac_path = self.path("ActiveConnection")
        ac = self.add(ac_path, {"org.freedesktop.NetworkManager.Connection.Active": {
            "Connection": conn_path, "SpecificObject": ap or "/", "Id": s["connection"]["id"],
            "Uuid": s["connection"]["uuid"], "Type": "802-11-wireless", "Devices": [self.dev.path], "State": 1,
            "StateFlags": 0, "Default": False, "Ip4Config": "/", "Dhcp4Config": "/", "Default6": False,
            "Ip6Config": "/", "Dhcp6Config": "/", "Vpn": False, "Controller": "/", "Master": "/"}})
        self.mgr.set(NM, ActiveConnections=self.mgr.props[NM]["ActiveConnections"] + [ac_path],
                     ActivatingConnection=ac_path, State=40)
        self.dev.set("org.freedesktop.NetworkManager.Device", ActiveConnection=ac_path)
        self.dev_state(40)
        self.log.append(f"activate {ssid}")
        d = self.delay

        def fail(reason, ac_reason):
            self.dev_state(120, reason)
            self._drop_ac(ac_path, ac_reason)
            self.later(50, lambda: self.dev_state(30, 0))

        if ap is None:
            self.later(d, lambda: fail(53, 1))
            return ac_path
        self.later(d, lambda: self.dev_state(50))
        want = AP_KEYS.get(ssid)
        sec = s.get("802-11-wireless-security", {})
        x = s.get("802-1x", {})
        if want is None:
            ok = True
        elif isinstance(want, tuple):
            ok = (x.get("identity"), x.get("password")) == want
        else:
            ok = want in (sec.get("psk"), sec.get("wep-key0"))
        if not ok:
            # need-auth while NetworkManager asks for new secrets; nobody answers
            self.later(2 * d, lambda: self.dev_state(60))
            self.later(3 * d, lambda: fail(7, 9))
            return ac_path

        def ip():
            self.dev_state(70)

        def done():
            self.dev.set("org.freedesktop.NetworkManager.Device", Ip4Config=self.ip4.path)
            self.dev.set("org.freedesktop.NetworkManager.Device.Wireless", ActiveAccessPoint=ap, Bitrate=866000)
            ac.set("org.freedesktop.NetworkManager.Connection.Active", State=2, Ip4Config=self.ip4.path,
                   Default=True)
            ac.emit("org.freedesktop.NetworkManager.Connection.Active", "StateChanged", 2, 1)
            self.dev_state(100)
            self.mgr.set(NM, PrimaryConnection=ac_path, PrimaryConnectionType="802-11-wireless",
                         ActivatingConnection="/", State=70, Connectivity=4)
        self.later(2 * d, ip)
        self.later(3 * d, done)
        return ac_path

    def _drop_ac(self, ac_path, ac_reason):
        ac = self.objs.get(ac_path)
        if ac is None:
            return
        ac.set("org.freedesktop.NetworkManager.Connection.Active", State=4)
        ac.emit("org.freedesktop.NetworkManager.Connection.Active", "StateChanged", 4, ac_reason)
        acs = [a for a in self.mgr.props[NM]["ActiveConnections"] if a != ac_path]
        mgr = {"ActiveConnections": acs, "State": 70 if acs else 20}
        if self.mgr.props[NM]["PrimaryConnection"] == ac_path:
            mgr.update(PrimaryConnection="/", PrimaryConnectionType="")
        if self.mgr.props[NM]["ActivatingConnection"] == ac_path:
            mgr["ActivatingConnection"] = "/"
        self.mgr.set(NM, **mgr)
        if self.dev.props["org.freedesktop.NetworkManager.Device"]["ActiveConnection"] == ac_path:
            self.dev.set("org.freedesktop.NetworkManager.Device", ActiveConnection="/", Ip4Config="/")
            self.dev.set("org.freedesktop.NetworkManager.Device.Wireless", ActiveAccessPoint="/", Bitrate=0)
        self.remove(ac_path)

    def deactivate(self, ac_path, reason=39, ac_reason=2, quiet=False):
        if ac_path not in self.objs:
            raise DBusError("org.freedesktop.NetworkManager.ConnectionNotActive", "Not active")
        self.cancel_timers()
        self.log.append(f"deactivate {ac_path}")
        self.dev_state(110, reason)
        self._drop_ac(ac_path, ac_reason)
        if quiet:
            self.dev_state(30, reason)
        else:
            self.later(50, lambda: self.dev_state(30, reason))

    def set_wireless(self, on):
        self.log.append(f"wireless {on}")
        if not on:
            cur = self.dev.props["org.freedesktop.NetworkManager.Device"]["ActiveConnection"]
            if cur != "/":
                self.deactivate(cur, reason=36, quiet=True)
            self.dev_state(20, 0)
        else:
            self.dev_state(30, 0)
        self.mgr.set(NM, WirelessEnabled=on)

    def delete_conn(self, path):
        o = self.objs.get(path)
        for ac in list(self.mgr.props[NM]["ActiveConnections"]):
            if self.objs[ac].props["org.freedesktop.NetworkManager.Connection.Active"]["Connection"] == path:
                self.deactivate(ac, reason=38, ac_reason=11, quiet=True)
        o.emit("org.freedesktop.NetworkManager.Settings.Connection", "Removed")
        conns = [c for c in self.settings.props["org.freedesktop.NetworkManager.Settings"]["Connections"]
                 if c != path]
        self.settings.set("org.freedesktop.NetworkManager.Settings", Connections=conns)
        self.settings.emit("org.freedesktop.NetworkManager.Settings", "ConnectionRemoved", path)
        self.remove(path)
        self.log.append(f"delete {o.data['connection']['id']}")

    def complete(self, settings, ap_path):
        """What NetworkManager's AddAndActivate completion does for Wi-Fi."""
        s = {k: dict(v) for k, v in settings.items()}
        w = s.setdefault("802-11-wireless", {})
        if "ssid" not in w:
            if ap_path in ("", "/"):
                raise DBusError("org.freedesktop.NetworkManager.Settings.InvalidProperty", "missing ssid")
            w["ssid"] = bytes(self.objs[ap_path].props["org.freedesktop.NetworkManager.AccessPoint"]["Ssid"])
        w["ssid"] = bytes(w["ssid"])
        ssid = w["ssid"].decode("utf-8", "replace")
        c = s.setdefault("connection", {})
        c.setdefault("id", ssid)
        c.setdefault("uuid", str(uuidlib.uuid4()))
        c.setdefault("type", "802-11-wireless")
        c.setdefault("autoconnect", True)
        if ap_path not in ("", "/"):
            ap = self.objs[ap_path].props["org.freedesktop.NetworkManager.AccessPoint"]
            secured = bool(ap["Flags"] & PRIVACY)
            km = s.get("802-11-wireless-security", {}).get("key-mgmt")
            rsn = ap["RsnFlags"] | ap["WpaFlags"]
            if secured and "802-11-wireless-security" not in s:
                pass  # NetworkManager fills key-mgmt and asks the agent for the key
            elif km == "wpa-psk" and not rsn & PSK:
                raise DBusError("org.freedesktop.NetworkManager.Settings.InvalidProperty",
                                "802-11-wireless-security.key-mgmt: access point does not support PSK")
            elif km == "sae" and not rsn & SAE:
                raise DBusError("org.freedesktop.NetworkManager.Settings.InvalidProperty",
                                "802-11-wireless-security.key-mgmt: access point does not support SAE")
            elif km == "wpa-eap" and not rsn & EAP:
                raise DBusError("org.freedesktop.NetworkManager.Settings.InvalidProperty",
                                "802-11-wireless-security.key-mgmt: access point does not support 802.1X")
            elif km is None and "802-11-wireless-security" in s:
                raise DBusError("org.freedesktop.NetworkManager.Settings.InvalidProperty",
                                "802-11-wireless-security.key-mgmt: property is missing")
        sec = s.get("802-11-wireless-security", {})
        if sec.get("key-mgmt") == "wpa-psk" and "psk" in sec and not 8 <= len(sec["psk"]) <= 64:
            raise DBusError("org.freedesktop.NetworkManager.Settings.InvalidProperty",
                            "802-11-wireless-security.psk: property is invalid")
        s.setdefault("ipv4", {"method": "auto"})
        s.setdefault("ipv6", {"method": "auto"})
        return s

    # ------------------------------------------------------------ method dispatch
    def _call(self, conn, sender, path, iface, method, params, inv):
        try:
            r = self.dispatch(path, iface, method, params.unpack() if params is not None else ())
            if iface == "org.freedesktop.NetworkManager.Settings.Connection" and method in ("GetSettings",
                                                                                            "GetSecrets"):
                inv.return_value(GLib.Variant.new_tuple(*r))
                return
            out = IFACES[iface]["methods"][method][1]
            if not out:
                inv.return_value(None)
            else:
                vals = r if isinstance(r, tuple) else (r,)
                inv.return_value(GLib.Variant(f"({out})", vals))
        except DBusError as e:
            self.log.append(f"error {method}: {e.msg}")
            inv.return_dbus_error(e.name, e.msg)
        except Exception as e:  # noqa: BLE001 - a mock bug must not hang the client
            import traceback
            traceback.print_exc()
            self.log.append(f"MOCK BUG {method}: {e}")
            inv.return_dbus_error("org.fenestra.MockNM.Bug", str(e))

    def dispatch(self, path, iface, method, a):
        self.log.append(f"call {iface.rsplit('.', 1)[-1]}.{method}")
        if iface == NM:
            if method in ("GetDevices", "GetAllDevices"):
                return [self.dev.path]
            if method == "GetPermissions":
                return {k: "yes" for k in ("org.freedesktop.NetworkManager.enable-disable-wifi",
                                           "org.freedesktop.NetworkManager.network-control",
                                           "org.freedesktop.NetworkManager.settings.modify.system",
                                           "org.freedesktop.NetworkManager.settings.modify.own",
                                           "org.freedesktop.NetworkManager.wifi.scan")}
            if method in ("CheckConnectivity", "state"):
                return self.mgr.props[NM]["State"] if method == "state" else 4
            if method == "GetDeviceByIpIface":
                return self.dev.path
            if method == "ActivateConnection":
                return self.activate(a[0], a[2])
            if method in ("AddAndActivateConnection", "AddAndActivateConnection2"):
                settings, _dev, ap = a[0], a[1], a[2]
                s = self.complete(settings, ap)
                c = self.add_conn(s)
                self.log.append(f"added {s['connection']['id']} autoconnect={s['connection']['autoconnect']}")
                ac = self.activate(c.path, ap)
                return (c.path, ac) if method == "AddAndActivateConnection" else (c.path, ac, {})
            if method == "DeactivateConnection":
                return self.deactivate(a[0])
            return None
        if iface == "org.freedesktop.NetworkManager.Settings":
            if method == "ListConnections":
                return self.settings.props[iface]["Connections"]
            if method in ("AddConnection", "AddConnectionUnsaved", "AddConnection2"):
                s = self.complete(a[0], "/")
                c = self.add_conn(s)
                self.log.append(f"added {s['connection']['id']} autoconnect={s['connection']['autoconnect']}")
                return (c.path, {}) if method == "AddConnection2" else c.path
            if method == "GetConnectionByUuid":
                for p in self.settings.props[iface]["Connections"]:
                    if self.objs[p].data["connection"]["uuid"] == a[0]:
                        return p
                raise DBusError("org.freedesktop.NetworkManager.Settings.InvalidConnection", "no such uuid")
            return True
        if iface == "org.freedesktop.NetworkManager.Settings.Connection":
            o = self.objs[path]
            if method == "GetSettings":
                return (_pack_settings(o.data),)
            if method == "GetSecrets":
                return (_secrets_only(o.data, a[0]),)
            if method == "Delete":
                return self.delete_conn(path)
            if method in ("Update", "UpdateUnsaved", "Update2"):
                new = {k: dict(v) for k, v in a[0].items()}
                old = o.data
                for sname, keys in SECRETS.items():  # secrets not sent are kept, like NM
                    for k in keys:
                        if sname in new and k not in new[sname] and k in old.get(sname, {}):
                            new[sname][k] = old[sname][k]
                if "802-11-wireless" in new:
                    new["802-11-wireless"]["ssid"] = bytes(new["802-11-wireless"]["ssid"])
                o.data = new
                self.log.append(f"update {new['connection']['id']} autoconnect="
                                f"{new['connection'].get('autoconnect', True)} metered="
                                f"{new['connection'].get('metered', 0)}")
                o.emit("org.freedesktop.NetworkManager.Settings.Connection", "Updated")
                return {} if method == "Update2" else None
            return None
        if iface == "org.freedesktop.NetworkManager.Device.Wireless":
            if method in ("GetAccessPoints", "GetAllAccessPoints"):
                return self.aps()
            if method == "RequestScan":
                self.dev.set(iface, LastScan=self.dev.props[iface]["LastScan"] + 1000)
                return None
        if iface == "org.freedesktop.NetworkManager.Device":
            if method == "Disconnect":
                cur = self.dev.props[iface]["ActiveConnection"]
                if cur == "/":
                    raise DBusError("org.freedesktop.NetworkManager.Device.NotActive", "not active")
                return self.deactivate(cur)
        if iface == "org.fenestra.MockNM":
            return self.control(method, a)
        return None

    def control(self, method, a):
        if method == "Log":
            return list(self.log)
        if method == "SetDelay":
            self.delay = a[0]
        if method == "SetStrength":
            for p in self.aps():
                if self.ap_ssid(p) == a[0]:
                    self.objs[p].set("org.freedesktop.NetworkManager.AccessPoint", Strength=a[1])
        if method == "RemoveNetwork":
            for p in list(self.aps()):
                if self.ap_ssid(p) == a[0]:
                    w = "org.freedesktop.NetworkManager.Device.Wireless"
                    self.dev.set(w, AccessPoints=[x for x in self.aps() if x != p])
                    self.dev.emit(w, "AccessPointRemoved", p)
                    self.remove(p)
        if method == "AddNetwork":
            self.add_ap(a[0], a[1], a[2], 0, a[3], a[4])
        return None


def main():
    loop = GLib.MainLoop()
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    srv = MockNM(bus)

    def om_call(conn, sender, path, iface, method, params, inv):
        inv.return_value(srv.managed_objects())
    bus.register_object("/org/freedesktop", NODE.lookup_interface("org.freedesktop.DBus.ObjectManager"),
                        om_call, None, None)
    srv.setup()

    def acquired(*_):
        print("mock NetworkManager ready", flush=True)

    Gio.bus_own_name_on_connection(bus, NM, Gio.BusNameOwnerFlags.NONE, acquired, lambda *_: loop.quit())
    loop.run()


if __name__ == "__main__":
    main()

"""Wi-Fi through libnm (NetworkManager's own client library, via GObject introspection).

Why libnm and not nmcli: the Windows-style Wi-Fi page needs live state (access points
appearing, the connection going through prepare → config → ip-config → activated), the reason
an attempt failed (wrong key versus out of range) and the key must never appear on a command
line. NMClient keeps a cache of NetworkManager's objects that is updated by signals, so the
page only re-reads that cache when ``Wifi.changed`` fires.

Every change goes through ``_blocked`` (read-only/screenshot mode and the control-audit
sandbox refuse it), exactly like util.run_async/dbus_call.
"""
from __future__ import annotations

import time

from gi.repository import GLib

from .. import util
from ..i18n import C_, _

try:
    import gi
    gi.require_version("NM", "1.0")
    from gi.repository import NM
except (ImportError, ValueError):  # libnm / its typelib (NetworkManager-libnm) not installed
    NM = None

# NetworkManager numeric constants (stable D-Bus API)
ST_UNAVAILABLE, ST_DISCONNECTED, ST_PREPARE, ST_CONFIG, ST_NEED_AUTH = 20, 30, 40, 50, 60
ST_IP_CONFIG, ST_IP_CHECK, ST_SECONDARIES, ST_ACTIVATED, ST_DEACTIVATING, ST_FAILED = 70, 80, 90, 100, 110, 120
R_NO_SECRETS, R_SUPPLICANT = 7, (8, 9, 10, 11)
R_SSID_NOT_FOUND, R_USER_REQUESTED, R_NEW_ACTIVATION, R_CONNECTION_REMOVED = 53, 39, 60, 38
AC_DEACTIVATED, AC_R_NO_SECRETS = 4, 9
AP_PRIVACY = 0x1
SEC_PSK, SEC_EAP, SEC_SAE, SEC_OWE, SEC_OWE_TM, SEC_SUITE_B = 0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000
SEC_PAIR_TKIP, SEC_PAIR_CCMP = 0x4, 0x8

OPEN, OWE, WEP, PSK, SAE, EAP = "open", "owe", "wep", "psk", "sae", "eap"
# Windows names (Security type in network properties / Add a network)
SECURITY_NAMES = {OPEN: "Open", OWE: "Enhanced Open", WEP: "WEP", PSK: "WPA2-Personal",
                  SAE: "WPA3-Personal", EAP: "WPA2-Enterprise"}


def _blocked(what):
    return util._blocked("dbus", f"org.freedesktop.NetworkManager {what}")


def ssid_text(raw: bytes | None) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return NM.utils_ssid_to_utf8(raw) if NM else raw.decode("latin-1")


def _bytes(gbytes) -> bytes | None:
    if gbytes is None:
        return None
    data = gbytes.get_data()
    return bytes(data) if data is not None else b""


def ap_security(ap) -> str:
    flags, wpa, rsn = int(ap.get_flags()), int(ap.get_wpa_flags()), int(ap.get_rsn_flags())
    sec = wpa | rsn
    if sec & SEC_EAP or sec & SEC_SUITE_B:
        return EAP
    if sec & SEC_PSK:
        return PSK        # WPA2 (and WPA2/WPA3 transition networks): wpa-psk works on both
    if sec & SEC_SAE:
        return SAE
    if sec & (SEC_OWE | SEC_OWE_TM):
        return OWE
    if flags & AP_PRIVACY:
        return WEP
    return OPEN


def security_label(ap) -> str:
    """'WPA2-Personal', 'WPA3-Personal', 'WPA2/WPA3-Personal'… as Windows' Security type."""
    sec = ap_security(ap)
    rsn, wpa = int(ap.get_rsn_flags()), int(ap.get_wpa_flags())
    if sec == PSK and rsn & SEC_SAE:
        return "WPA2/WPA3-Personal"
    if sec == PSK and not rsn and wpa:
        return "WPA-Personal"
    if sec == EAP and rsn & SEC_SUITE_B:
        return "WPA3-Enterprise"
    return SECURITY_NAMES[sec]


def key_valid(security: str, key: str) -> bool:
    """Same limits NetworkManager enforces (Windows keeps Next disabled until they are met)."""
    if security in (PSK, SAE):
        if len(key) == 64:
            return all(c in "0123456789abcdefABCDEF" for c in key)
        return 8 <= len(key.encode()) <= 63 if security == PSK else len(key) >= 1
    if security == WEP:
        if len(key) in (10, 26):
            return all(c in "0123456789abcdefABCDEF" for c in key)
        return len(key) in (5, 13) or len(key) >= 1  # 104/128-bit passphrase also accepted
    return True


def signal_level(strength: int) -> int:
    """0..3 bars above the dot, as the Windows glyphs (thresholds of the shell's model)."""
    return 3 if strength >= 70 else 2 if strength >= 45 else 1 if strength >= 20 else 0


class Network:
    """One row of 'Show available networks': all access points of one SSID."""

    def __init__(self, ssid: bytes | None):
        self.raw = ssid                       # None for the "Hidden Network" entry
        self.ssid = ssid_text(ssid) if ssid else ""
        self.hidden = ssid is None
        self.aps = []
        self.strength = 0
        self.security = OPEN
        self.security_name = ""
        self.connections = []                 # saved profiles usable with this network
        self.state = None                     # None, "connecting", "connected"
        self.no_internet = False
        self.frequency = 0

    @property
    def key(self):
        return "\0hidden" if self.hidden else self.raw

    @property
    def secured(self):
        return self.security not in (OPEN, OWE)

    @property
    def known(self):
        return bool(self.connections)

    def best_connection(self):
        if not self.connections:
            return None
        return max(self.connections, key=lambda c: (c.get_setting_connection().get_timestamp() or 0))

    def best_ap(self):
        return max(self.aps, key=lambda a: a.get_strength()) if self.aps else None

    def status_text(self):
        if self.state == "connected":
            if self.no_internet:
                return _("No internet, secured") if self.secured else _("No internet, open")
            return _("Connected, secured") if self.secured else _("Connected")
        if self.state == "connecting":
            return _("Connecting")
        return _("Secured") if self.secured else C_("wifi", "Open")


class Attempt:
    """One Connect: from the click to connected/failed (states for the inline row)."""

    def __init__(self, key, ssid, security):
        self.key, self.ssid, self.security = key, ssid, security
        self.phase = "connecting"   # "connecting" | "connected" | "failed" | "cancelled"
        self.error = None           # None | "wrong-key" | "not-found" | "failed" | message
        self.uuid = None
        self.conn_path = None       # profile being activated
        self.created = False        # profile created by this attempt (removed if it fails)
        self.had_key = False        # the user typed a key in this attempt
        self.started = False        # NetworkManager is activating *our* profile
        self.fail_reason = 0
        self.t0 = time.monotonic()


class Wifi:
    """Process-wide NetworkManager client (async init, cached, change-notifying)."""

    _instance = None

    @classmethod
    def get(cls) -> "Wifi":
        if cls._instance is None:
            cls._instance = DemoWifi() if util.DEMO else cls()
        return cls._instance

    def __init__(self):
        self.client = None
        self.ready = False
        self.error = None
        self.attempt: Attempt | None = None
        self._listeners = []
        self._pending = 0
        self._dev_handlers = {}
        self._ap_handlers = {}
        self._conn_handlers = {}
        self._last_scan_req = 0.0
        if NM is None:
            self.error = "libnm"
            self.ready = True
            return
        NM.Client.new_async(None, self._client_ready)

    # ------------------------------------------------------------- plumbing
    def _client_ready(self, _src, res):
        try:
            self.client = NM.Client.new_finish(res)
        except GLib.Error as e:
            self.error = e.message
            self.ready = True
            self._emit_now()
            return
        c = self.client
        for sig in ("notify::wireless-enabled", "notify::wireless-hardware-enabled", "notify::nm-running",
                    "notify::connectivity", "active-connection-added", "active-connection-removed"):
            c.connect(sig, lambda *_: self.changed())
        c.connect("device-added", lambda _c, d: (self._watch_device(d), self.changed()))
        c.connect("device-removed", lambda _c, d: (self._unwatch_device(d), self.changed()))
        c.connect("connection-added", lambda _c, rc: (self._watch_conn(rc), self.changed()))
        c.connect("connection-removed", lambda _c, rc: (self._unwatch_conn(rc), self.changed()))
        for d in c.get_devices():
            self._watch_device(d)
        for rc in c.get_connections():
            self._watch_conn(rc)
        self.ready = True
        self._emit_now()

    def _watch_device(self, d):
        if not isinstance(d, NM.DeviceWifi) or d in self._dev_handlers:
            return
        ids = [d.connect("access-point-added", lambda _d, ap: (self._watch_ap(ap), self.changed())),
               d.connect("access-point-removed", lambda _d, ap: (self._unwatch_ap(ap), self.changed())),
               d.connect("state-changed", self._dev_state),
               d.connect("notify::active-access-point", lambda *_: self.changed()),
               d.connect("notify::last-scan", lambda *_: self.changed())]
        self._dev_handlers[d] = ids
        for ap in d.get_access_points():
            self._watch_ap(ap)

    def _unwatch_device(self, d):
        for i in self._dev_handlers.pop(d, []):
            d.disconnect(i)

    def _watch_ap(self, ap):
        if ap not in self._ap_handlers:
            self._ap_handlers[ap] = ap.connect("notify::strength", lambda *_: self.changed(300))

    def _unwatch_ap(self, ap):
        h = self._ap_handlers.pop(ap, None)
        if h:
            ap.disconnect(h)

    def _watch_conn(self, rc):
        if rc not in self._conn_handlers:
            self._conn_handlers[rc] = rc.connect("changed", lambda *_: self.changed())

    def _unwatch_conn(self, rc):
        h = self._conn_handlers.pop(rc, None)
        if h:
            rc.disconnect(h)

    def add_listener(self, cb):
        self._listeners.append(cb)
        if self.ready:
            GLib.idle_add(lambda: (cb(), False)[1])

    def remove_listener(self, cb):
        if cb in self._listeners:
            self._listeners.remove(cb)

    def changed(self, delay=60):
        """Coalesce bursts of signals (a scan adds dozens of access points) into one update."""
        if self._pending:
            return
        self._pending = GLib.timeout_add(delay, self._emit)

    def _emit(self):
        self._pending = 0
        self._emit_now()
        return False

    def _emit_now(self):
        for cb in list(self._listeners):
            try:
                cb()
            except Exception as e:  # noqa: BLE001 - a broken page must not stop the others
                util.log("wifi listener failed", e)

    # ------------------------------------------------------------- state
    def available(self) -> bool:
        return self.client is not None and self.client.get_nm_running()

    def device(self):
        if not self.available():
            return None
        devs = [d for d in self.client.get_devices() if isinstance(d, NM.DeviceWifi)
                and d.get_state() not in (0, 10)]   # unknown / unmanaged
        if not devs:
            return None
        devs.sort(key=lambda d: d.get_active_connection() is None)
        return devs[0]

    def enabled(self) -> bool | None:
        if not self.available():
            return None
        return bool(self.client.wireless_get_enabled())

    def hardware_enabled(self) -> bool:
        return bool(self.client and self.client.wireless_hardware_get_enabled())

    def wifi_connections(self):
        if not self.available():
            return []
        out = []
        for c in self.client.get_connections():
            sw = c.get_setting_wireless()
            if sw is None or c.get_connection_type() != "802-11-wireless":
                continue
            if (sw.get_mode() or "infrastructure") != "infrastructure":
                continue   # hotspots (ap / adhoc) are not "known networks"
            out.append(c)
        return out

    def active_connection(self):
        d = self.device()
        return d.get_active_connection() if d else None

    def networks(self) -> list[Network]:
        """Visible networks, connected first, then by signal; a 'Hidden Network' entry last."""
        d = self.device()
        if d is None or not self.enabled():
            return []
        nets: dict = {}
        ac = d.get_active_connection()
        active_ap = d.get_active_access_point()
        for ap in d.get_access_points():
            raw = _bytes(ap.get_ssid())
            if not (raw and raw.strip(b"\0")) and ac is not None and active_ap is not None \
                    and ap.get_path() == active_ap.get_path():
                # connected to a hidden network: the row takes the profile's name, as Windows
                rc = ac.get_connection()
                sw = rc.get_setting_wireless() if rc is not None else None
                raw = _bytes(sw.get_ssid()) if sw is not None else raw
            k = raw if raw and raw.strip(b"\0") else None
            n = nets.get(k)
            if n is None:
                n = nets[k] = Network(k)
            n.aps.append(ap)
        conns = self.wifi_connections()
        ac_uuid = ac.get_uuid() if ac else None
        dstate = int(d.get_state())
        active_raw = _bytes(active_ap.get_ssid()) if active_ap else None
        connectivity = int(self.client.get_connectivity())
        for k, n in nets.items():
            best = n.best_ap()
            n.strength = best.get_strength()
            n.frequency = best.get_frequency()
            n.security = ap_security(best)
            n.security_name = security_label(best)
            has_active_ap = active_ap is not None and any(a.get_path() == active_ap.get_path() for a in n.aps)
            if k is not None:
                for c in conns:
                    if _bytes(c.get_setting_wireless().get_ssid()) == k and \
                            (any(ap.connection_valid(c) for ap in n.aps) or
                             (has_active_ap and c.get_uuid() == ac_uuid)):   # hidden network in use
                        n.connections.append(c)
            ours = ac_uuid and any(c.get_uuid() == ac_uuid for c in n.connections)
            if ac is not None and k is not None and (ours or k == active_raw or has_active_ap):
                n.state = "connected" if dstate == ST_ACTIVATED else \
                    "connecting" if ST_PREPARE <= dstate < ST_ACTIVATED else None
                n.no_internet = n.state == "connected" and connectivity in (1, 3)  # none / limited
        out = [n for k, n in nets.items() if k is not None]
        out.sort(key=lambda n: (n.state is None, -n.strength, n.ssid.lower()))
        if None in nets:
            out.append(nets[None])
        return out

    def current(self) -> Network | None:
        for n in self.networks():
            if n.state in ("connected", "connecting"):
                return n
        return None

    # ------------------------------------------------------------- actions
    def set_enabled(self, on: bool, cb=None):
        if _blocked(f"WirelessEnabled={on}"):
            return self._fail(cb)

        def done(client, res):
            try:
                client.dbus_set_property_finish(res)
                ok = True
            except GLib.Error as e:
                util.log("wifi enable failed", e.message)
                ok = False
            if cb:
                cb(ok)
        self.client.dbus_set_property(NM.DBUS_PATH, NM.DBUS_INTERFACE, "WirelessEnabled",
                                      GLib.Variant("b", on), -1, None, done)

    def scan(self, force=False):
        """Ask for a fresh scan (NetworkManager rate-limits; errors are expected and ignored)."""
        d = self.device()
        if d is None or not self.enabled():
            return
        now = time.monotonic()
        if not force and now - self._last_scan_req < 10:
            return
        self._last_scan_req = now

        def done(dev, res):
            try:
                dev.request_scan_finish(res)
            except GLib.Error as e:
                util.log("scan:", e.message)
        d.request_scan_async(None, done)

    def connect(self, net: Network, key=None, identity=None, autoconnect=True, hidden_ssid=None, cb=None, eap=None):
        """Start connecting; progress arrives through changed() and self.attempt.

        net: a Network from networks(). key/identity: what the user typed (None = use the saved
        profile). hidden_ssid: the name typed for the 'Hidden Network' entry.
        """
        d = self.device()
        ssid = hidden_ssid if net.hidden else net.ssid
        raw = hidden_ssid.encode() if net.hidden else net.raw
        att = Attempt(net.key, ssid, net.security)
        att.had_key = key is not None
        self.attempt = att
        if _blocked(f"connect {ssid}") or d is None:
            att.phase, att.error = "failed", ("read-only" if util.READ_ONLY or util.SANDBOX else "failed")
            self.changed(0)
            return att
        existing = None if net.hidden else net.best_connection()
        if net.hidden:
            existing = next((c for c in self.wifi_connections()
                             if _bytes(c.get_setting_wireless().get_ssid()) == raw), None)
        ap = None if net.hidden else net.best_ap()
        ap_path = ap.get_path() if ap else "/"

        def activated(client, res, finish):
            try:
                ac = finish(res)
            except GLib.Error as e:
                util.log("activation refused:", e.message)
                if self.attempt is att and att.phase == "connecting":
                    att.phase, att.error = "failed", _nm_error(e.message)
                    if att.created and att.uuid:
                        self._delete_uuid(att.uuid)
                    self.changed(0)
                return
            if ac is not None and att.uuid is None:
                att.uuid = ac.get_uuid()
            if ac is not None:
                ac.connect("state-changed", lambda a, st, reason: self._ac_state(att, a, st, reason))
            self.changed(0)

        if existing is not None:
            att.uuid = existing.get_uuid()
            att.conn_path = existing.get_path()
            if key is not None or identity is not None or eap is not None \
                    or existing.get_setting_connection().get_autoconnect() \
                    != autoconnect:
                # wrong/changed key of a saved network: update that profile (never a duplicate)
                conn = NM.SimpleConnection.new_clone(existing)
                self._fill_security(conn, net.security, key, identity, eap)
                conn.get_setting_connection().props.autoconnect = autoconnect
                existing.replace_settings_from_connection(conn)

                def committed(rc, res):
                    try:
                        rc.commit_changes_finish(res)
                    except GLib.Error as e:
                        att.phase, att.error = "failed", _nm_error(e.message)
                        self.changed(0)
                        return
                    self.client.activate_connection_async(
                        rc, d, ap_path, None, lambda c, r: activated(c, r, c.activate_connection_finish))
                existing.commit_changes_async(True, None, committed)
            else:
                self.client.activate_connection_async(
                    existing, d, ap_path, None, lambda c, r: activated(c, r, c.activate_connection_finish))
            self.changed(0)
            return att

        conn = self._new_connection(raw, net.security, key, identity, autoconnect, hidden=net.hidden, eap=eap)
        att.uuid = conn.get_uuid()
        att.created = True
        self.client.add_and_activate_connection_async(
            conn, d, ap_path, None, lambda c, r: activated(c, r, c.add_and_activate_connection_finish))
        self.changed(0)
        return att

    def _new_connection(self, raw, security, key, identity, autoconnect, hidden=False, eap=None):
        conn = NM.SimpleConnection.new()
        s_con = NM.SettingConnection.new()
        s_con.props.id = ssid_text(raw)
        s_con.props.uuid = NM.utils_uuid_generate()
        s_con.props.type = "802-11-wireless"
        s_con.props.autoconnect = autoconnect
        conn.add_setting(s_con)
        s_wifi = NM.SettingWireless.new()
        s_wifi.props.ssid = GLib.Bytes.new(raw)
        s_wifi.props.mode = "infrastructure"
        if hidden:
            s_wifi.props.hidden = True
        conn.add_setting(s_wifi)
        conn.add_setting(NM.SettingIP4Config.new())
        conn.get_setting_ip4_config().props.method = "auto"
        conn.add_setting(NM.SettingIP6Config.new())
        conn.get_setting_ip6_config().props.method = "auto"
        self._fill_security(conn, security, key, identity, eap)
        return conn

    @staticmethod
    def _fill_security(conn, security, key, identity, eap=None):
        if security == OPEN:
            conn.remove_setting(NM.SettingWirelessSecurity)
            return
        s = conn.get_setting_wireless_security()
        if s is None:
            s = NM.SettingWirelessSecurity.new()
            conn.add_setting(s)
        if security == OWE:
            s.props.key_mgmt = "owe"
        elif security in (PSK, SAE):
            s.props.key_mgmt = "wpa-psk" if security == PSK else "sae"
            if key is not None:
                s.props.psk = key
                s.props.psk_flags = NM.SettingSecretFlags.NONE   # stored by NetworkManager
        elif security == WEP:
            s.props.key_mgmt = "none"
            if key is not None:
                hexkey = len(key) in (10, 26) and all(c in "0123456789abcdefABCDEF" for c in key)
                s.props.wep_key_type = NM.WepKeyType.KEY if hexkey or len(key) in (5, 13) \
                    else NM.WepKeyType.PASSPHRASE
                s.set_wep_key(0, key)
                s.props.wep_key_flags = NM.SettingSecretFlags.NONE
        elif security == EAP:
            s.props.key_mgmt = "wpa-eap"
            x = conn.get_setting_802_1x()
            if x is None:
                x = NM.Setting8021x.new()
                conn.add_setting(x)
                x.props.eap = ["peap"]
                x.props.phase2_auth = "mschapv2"
            if eap is not None:
                apply_8021x(x, eap)
            if identity is not None:
                x.props.identity = identity
            if key is not None:
                x.props.password = key
                x.props.password_flags = NM.SettingSecretFlags.NONE

    def _dev_state(self, dev, new, old, reason):
        att = self.attempt
        if att is not None and att.phase == "connecting":
            ac = dev.get_active_connection()
            mine = ac is not None and ac.get_uuid() == att.uuid
            if mine and ST_PREPARE <= new <= ST_ACTIVATED:
                att.started = True
            if new == ST_ACTIVATED and mine:
                att.phase = "connected"
            elif new == ST_FAILED and (mine or att.started):
                self._failed(att, reason)
            elif att.started and new in (ST_DISCONNECTED, ST_DEACTIVATING) and not mine:
                if reason in (R_NEW_ACTIVATION, R_USER_REQUESTED, R_CONNECTION_REMOVED) and att.phase == "connecting":
                    att.phase = "cancelled"
        self.changed(0 if new in (ST_ACTIVATED, ST_FAILED, ST_NEED_AUTH) else 60)

    def _ac_state(self, att, ac, state, reason):
        if self.attempt is att and att.phase == "connecting" and state == AC_DEACTIVATED:
            if reason == AC_R_NO_SECRETS:
                self._failed(att, R_NO_SECRETS)
            else:
                # the device's own state change carries the precise reason; give it a moment
                GLib.timeout_add(400, self._ac_gone, att)
        self.changed(0)

    def _ac_gone(self, att):
        if self.attempt is att and att.phase == "connecting":
            d = self.device()
            reason = int(d.get_state_reason()) if d is not None else 1
            self._failed(att, att.fail_reason or reason or 1)
            self.changed(0)
        return False

    def _failed(self, att, reason):
        att.fail_reason = reason
        att.phase = "failed"
        if att.security != OPEN and (reason == R_NO_SECRETS or reason in R_SUPPLICANT):
            att.error = "wrong-key"
        elif reason == R_SSID_NOT_FOUND:
            att.error = "not-found"
        else:
            att.error = "failed"
        if att.created and att.uuid:
            # Windows keeps no profile for a network it never connected to
            self._delete_uuid(att.uuid)

    def _delete_uuid(self, uuid):
        rc = self.client.get_connection_by_uuid(uuid) if self.client else None
        if rc is None:
            # the profile may not be in the cache yet: retry shortly
            GLib.timeout_add(300, lambda: (self._delete_uuid_late(uuid), False)[1])
            return
        rc.delete_async(None, lambda c, r: _finish_quiet(c.delete_finish, r))

    def _delete_uuid_late(self, uuid):
        rc = self.client.get_connection_by_uuid(uuid)
        if rc is not None:
            rc.delete_async(None, lambda c, r: _finish_quiet(c.delete_finish, r))

    def cancel(self):
        """Cancel the attempt in progress (Windows' Cancel while 'Connecting')."""
        att = self.attempt
        if att is None:
            return
        if att.phase == "connecting":
            att.phase = "cancelled"
            ac = self.active_connection()
            if ac is not None and ac.get_uuid() == att.uuid and not _blocked("deactivate"):
                self.client.deactivate_connection_async(
                    ac, None, lambda c, r: _finish_quiet(c.deactivate_connection_finish, r))
            if att.created and att.uuid:
                self._delete_uuid(att.uuid)
        self.attempt = None
        self.changed(0)

    def clear_attempt(self):
        self.attempt = None

    def disconnect(self, cb=None):
        d = self.device()
        if d is None or _blocked("disconnect"):
            return self._fail(cb)

        def done(dev, res):
            ok = _finish_quiet(dev.disconnect_finish, res)
            if cb:
                cb(ok)
        d.disconnect_async(None, done)

    def forget(self, conns, cb=None):
        """Delete saved profiles (all profiles of one SSID: Windows has one per network)."""
        if _blocked("forget"):
            return self._fail(cb)
        left = [len(conns)]
        ok_all = [True]

        def done(rc, res):
            ok_all[0] &= _finish_quiet(rc.delete_finish, res)
            left[0] -= 1
            if left[0] == 0 and cb:
                cb(ok_all[0])
        for c in conns:
            c.delete_async(None, done)
        if not conns and cb:
            cb(True)

    def update(self, conn, cb=None, **changes):
        """autoconnect=bool, metered=bool, mac_random=bool on a saved profile."""
        if _blocked(f"update {changes}"):
            return self._fail(cb)
        s_con = conn.get_setting_connection()
        if "autoconnect" in changes:
            s_con.props.autoconnect = changes["autoconnect"]
        if "metered" in changes:
            s_con.props.metered = NM.Metered.YES if changes["metered"] else NM.Metered.NO
        if "mac_random" in changes:
            conn.get_setting_wireless().props.cloned_mac_address = "stable" if changes["mac_random"] else "permanent"

        def done(rc, res):
            ok = _finish_quiet(rc.commit_changes_finish, res)
            if cb:
                cb(ok)
        conn.commit_changes_async(True, None, done)

    def add_network(self, ssid, security, key, autoconnect=True, hidden=False, cb=None, eap=None):
        """'Add a new network' (Manage known networks): save a profile without connecting."""
        if _blocked(f"add {ssid}"):
            return self._fail(cb)
        conn = self._new_connection(ssid.encode(), security, key, None if security != EAP else "", autoconnect,
                                    hidden=hidden, eap=eap)

        def done(client, res):
            try:
                client.add_connection_finish(res)
                ok, msg = True, None
            except GLib.Error as e:
                ok, msg = False, _nm_error(e.message)
            if cb:
                cb(ok, msg)
        self.client.add_connection_async(conn, True, None, done)

    def eap_settings(self, conn):
        """The 802.1X settings of a saved profile (pages/wifi_enterprise.py), without the password."""
        return read_8021x(conn.get_setting_802_1x() if conn is not None else None)

    def update_security(self, conn, eap, cb=None):
        """Replace a saved enterprise profile's 802.1X settings (and password, when given)."""
        if _blocked(f"update 802.1x {conn.get_id()}"):
            return self._fail(cb)
        x = conn.get_setting_802_1x()
        if x is None:
            x = NM.Setting8021x.new()
            conn.add_setting(x)
        apply_8021x(x, eap)
        if eap.get("identity") is not None:
            x.props.identity = eap["identity"]
        if eap.get("password"):
            x.props.password = eap["password"]
            x.props.password_flags = NM.SettingSecretFlags.NONE

        def done(rc, res):
            ok = _finish_quiet(rc.commit_changes_finish, res)
            if cb:
                cb(ok)
        conn.commit_changes_async(True, None, done)

    def get_key(self, conn, cb):
        """The saved key ('View Wi-Fi security key'); cb(key or None)."""
        if not self.available():
            return cb(None)
        setting = "802-1x" if conn.get_setting_802_1x() is not None else "802-11-wireless-security"

        def done(rc, res):
            try:
                v = rc.get_secrets_finish(res)
                vals = (v.unpack() if v is not None else {}).get(setting, {})
                cb(vals.get("psk") or vals.get("password") or vals.get("wep-key0"))
            except GLib.Error as e:
                util.log("secrets:", e.message)
                cb(None)
        conn.get_secrets_async(setting, None, done)

    @staticmethod
    def _fail(cb):
        if cb:
            GLib.idle_add(lambda: (cb(False), False)[1])

    # ------------------------------------------------------------- properties
    def details(self, conn=None) -> list[tuple[str, str]]:
        """Windows' properties list for the connected network (or only the adapter rows)."""
        d = self.device()
        if d is None:
            return []
        rows = []
        ac = d.get_active_connection()
        ap = d.get_active_access_point()
        connected = ac is not None and int(d.get_state()) == ST_ACTIVATED and \
            (conn is None or ac.get_uuid() == conn.get_uuid())
        if connected and ap is not None:
            freq = ap.get_frequency()
            rows += [(_("SSID"), ssid_text(_bytes(ap.get_ssid()))),
                     (_("Protocol"), _protocol(d, ap)),
                     (_("Security type"), security_label(ap))]
        rows += [(_("Manufacturer"), d.get_vendor() or ""),
                 (_("Description"), d.get_product() or d.get_description() or ""),
                 (_("Driver version"), " ".join(x for x in (d.get_driver(), d.get_driver_version()) if x))]
        if connected and ap is not None:
            band = "6 GHz" if freq >= 5925 else "5 GHz" if freq >= 4900 else "2.4 GHz"
            rows += [(_("Network band"), band),
                     (_("Network channel"), str(NM.utils_wifi_freq_to_channel(freq))),
                     (_("Link speed (Receive/Transmit)"),
                      "{0}/{0} (Mbps)".format(d.get_bitrate() // 1000))]
            ip6 = d.get_ip6_config()
            if ip6 is not None:
                addrs = [a.get_address() for a in ip6.get_addresses()]
                glob = [a for a in addrs if not a.lower().startswith("fe80")]
                ll = [a for a in addrs if a.lower().startswith("fe80")]
                if glob:
                    rows.append((_("IPv6 address"), "\n".join(glob)))
                if ll:
                    rows.append((_("Link-local IPv6 address"), "\n".join(f"{a}%{d.get_iface()}" for a in ll)))
                if ip6.get_nameservers():
                    rows.append((_("IPv6 DNS servers"), "\n".join(ip6.get_nameservers())))
            ip4 = d.get_ip4_config()
            if ip4 is not None:
                a4 = [a.get_address() for a in ip4.get_addresses()]
                if a4:
                    rows.append((_("IPv4 address"), "\n".join(a4)))
                if ip4.get_nameservers():
                    rows.append((_("IPv4 DNS servers"), "\n".join(ip4.get_nameservers())))
                if ip4.get_domains():
                    rows.append((_("Primary DNS suffix"), ip4.get_domains()[0]))
        rows.append((_("Physical address (MAC)"), d.get_hw_address() or ""))
        return [(k, v) for k, v in rows if v]

    def ip_summary(self, conn):
        """('Automatic (DHCP)' | 'Manual', same for DNS) of a saved profile."""
        s4 = conn.get_setting_ip4_config()
        manual_ip = s4 is not None and s4.get_method() == "manual"
        manual_dns = s4 is not None and (s4.get_ignore_auto_dns() or s4.get_num_dns() > 0)
        return (_("Manual") if manual_ip else _("Automatic (DHCP)"),
                _("Manual") if manual_dns else _("Automatic (DHCP)"))


def _protocol(dev, ap):
    """Wi-Fi generation from the link (iw), else from the access point's maximum rate."""
    out = util.run_sync(["iw", "dev", dev.get_iface(), "link"]) if util.have("iw") else ""
    if "EHT-MCS" in out:
        return "Wi-Fi 7 (802.11be)"
    if "HE-MCS" in out:
        return "Wi-Fi 6E (802.11ax)" if ap.get_frequency() >= 5925 else "Wi-Fi 6 (802.11ax)"
    if "VHT-MCS" in out:
        return "Wi-Fi 5 (802.11ac)"
    if " MCS" in out:
        return "Wi-Fi 4 (802.11n)"
    rate = ap.get_max_bitrate() // 1000
    if rate > 600 and ap.get_frequency() >= 4900:
        return "Wi-Fi 5 (802.11ac)"
    if rate > 54:
        return "Wi-Fi 4 (802.11n)"
    return "802.11g" if ap.get_frequency() < 4900 else "802.11a"


PHASE2_EAP_PREFIX = "eap-"


def apply_8021x(x, e):
    """e: method, phase2, anonymous, ca (system/file/none), ca_path, domain, client_cert,
    private_key, key_password, peapver. Identity and password are set by the caller."""
    def path(v):   # the "path" scheme of the certificate properties
        return GLib.Bytes.new(b"file://" + v.encode() + b"\0") if v else None
    method = e.get("method") or "peap"
    x.props.eap = [method]
    x.props.phase2_auth = None
    x.props.phase2_autheap = None
    p2 = e.get("phase2") or ""
    if method in ("peap", "ttls", "fast") and p2:
        if p2.startswith(PHASE2_EAP_PREFIX):
            x.props.phase2_autheap = p2[len(PHASE2_EAP_PREFIX):]
        else:
            x.props.phase2_auth = p2
    x.props.anonymous_identity = e.get("anonymous") or None
    x.props.phase1_peapver = e.get("peapver") if e.get("peapver") in ("0", "1") else None
    ca = e.get("ca") or "none"
    x.props.system_ca_certs = ca == "system"
    x.props.ca_cert = path(e.get("ca_path") if ca == "file" else None)
    x.props.domain_suffix_match = e.get("domain") or None
    if method == "fast":
        x.props.phase1_fast_provisioning = "3"
    if method == "tls":
        x.props.client_cert = path(e.get("client_cert"))
        x.props.private_key = path(e.get("private_key"))
        if e.get("key_password"):
            x.props.private_key_password = e["key_password"]
        x.props.private_key_password_flags = NM.SettingSecretFlags.NONE
    else:
        x.props.client_cert = None
        x.props.private_key = None


def _cert_path(blob):
    if blob is None:
        return ""
    data = bytes(blob.get_data())
    return data[len(b"file://"):].rstrip(b"\0").decode(errors="replace") if data.startswith(b"file://") else ""


def read_8021x(x):
    if x is None:
        return {"method": "peap", "phase2": "mschapv2", "ca": "none"}
    method = (x.get_eap_method(0) if x.get_num_eap_methods() else None) or "peap"
    p2 = x.props.phase2_auth or (PHASE2_EAP_PREFIX + x.props.phase2_autheap if x.props.phase2_autheap else "")
    ca_path = _cert_path(x.props.ca_cert)
    return {"method": method, "phase2": p2, "identity": x.props.identity or "",
            "anonymous": x.props.anonymous_identity or "",
            "ca": "file" if ca_path else "system" if x.props.system_ca_certs else "none", "ca_path": ca_path,
            "domain": x.props.domain_suffix_match or "", "peapver": x.props.phase1_peapver or "",
            "client_cert": _cert_path(x.props.client_cert), "private_key": _cert_path(x.props.private_key)}


def _nm_error(msg: str) -> str:
    if "psk" in msg or "wep-key" in msg or "password" in msg:
        return "wrong-key"
    if "authoriz" in msg.lower() or "not allowed" in msg.lower() or "permission" in msg.lower():
        return "denied"
    return "failed"


def _finish_quiet(finish, res) -> bool:
    try:
        finish(res)
        return True
    except GLib.Error as e:
        util.log("NetworkManager:", e.message)
        return False


# ----------------------------------------------------------------- demo (screenshots)

class _DemoAP:
    def __init__(self, ssid, strength, sec, freq=5180):
        self.ssid, self.strength, self.sec, self.freq = ssid, strength, sec, freq

    def get_strength(self):
        return self.strength

    def get_frequency(self):
        return self.freq


class _DemoConn:
    def __init__(self, ssid, autoconnect=True, metered=False):
        self.ssid, self.autoconnect, self.metered = ssid, autoconnect, metered

    def get_id(self):
        return self.ssid

    def get_uuid(self):
        return "demo-" + self.ssid

    def get_setting_connection(self):
        c = self

        class S:
            def get_timestamp(self):
                return 1

            def get_autoconnect(self):
                return c.autoconnect

            def get_metered(self):
                return 1 if c.metered else 0

            def get_autoconnect_priority(self):
                return 0
        return S()

    def get_setting_wireless(self):
        c = self

        class W:
            def get_ssid(self):
                return GLib.Bytes.new(c.ssid.encode())

            def get_cloned_mac_address(self):
                return None
        return W()

    def get_setting_wireless_security(self):
        return None

    def get_setting_802_1x(self):
        return None

    def get_setting_ip4_config(self):
        return None


class DemoWifi(Wifi):
    """Neutral sample networks for --demo-data / --screenshot (never the real ones)."""

    def __init__(self):  # noqa: D107 - no NetworkManager at all
        self.client = None
        self.ready = True
        self.error = None
        self.attempt = None
        self._listeners = []
        self._pending = 0
        self._known = [_DemoConn("HomeNetwork"), _DemoConn("Office-5G"), _DemoConn("Library", autoconnect=False)]

    def available(self):
        return True

    def device(self):
        return True

    def enabled(self):
        return True

    def hardware_enabled(self):
        return True

    def wifi_connections(self):
        return list(self._known)

    def active_connection(self):
        return self._known[0]

    def networks(self):
        out = []
        for ssid, st, sec in (("HomeNetwork", 82, PSK), ("Office-5G", 64, PSK), ("Cafe-Guest", 48, OPEN),
                              ("Neighbours-WiFi", 35, SAE), (None, 30, PSK)):
            n = Network(ssid.encode() if ssid else None)
            n.aps = [_DemoAP(ssid, st, sec)]
            n.strength, n.security = st, sec
            n.security_name = SECURITY_NAMES[sec]
            n.connections = [c for c in self._known if c.ssid == ssid]
            n.state = "connected" if ssid == "HomeNetwork" else None
            out.append(n)
        return out

    def scan(self, force=False):
        pass

    def details(self, conn=None):
        return [(_("SSID"), "HomeNetwork"), (_("Protocol"), "Wi-Fi 6 (802.11ax)"),
                (_("Security type"), "WPA2-Personal"), (_("Manufacturer"), "Intel Corporation"),
                (_("Description"), "Wi-Fi 6 AX201 160MHz"), (_("Driver version"), "iwlwifi 6.17.1"),
                (_("Network band"), "5 GHz"), (_("Network channel"), "36"),
                (_("Link speed (Receive/Transmit)"), "1201/1201 (Mbps)"),
                (_("IPv4 address"), "192.168.1.23"), (_("IPv4 DNS servers"), "192.168.1.1"),
                (_("Physical address (MAC)"), "00:11:22:33:44:55")]

    def ip_summary(self, conn):
        return _("Automatic (DHCP)"), _("Automatic (DHCP)")

    def get_key(self, conn, cb):
        GLib.idle_add(lambda: (cb(None), False)[1])

    def eap_settings(self, conn):
        return read_8021x(getattr(conn, 'get_setting_802_1x', lambda: None)())

    def update_security(self, conn, eap, cb=None):
        if cb:
            cb(True)

    def connect(self, net, key=None, identity=None, autoconnect=True, hidden_ssid=None, cb=None, eap=None):
        att = Attempt(net.key, net.ssid, net.security)
        att.phase, att.error = "failed", "read-only"
        self.attempt = att
        self.changed(0)
        return att

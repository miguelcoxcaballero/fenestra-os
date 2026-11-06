"""Network & internet (NetworkManager via nmcli)."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import util
from ..backends import network, session
from ..i18n import _
from ..widgets import (ContentDialog, ExpanderRow, SettingRow, ToggleSwitch, button, icon, label,
                       not_available_row, show_dialog, spinner, toast)
from .base import Page, register


def _airplane_row(page):
    state = network.airplane_mode()
    t = ToggleSwitch(bool(state), lambda v: network.set_airplane_mode(
        v, lambda *_: GLib.timeout_add(800, lambda: (page.refresh(), False)[1])))
    r = SettingRow(_("Airplane mode"), _("Stop all wireless communication"), "fs-airplane-symbolic",
                   control=t, key="airplane")
    page.remember("airplane", r)
    return r, t


@register
class NetworkPage(Page):
    id = "network"
    title = "Network & internet"
    keywords = "internet wifi ethernet vpn proxy airplane hotspot"
    index = [
        ("airplane", "Airplane mode", "flight wireless off"),
        ("wifi-toggle", "Wi-Fi", "wireless wlan"),
        ("proxy", "Proxy", "http socks"),
        ("vpn", "VPN", "wireguard openvpn"),
        ("advanced-net", "Advanced network settings", "adapters reset"),
    ]

    def build(self, box):
        # Hero like the reference: big accent glyph, connection name, status with a
        # small globe, and a Properties status item on the right.
        from .common import _status_item
        hero = Gtk.Box(spacing=24)
        hero.add_css_class("net-hero")
        self.hero_icon = Gtk.Image.new_from_icon_name("fs-wifi-1-symbolic")
        self.hero_icon.set_pixel_size(92)
        self.hero_icon.add_css_class("accent-icon")
        hero.append(self.hero_icon)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        self.hero_title = label(_("Checking…"), "hero-name", ellipsize=True)
        st = Gtk.Box(spacing=6)
        st.add_css_class("net-hero-status")
        st.append(icon("fs-globe-symbolic", 14, "accent-icon"))
        self.hero_sub = label("", "net-hero-sub", ellipsize=True)
        st.append(self.hero_sub)
        tb.append(self.hero_title)
        tb.append(st)
        hero.append(tb)
        self._hero_target = "wifi"
        self.hero_btn = _status_item("fs-info-symbolic", _("Properties"), "", lambda: self.go(self._hero_target))
        self.hero_btn.ic.remove_css_class("accent-icon")
        self.hero_btn.set_valign(Gtk.Align.CENTER)
        hero.append(self.hero_btn)
        box.append(hero)

        g = self.group()
        if not network.available():
            g.add(not_available_row(_("Network"), _("NetworkManager (nmcli) is not installed")))
            return
        self.wifi_row = SettingRow(_("Wi-Fi"), _("Connect, manage known networks, metered network"),
                                   "fs-wifi-1-symbolic", chevron=True, on_click=lambda: self.go("wifi"),
                                   key="wifi-toggle")
        self.remember("wifi-toggle", self.wifi_row)
        g.add(self.wifi_row)
        self.eth_row = SettingRow(_("Ethernet"), _("Authentication, IP and DNS settings, metered network"),
                                  "fs-plug-connected-symbolic", chevron=True, on_click=lambda: self.go("ethernet"))
        g.add(self.eth_row)
        self.ext_row(g, _("VPN"), _("Add, connect, manage"), "fs-shield-lock-symbolic",
                     ["gnome-control-center", "network"], key="vpn")
        self.ext_row(g, _("Mobile hotspot"), _("Share your internet connection"), "fs-router-symbolic",
                     ["gnome-control-center", "wifi"])
        r, self.air_toggle = _airplane_row(self)
        g.add(r)
        self.nav_row(g, "proxy", _("Proxy"), _("Proxy server for Wi-Fi and Ethernet connections"),
                     "fs-globe-symbolic", key="proxy")
        self.ext_row(g, _("Advanced network settings"), _("View all network adapters, network reset"),
                     "fs-network-check-symbolic", ["nm-connection-editor"] if util.have("nm-connection-editor")
                     else ["gnome-control-center", "network"], key="advanced-net")
        self.refresh()

    def on_show(self):
        if hasattr(self, "wifi_row"):
            self.refresh()

    def refresh(self):
        network.status(self._got)
        st = network.airplane_mode()
        if st is not None and hasattr(self, "air_toggle"):
            self.air_toggle.set_active(st)

    def _got(self, res):
        devs = res["devices"]
        conn = [d for d in devs if d.connected and d.type in ("wifi", "ethernet")]
        wifi_on = res["wifi_enabled"]
        if wifi_on is not None:
            self.wifi_row.set_control(ToggleSwitch(wifi_on, lambda v: network.set_wifi(
                v, lambda *_: GLib.timeout_add(800, lambda: (self.refresh(), False)[1]))))
        eth = [d for d in devs if d.type == "ethernet"]
        if not eth:
            self.eth_row.set_subtitle(_("No Ethernet adapter"))
        else:
            self.eth_row.set_subtitle(_("Connected") if eth[0].connected else _("Not connected"))
        if conn:
            d = conn[0]
            self.hero_title.set_label(d.connection or d.name)
            self.hero_sub.set_label(_("Connected"))
            self.hero_btn.sub.set_label(_("Wi-Fi") if d.type == "wifi" else _("Ethernet"))
            self.hero_icon.set_from_icon_name("fs-wifi-1-symbolic" if d.type == "wifi"
                                              else "fs-plug-connected-symbolic")
            self._hero_target = "wifi" if d.type == "wifi" else "ethernet"
        else:
            self.hero_title.set_label(_("Not connected"))
            self.hero_sub.set_label(_("You aren't connected to any networks"))
            self.hero_btn.sub.set_label("")
            self.hero_icon.set_from_icon_name("fs-globe-symbolic")


@register
class WifiPage(Page):
    id = "wifi"
    parent = "network"
    title = "Wi-Fi"
    keywords = "wireless networks connect password ssid hidden known"
    index = [
        ("wifi", "Wi-Fi", "on off"),
        ("available", "Show available networks", "scan list connect"),
        ("known", "Manage known networks", "forget saved"),
    ]

    def build(self, box):
        g = self.group()
        self.toggle_row = SettingRow(_("Wi-Fi"), None, "fs-wifi-1-symbolic", key="wifi")
        self.remember("wifi", self.toggle_row)
        g.add(self.toggle_row)
        self.avail = ExpanderRow(_("Show available networks"), None, "fs-wifi-1-symbolic", key="available",
                                 expanded=True,
                                 control=button(_("Refresh"), lambda: self.load(rescan=True), css="small"))
        self.remember("available", self.avail)
        g.add(self.avail)
        self.props_row = SettingRow(_("Hardware properties"), _("View and edit details for this adapter"),
                                    "fs-options-symbolic", chevron=True,
                                    on_click=lambda: session.open_panel("wifi", self.window), key="hw-props")
        g.add(self.props_row)
        if not session.panel_available("wifi"):
            self._session_hide(self.props_row)
        self.known = ExpanderRow(_("Manage known networks"), _("Add, remove, edit networks"),
                                 "fs-history-symbolic", key="known")
        self.remember("known", self.known)
        g.add(self.known)
        self.wifi_dev = None
        self.load()

    def on_show(self):
        self.load()

    def load(self, rescan=False):
        network.status(lambda res: self._status(res, rescan))

    def _status(self, res, rescan):
        wifi_on = res["wifi_enabled"]
        devs = [d for d in res["devices"] if d.type == "wifi"]
        self.wifi_dev = devs[0] if devs else None
        if wifi_on is None or not devs:
            self.toggle_row.set_control(label(_("Not available"), "row-value"))
            self.toggle_row.set_subtitle(_("No Wi-Fi adapter found"))
            self.avail.clear()
            return
        self.toggle_row.set_control(ToggleSwitch(wifi_on, lambda v: network.set_wifi(
            v, lambda *_: GLib.timeout_add(1500, lambda: (self.load(), False)[1]))))
        self.avail.clear()
        if not wifi_on:
            self.avail.add(SettingRow(_("Turn on Wi-Fi to see available networks"), None, None))
            return
        self.avail.add(SettingRow(_("Searching…"), None, None, control=spinner()))
        network.known_connections(lambda known: network.wifi_list(lambda aps: self._list(aps, known),
                                                                  rescan=rescan))

    def _list(self, aps, known):
        self.avail.clear()
        if not aps:
            self.avail.add(SettingRow(_("No networks found"), None, None))
        for ap in aps[:25]:
            sub = _("Connected, secured") if ap.in_use and ap.secured else \
                _("Connected") if ap.in_use else _("Secured") if ap.secured else _("Open")
            if ap.in_use and self.wifi_dev:
                ctrl = button(_("Disconnect"), lambda: network.disconnect(
                    self.wifi_dev.name, lambda *_: self.load()), css="small")
            else:
                ctrl = button(_("Connect"), lambda a=ap, k=known: self._connect(a, k), css="small")
            r = SettingRow(ap.ssid, f"{sub} · {ap.signal}%", "fs-wifi-1-symbolic"
                           if not ap.secured else "fs-lock-closed-symbolic", control=ctrl)
            self.avail.add(r)
        self.known.clear()
        for name in sorted(known):
            self.known.add(SettingRow(name, None, None, control=button(
                _("Forget"), lambda n=name: network.forget(n, lambda *_: self.load()), css="small")))
        if not known:
            self.known.add(SettingRow(_("No known networks"), None, None))

    def _connect(self, ap, known):
        def done(ok, out, err):
            if ok:
                toast(self.box, _("Connected to {0}").format(ap.ssid))
            else:
                toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("Couldn't connect to this network"))
            self.load()
        if ap.ssid in known or not ap.secured:
            if ap.ssid in known:
                network.connect_known(ap.ssid, done)
            else:
                network.connect(ap.ssid, None, done)
            return
        entry = Gtk.PasswordEntry()
        entry.set_show_peek_icon(True)
        entry.add_css_class("fluent-entry")
        extra = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        extra.append(label(_("Enter the network security key"), "caption"))
        extra.append(entry)

        def resp(r):
            if r == "primary":
                network.connect(ap.ssid, entry.get_text(), done)
        dlg = ContentDialog(ap.ssid, None, primary=_("Next"), close=_("Cancel"), on_response=resp, extra=extra)
        entry.connect("activate", lambda *_: dlg.respond("primary"))
        show_dialog(self.box, dlg)
        entry.grab_focus()


@register
class EthernetPage(Page):
    id = "ethernet"
    parent = "network"
    title = "Ethernet"
    keywords = "wired lan ip dns"

    def build(self, box):
        self.g = self.group()
        network.status(self._got)

    def _got(self, res):
        eth = [d for d in res["devices"] if d.type == "ethernet"]
        if not eth:
            self.g.add(not_available_row(_("Ethernet"), _("No Ethernet adapter found"),
                                         "fs-plug-connected-symbolic"))
            return
        d = eth[0]
        self.g.add(SettingRow(d.connection or d.name, _("Connected") if d.connected else _("Not connected"),
                              "fs-plug-connected-symbolic"))
        props = self.group(_("Properties"))
        network.device_details(d.name, lambda info: self._details(props, info))
        self.ext_row(props, _("Edit IP and DNS settings"), None, "fs-options-symbolic",
                     ["gnome-control-center", "network"])

    def _details(self, g, info):
        for k, t in (("IP4.ADDRESS", _("IPv4 address")), ("IP4.GATEWAY", _("Default gateway")),
                     ("IP4.DNS", _("DNS servers")), ("IP6.ADDRESS", _("IPv6 address")),
                     ("GENERAL.HWADDR", _("Physical address (MAC)")), ("CAPABILITIES.SPEED", _("Link speed")),
                     ("GENERAL.DRIVER", _("Driver"))):
            if info.get(k):
                g.add(SettingRow(t, None, None, control=label(info[k], "row-value", selectable=True)))


PROXY = "org.gnome.system.proxy"


@register
class ProxyPage(Page):
    id = "proxy"
    parent = "network"
    title = "Proxy"
    keywords = "proxy http https socks pac automatic configuration"

    def build(self, box):
        from .common import gsetting_dropdown
        g = self.group(_("Proxy setup"))
        if not util.has_key(PROXY, "mode"):
            g.add(not_available_row(_("Proxy")))
            return
        dd = gsetting_dropdown(PROXY, "mode", [("none", _("Off")), ("auto", _("Use setup script")),
                                               ("manual", _("Use a proxy server"))])
        g.add(SettingRow(_("Proxy mode"), None, "fs-globe-symbolic", control=dd))
        self.auto_g = self.group(_("Automatic proxy setup"))
        self.auto_g.add(SettingRow(_("Script address"), None, None, control=self._entry(PROXY, "autoconfig-url", 300)))
        self.man_g = self.group(_("Manual proxy setup"))
        for proto, title in (("http", "HTTP"), ("https", "HTTPS"), ("ftp", "FTP"), ("socks", "SOCKS")):
            schema = f"{PROXY}.{proto}"
            if not util.has_key(schema, "host"):
                continue
            ctrl = Gtk.Box(spacing=8)
            ctrl.append(self._entry(schema, "host", 220))
            ctrl.append(self._entry(schema, "port", 80, is_int=True))
            self.man_g.add(SettingRow(title, _("Address and port"), None, control=ctrl))
        self.man_g.add(SettingRow(_("Don't use the proxy server for these addresses"), _("Separate entries with commas"),
                                  None, control=self._entry(PROXY, "ignore-hosts", 260, is_list=True)))
        util.gconnect(PROXY, "mode", self._vis)
        self._vis()

    def _vis(self):
        mode = util.gget(PROXY, "mode", "none")
        self.auto_g.set_visible(mode == "auto")
        self.man_g.set_visible(mode == "manual")

    def _entry(self, schema, key, width, is_int=False, is_list=False):
        e = Gtk.Entry()
        e.add_css_class("fluent-entry")
        e.set_size_request(width, -1)
        e.set_valign(Gtk.Align.CENTER)

        def load():
            v = util.gget(schema, key)
            txt = ", ".join(v) if is_list else ("" if (is_int and not v) else str(v if v is not None else ""))
            if e.get_text() != txt and not e.has_focus():
                e.set_text(txt)

        def save(*_a):
            t = e.get_text().strip()
            if is_int:
                val = int(t) if t.isdigit() else 0
            elif is_list:
                val = [x.strip() for x in t.split(",") if x.strip()]
            else:
                val = t
            if util.gget(schema, key) != val and not util.gset(schema, key, val):
                toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("The change was not applied"))
        load()
        e.connect("activate", save)
        fc = Gtk.EventControllerFocus()
        fc.connect("leave", save)
        e.add_controller(fc)
        util.gconnect(schema, key, load)
        return e

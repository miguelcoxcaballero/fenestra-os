"""Network & internet › Wi-Fi, as Windows 11: available networks with inline connect, known
networks, per-network properties and the adapter's hardware properties (backends/wifi.py)."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import util
from ..backends import wifi as wb
from ..i18n import C_, _
from ..widgets import (ContentDialog, Dropdown, ExpanderRow, SettingRow, ToggleSwitch, button, clear, icon,
                       label, link, not_available_row, show_dialog, spinner, toast)
from .base import Page, register

SCAN_EVERY_MS = 20000


def wifi_glyph(strength: int, secured: bool, size=20) -> Gtk.Widget:
    """Windows' list glyph: all arcs dimmed, the received ones solid, a lock badge if secured."""
    ov = Gtk.Overlay()
    ov.add_css_class("wifi-glyph")
    base = icon("fs-wifi-1-symbolic", size, "wifi-glyph-dim")
    ov.set_child(base)
    lvl = wb.signal_level(strength)
    top = icon(f"fs-wifi-{4 - lvl}-symbolic" if lvl < 3 else "fs-wifi-1-symbolic", size, "wifi-glyph-on")
    ov.add_overlay(top)
    if secured:
        lock = icon("fs-lock-badge-symbolic", 10, "wifi-glyph-lock")
        lock.set_halign(Gtk.Align.END)
        lock.set_valign(Gtk.Align.END)
        ov.add_overlay(lock)
    ov.set_valign(Gtk.Align.CENTER)
    return ov


def _copy(widget, text):
    widget.get_clipboard().set(text)
    toast(widget, _("Copied"))


def _error_text(att) -> str:
    if att.error == "read-only":
        return _("This action is disabled in read-only mode")
    if att.error == "wrong-key":
        if att.security == wb.EAP:
            return _("Can't connect to this network. Check your user name and password.")
        return _("The network security key isn't correct. Please try again.")
    return _("Can't connect to this network")


class NetworkRow(Gtk.Box):
    """One network in 'Show available networks'. Selecting it reveals the inline actions;
    secured networks ask for the key right in the row, as the Windows list does."""

    def __init__(self, page, net: wb.Network):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("wifi-net")
        self.page = page
        self.net = net
        self.key = net.key
        self.stage = "idle"     # idle | ssid | key | connecting
        self.error = None
        self.hidden_ssid = None
        self.selected = False
        head = Gtk.Box(spacing=12)
        head.add_css_class("wifi-net-head")
        self.glyph_slot = Gtk.Box()
        head.append(self.glyph_slot)
        self.glyph_slot.set_valign(Gtk.Align.CENTER)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        self.name_lbl = label("", "row-title", ellipsize=True)
        self.status_lbl = label("", "row-subtitle", ellipsize=True)
        texts.append(self.name_lbl)
        texts.append(self.status_lbl)
        head.append(texts)
        self.append(head)
        g = Gtk.GestureClick()
        g.connect("released", lambda *_: page.select(self))
        head.add_controller(g)
        head.set_cursor_from_name("default")
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.body.add_css_class("wifi-net-body")
        self.revealer = Gtk.Revealer(child=self.body, transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                     transition_duration=150)
        self.append(self.revealer)
        self.auto = Gtk.CheckButton(label=_("Connect automatically"))
        self.auto.set_active(True)
        self._glyph_key = None
        self.update(net)

    # ------------------------------------------------------------------ model
    def update(self, net):
        self.net = net
        gk = (wb.signal_level(net.strength), net.secured)
        if gk != self._glyph_key:
            self._glyph_key = gk
            clear(self.glyph_slot)
            self.glyph_slot.append(wifi_glyph(net.strength, net.secured))
        self.name_lbl.set_label(_("Hidden Network") if net.hidden else net.ssid)
        conn = net.best_connection()
        if conn is not None and self.stage == "idle":
            self.auto.set_active(bool(conn.get_setting_connection().get_autoconnect()))
        self._status()
        if net.state == "connected" and self.stage == "connecting":
            self.stage, self.error = "idle", None
        self._build_body()

    def _status(self):
        att = self.page.w.attempt
        if self.stage == "connecting":
            txt = _("Verifying and connecting") if att is not None and att.had_key else _("Connecting")
        elif self.error and self.stage == "idle":
            txt = self.error
        else:
            txt = self.net.status_text()
        self.status_lbl.set_label(txt)
        if self.net.state == "connected":
            self.add_css_class("connected")
        else:
            self.remove_css_class("connected")

    def set_selected(self, on):
        self.selected = on
        if on:
            self.add_css_class("selected")
        else:
            self.remove_css_class("selected")
            if self.stage in ("ssid", "key"):
                self.stage = "idle"
            self.error = None if self.stage == "idle" else self.error
        self._status()
        self._build_body()
        self.revealer.set_reveal_child(on)

    def busy(self):
        """True while the row holds typed text or an attempt (never rebuilt nor dropped)."""
        return self.stage in ("ssid", "key", "connecting")

    # ------------------------------------------------------------------ body
    def _build_body(self):
        sig = (self.stage, self.net.state, self.selected, self.error, self.net.known, self.net.secured)
        if getattr(self, "_body_sig", None) == sig:
            return
        self._body_sig = sig
        focus = None
        for w in list(self._iter(self.body)):
            self.body.remove(w)
        if self.auto.get_parent() is not None:
            self.auto.get_parent().remove(self.auto)
        if not self.selected:
            return
        b = self.body
        if self.stage == "connecting":
            b.append(self._buttons([(_("Cancel"), self._cancel, False)]))
        elif self.stage == "ssid":
            b.append(label(_("Enter the name (SSID) for the network"), "caption"))
            self.ssid_entry = Gtk.Entry()
            self.ssid_entry.add_css_class("fluent-entry")
            self.ssid_entry.set_halign(Gtk.Align.START)
            self.ssid_entry.set_size_request(400, -1)
            self.ssid_entry.set_text(self.hidden_ssid or "")
            b.append(self.ssid_entry)
            row = self._buttons([(_("Next"), self._ssid_next, True), (_("Cancel"), self._back, False)])
            nxt = row.get_first_child()
            ok = lambda *_: nxt.set_sensitive(0 < len(self.ssid_entry.get_text().encode()) <= 32)  # noqa: E731
            self.ssid_entry.connect("changed", ok)
            self.ssid_entry.connect("activate", lambda *_: nxt.get_sensitive() and self._ssid_next())
            ok()
            b.append(row)
            focus = self.ssid_entry
        elif self.stage == "key":
            sec = self.net.security
            if self.error:
                err = label(self.error, "wifi-error", wrap=True)
                b.append(err)
            self.user_entry = None
            if sec == wb.EAP:
                b.append(label(_("Enter your user name and password"), "caption"))
                self.user_entry = Gtk.Entry()
                self.user_entry.add_css_class("fluent-entry")
                self.user_entry.set_halign(Gtk.Align.START)
                self.user_entry.set_size_request(400, -1)
                self.user_entry.set_placeholder_text(_("User name"))
                b.append(self.user_entry)
            else:
                b.append(label(_("Enter the network security key"), "caption"))
            self.key_entry = Gtk.PasswordEntry()
            self.key_entry.set_show_peek_icon(True)
            self.key_entry.add_css_class("fluent-entry")
            self.key_entry.set_halign(Gtk.Align.START)
            self.key_entry.set_size_request(400, -1)
            if sec == wb.EAP:
                self.key_entry.set_property("placeholder-text", _("Password"))
            b.append(self.key_entry)
            row = self._buttons([(_("Next"), self._key_next, True), (_("Cancel"), self._back, False)])
            nxt = row.get_first_child()

            def ok(*_a):
                k = self.key_entry.get_text()
                good = wb.key_valid(sec, k) if sec != wb.EAP else bool(k) and bool(self.user_entry.get_text())
                nxt.set_sensitive(good)
            self.key_entry.connect("changed", ok)
            self.key_entry.connect("activate", lambda *_: nxt.get_sensitive() and self._key_next())
            if self.user_entry is not None:
                self.user_entry.connect("changed", ok)
                self.user_entry.connect("activate", lambda *_: self.key_entry.grab_focus())
            ok()
            b.append(row)
            focus = self.user_entry or self.key_entry
        elif self.net.state in ("connected", "connecting"):
            line = Gtk.Box(spacing=8)
            props = link(_("Properties"), self._properties)
            props.set_hexpand(True)
            line.append(props)
            line.append(button(_("Disconnect"), self._disconnect, css="wifi-btn"))
            b.append(line)
        else:
            if not self.net.secured and not self.net.hidden:
                b.append(label(_("Other people might be able to see info you send over this network"),
                               "caption", wrap=True))
            line = Gtk.Box(spacing=8)
            self.auto.set_hexpand(True)
            line.append(self.auto)
            line.append(button(_("Connect"), self._connect, accent=True, css="wifi-btn"))
            b.append(line)
        if focus is not None:
            GLib.idle_add(lambda: (focus.grab_focus(), False)[1])

    @staticmethod
    def _iter(box):
        c = box.get_first_child()
        while c is not None:
            yield c
            c = c.get_next_sibling()

    @staticmethod
    def _buttons(items):
        row = Gtk.Box(spacing=8, homogeneous=True)
        row.set_halign(Gtk.Align.END)
        for text, cb, accent in items:
            row.append(button(text, cb, accent=accent, css="wifi-btn"))
        return row

    # ------------------------------------------------------------------ actions
    def _connect(self):
        self.error = None
        if self.net.hidden:
            self.stage = "ssid"
        elif self.net.known or not self.net.secured:
            self._start()
            return
        else:
            self.stage = "key"
        self._refresh()

    def _ssid_next(self):
        self.hidden_ssid = self.ssid_entry.get_text()
        if self.net.secured:
            self.stage = "key"
            self._refresh()
        else:
            self._start()

    def _key_next(self):
        key = self.key_entry.get_text()
        user = self.user_entry.get_text() if self.user_entry is not None else None
        self._start(key=key, identity=user)

    def _start(self, key=None, identity=None):
        self.error = None
        self.stage = "connecting"
        self._refresh()
        self.page.w.connect(self.net, key=key, identity=identity, autoconnect=self.auto.get_active(),
                            hidden_ssid=self.hidden_ssid)

    def _back(self):
        self.stage, self.error = "idle", None
        self._refresh()

    def _cancel(self):
        self.page.w.cancel()
        self.stage, self.error = "idle", None
        self._refresh()

    def _disconnect(self):
        self.page.w.disconnect(lambda ok: ok or toast(self, _("This action is disabled in read-only mode")
                                                       if util.READ_ONLY else _("Couldn't disconnect")))

    def _properties(self):
        conn = self.net.best_connection()
        self.page.open_network(conn)

    def attempt_finished(self, att):
        """The backend finished our attempt: show the result in the row (Windows does too)."""
        if att.phase == "connected":
            self.stage, self.error = "idle", None
        elif att.phase == "failed":
            self.error = _error_text(att)
            self.stage = "key" if att.error == "wrong-key" else "idle"
        else:
            self.stage, self.error = "idle", None
        self._refresh()

    def _refresh(self):
        self._status()
        self._build_body()


@register
class WifiPage(Page):
    id = "wifi"
    parent = "network"
    title = "Wi-Fi"
    keywords = "wireless networks connect password ssid hidden known wlan"
    index = [
        ("wifi", "Wi-Fi", "on off"),
        ("available", "Show available networks", "scan list connect password"),
        ("hw-props", "Hardware properties", "adapter driver mac address"),
        ("known", "Manage known networks", "forget saved add network"),
    ]

    def build(self, box):
        self.w = wb.Wifi.get()
        self.rows: dict = {}
        self.sel_key = None
        self._scan_timer = 0
        g = self.group()
        self.g = g
        self.toggle_row = SettingRow(_("Wi-Fi"), None, "fs-wifi-1-symbolic", key="wifi")
        self.remember("wifi", self.toggle_row)
        self.toggle = ToggleSwitch(False, self._toggled)
        self.toggle_row.set_control(self.toggle)
        g.add(self.toggle_row)
        self.cur_row = SettingRow("", None, "fs-info-symbolic", chevron=True,
                                  on_click=lambda: self.open_network(self._cur_conn))
        self.cur_row.set_visible(False)
        self._cur_conn = None
        g.add(self.cur_row)
        refresh = Gtk.Button()
        refresh.set_child(icon("fs-arrow-clockwise-symbolic", 16))
        refresh.add_css_class("fluent-button")
        refresh.add_css_class("subtle-icon-button")
        refresh.set_tooltip_text(_("Refresh"))
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda *_: self.w.scan(force=True))
        self.avail = ExpanderRow(_("Show available networks"), None, "fs-wifi-1-symbolic", key="available",
                                 expanded=True, control=refresh)
        self.remember("available", self.avail)
        self.avail.revealer.connect("notify::reveal-child", lambda *_: self.w.scan())
        g.add(self.avail)
        self.placeholder = SettingRow(_("Searching…"), None, None, control=spinner())
        self.nav_row(g, "wifi-hardware", _("Hardware properties"), _("View and edit details for this adapter"),
                     "fs-options-symbolic", key="hw-props")
        self.nav_row(g, "wifi-known", _("Manage known networks"), _("Add, remove, and edit networks"),
                     "fs-history-symbolic", key="known")
        self.w.add_listener(self._update)
        box.connect("map", lambda *_: self._mapped(True))
        box.connect("unmap", lambda *_: self._mapped(False))

    def _mapped(self, on):
        if on and not self._scan_timer:
            self.w.scan()
            self._scan_timer = GLib.timeout_add(SCAN_EVERY_MS, lambda: (self.w.scan(), True)[1])
        elif not on and self._scan_timer:
            GLib.source_remove(self._scan_timer)
            self._scan_timer = 0

    def on_show(self):
        self.w.scan()
        self._update()

    def open_network(self, conn):
        if conn is None:
            return
        page = self.window.get_page("wifi-network")
        if page is not None:
            page.target_uuid = conn.get_uuid()
            self.go("wifi-network")

    def _toggled(self, on):
        def done(ok):
            if not ok:
                toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("The change was not applied"))
                self._update()
        self.w.set_enabled(on, done)

    # ------------------------------------------------------------------ live list
    def _update(self):
        if not self.w.ready:
            return
        if not self.w.available():
            self.toggle_row.set_control(label(_("Not available"), "row-value"))
            self.toggle_row.set_subtitle(_("NetworkManager isn't running") if self.w.error != "libnm"
                                         else _("NetworkManager's libnm is not installed"))
            self._set_rows([], _("Not available"))
            return
        if self.w.device() is None:
            self.toggle_row.set_control(label(_("Not available"), "row-value"))
            self.toggle_row.set_subtitle(_("No Wi-Fi adapter found"))
            self._set_rows([], _("No Wi-Fi adapter found"))
            self.cur_row.set_visible(False)
            return
        if self.toggle_row.control is not self.toggle:
            self.toggle_row.set_control(self.toggle)
        on = bool(self.w.enabled())
        self.toggle.set_active(on)
        self.toggle.set_sensitive(self.w.hardware_enabled())
        self.toggle_row.set_subtitle(None if self.w.hardware_enabled()
                                     else _("Wi-Fi is turned off by a hardware switch"))
        nets = self.w.networks() if on else []
        cur = next((n for n in nets if n.state == "connected"), None)
        self._cur_conn = cur.best_connection() if cur else None
        self.cur_row.set_visible(cur is not None and self._cur_conn is not None)
        if cur is not None:
            self.cur_row.set_title(_("{0} properties").format(cur.ssid))
            self.cur_row.set_subtitle(cur.status_text())
        if not on:
            self._set_rows([], _("Turn on Wi-Fi to see available networks"))
        else:
            self._set_rows(nets, None)
        att = self.w.attempt
        if att is not None and att.phase != "connecting":
            row = self.rows.get(att.key)
            self.w.clear_attempt()
            if row is not None:
                row.attempt_finished(att)

    def _set_rows(self, nets, message):
        content = self.avail.content
        keep = {}
        for n in nets:
            r = self.rows.get(n.key)
            if r is None:
                r = NetworkRow(self, n)
                r.add_css_class("nested")
            else:
                r.update(n)
            keep[n.key] = r
        # a row the user is typing in survives a scan that momentarily misses its network
        for k, r in self.rows.items():
            if k not in keep and r.busy() and nets:
                keep[k] = r
        for k, r in self.rows.items():
            if k not in keep and r.get_parent() is content:
                content.remove(r)
        self.rows = keep
        if self.sel_key not in keep:
            self.sel_key = None
        # placeholder row (searching / off / no adapter)
        if not keep:
            if self.placeholder.get_parent() is None:
                self.placeholder.add_css_class("nested")
                content.append(self.placeholder)
            searching = message is None
            self.placeholder.set_title(message or _("Searching…"))
            self.placeholder.set_control(spinner() if searching else None)
        elif self.placeholder.get_parent() is content:
            content.remove(self.placeholder)
        prev = None
        for r in keep.values():
            if r.get_parent() is None:
                content.append(r)
            content.reorder_child_after(r, prev)
            prev = r

    def select(self, row):
        old = self.rows.get(self.sel_key)
        if old is row:
            if not row.busy():
                row.set_selected(False)
                self.sel_key = None
            return
        if old is not None:
            if old.stage == "connecting":
                pass   # keep the attempt running (Windows does), just collapse
            old.set_selected(False)
        self.sel_key = row.key
        row.set_selected(True)


@register
class WifiKnownPage(Page):
    id = "wifi-known"
    parent = "wifi"
    title = "Manage known networks"
    keywords = "known saved networks forget add hidden"
    index = [("add-network", "Add a new network", "hidden ssid manual")]

    def build(self, box):
        self.w = wb.Wifi.get()
        g = self.group()
        add = SettingRow(_("Add a new network"), None, "fs-add-symbolic", key="add-network",
                         control=button(_("Add network"), self._add, accent=True))
        self.remember("add-network", add)
        g.add(add)
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("known-bar")
        self.search = Gtk.SearchEntry()
        self.search.add_css_class("fluent-entry")
        self.search.set_placeholder_text(_("Search"))
        self.search.set_size_request(260, -1)
        self.search.connect("search-changed", lambda *_: self._update())
        bar.append(self.search)
        spacer = Gtk.Box(hexpand=True)
        bar.append(spacer)
        bar.append(label(_("Sort by:"), "caption"))
        self.sort = Dropdown([("pref", _("Preference")), ("name", _("Name")), ("recent", _("Last connected"))],
                             "pref", lambda _v: self._update())
        self.sort.ui_only = "sorts the list (not a setting)"
        bar.append(self.sort)
        box.append(bar)
        self.list = self.group()
        self.w.add_listener(self._update)

    def on_show(self):
        self._update()

    def _update(self):
        if not self.w.ready:
            return
        self.list.clear()
        if not self.w.available():
            self.list.add(not_available_row(_("Known networks"), _("NetworkManager isn't running")))
            return
        q = self.search.get_text().strip().lower()
        conns = [c for c in self.w.wifi_connections()
                 if not q or q in wb.ssid_text(wb._bytes(c.get_setting_wireless().get_ssid())).lower()
                 or q in (c.get_id() or "").lower()]
        mode = self.sort.selected_id()
        ac = self.w.active_connection()
        ac_uuid = ac.get_uuid() if ac else None

        def ts(c):
            return c.get_setting_connection().get_timestamp() or 0
        if mode == "name":
            conns.sort(key=lambda c: wb.ssid_text(wb._bytes(c.get_setting_wireless().get_ssid())).lower())
        else:
            # Preference: the connected one, then auto-connecting ones by priority, then the rest
            conns.sort(key=lambda c: (c.get_uuid() != ac_uuid,
                                      0 if mode == "recent" else not c.get_setting_connection().get_autoconnect(),
                                      0 if mode == "recent" else -c.get_setting_connection().get_autoconnect_priority(),
                                      -ts(c)))
        if not conns:
            self.list.add(SettingRow(_("No known networks") if not q else _("No results found"), None, None))
        for c in conns:
            ssid = wb.ssid_text(wb._bytes(c.get_setting_wireless().get_ssid())) or c.get_id()
            fg = button(_("Forget"), lambda c=c: self._forget(c))
            self.list.add(SettingRow(ssid, None, "fs-wifi-1-symbolic", control=fg, chevron=True,
                                     on_click=lambda c=c: self._open(c)))

    def _open(self, conn):
        page = self.window.get_page("wifi-network")
        page.target_uuid = conn.get_uuid()
        self.go("wifi-network")

    def _forget(self, conn):
        ssid = wb._bytes(conn.get_setting_wireless().get_ssid())
        same = [c for c in self.w.wifi_connections() if wb._bytes(c.get_setting_wireless().get_ssid()) == ssid]

        def done(ok):
            if not ok:
                toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("Couldn't forget this network"))
        self.w.forget(same, done)

    def _add(self):
        add_network_dialog(self)


def add_network_dialog(page):
    """Windows' 'Add a new network' dialog."""
    w = wb.Wifi.get()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.add_css_class("add-network")
    box.append(label(_("Network name"), "caption"))
    name = Gtk.Entry()
    name.add_css_class("fluent-entry")
    box.append(name)
    box.append(label(_("Security type"), "caption"))
    sec = Dropdown([(wb.OPEN, C_("wifi", "Open")), (wb.WEP, "WEP"), (wb.PSK, "WPA2-Personal AES"),
                    (wb.SAE, "WPA3-Personal AES"), (wb.EAP, "WPA2-Enterprise AES")], wb.PSK)
    sec.set_halign(Gtk.Align.FILL)
    box.append(sec)
    key_lbl = label(_("Security key"), "caption")
    box.append(key_lbl)
    key = Gtk.PasswordEntry()
    key.set_show_peek_icon(True)
    key.add_css_class("fluent-entry")
    box.append(key)
    err = label("", "wifi-error", wrap=True)
    err.set_visible(False)
    box.append(err)
    auto = Gtk.CheckButton(label=_("Connect automatically"))
    auto.set_active(True)
    box.append(auto)
    hidden = Gtk.CheckButton(label=_("Connect even if this network is not broadcasting"))
    box.append(hidden)
    dlg = None

    def valid(*_a):
        s = sec.selected_id()
        needs = s in (wb.WEP, wb.PSK, wb.SAE)
        key_lbl.set_visible(needs)
        key.set_visible(needs)
        ok = 0 < len(name.get_text().encode()) <= 32 and (not needs or wb.key_valid(s, key.get_text()))
        if dlg is not None:
            dlg.primary_btn.set_sensitive(ok)
        return ok

    def resp(r):
        if r != "primary":
            return

        def done(ok, msg=None):
            if not ok:
                toast(page.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("Couldn't save this network"))
            else:
                toast(page.box, _("{0} was added").format(name.get_text()))
        s = sec.selected_id()
        w.add_network(name.get_text(), s, key.get_text() if s in (wb.WEP, wb.PSK, wb.SAE) else None,
                      autoconnect=auto.get_active(), hidden=hidden.get_active(), cb=done)

    dlg = ContentDialog(_("Add a new network"), None, primary=_("Save"), close=_("Cancel"), on_response=resp,
                        extra=box)
    for wdg in (name, key):
        wdg.connect("changed", valid)
    sec.connect("notify::selected", valid)
    valid()
    show_dialog(page.box, dlg)
    name.grab_focus()
    return dlg


def properties_card(page, rows_fn) -> Gtk.Box:
    """Windows' 'Properties' card: label/value pairs and a Copy button."""
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.add_css_class("setting-row")
    card.add_css_class("props-card")
    grid = Gtk.Grid(column_spacing=24, row_spacing=6, hexpand=True)
    top = Gtk.Box()
    top.append(grid)
    cp = button(_("Copy"), None, css="wifi-btn")
    cp.set_valign(Gtk.Align.START)
    top.append(cp)
    card.append(top)

    def fill():
        while grid.get_first_child() is not None:
            grid.remove(grid.get_first_child())
        rows = rows_fn()
        for i, (k, v) in enumerate(rows):
            kl = label(k + ":", "props-key")
            kl.set_valign(Gtk.Align.START)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(label(v, "props-value", selectable=True, wrap=True), 1, i, 1, 1)
        card.text = "\n".join(f"{k}:\t{v}" for k, v in rows)
        card.set_visible(bool(rows))
    cp.connect("clicked", lambda *_: _copy(card, card.text))
    card.fill = fill
    fill()
    return card


@register
class WifiNetworkPage(Page):
    """Properties of one saved network (Windows: Wi-Fi › <name> properties)."""
    id = "wifi-network"
    parent = "wifi"
    title = "Wi-Fi network"
    keywords = ""
    searchable = False

    target_uuid = None

    def tr_title(self):
        c = self._conn()
        return wb.ssid_text(wb._bytes(c.get_setting_wireless().get_ssid())) if c is not None else _(self.title)

    def _conn(self):
        if not self.target_uuid:
            return None
        for c in wb.Wifi.get().wifi_connections():
            if c.get_uuid() == self.target_uuid:
                return c
        return None

    def build(self, box):
        self.w = wb.Wifi.get()
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.content)
        self._shown = None
        self.w.add_listener(self._live)

    def on_show(self):
        self._shown = None
        self._render()

    def _live(self):
        if self.widget is not None and self.widget.get_mapped():
            c = self._conn()
            if c is None and self._shown is not None:
                self.window.go_back()    # forgotten elsewhere
                return
            if hasattr(self, "props_card"):
                self.props_card.fill()

    def _render(self):
        c = self._conn()
        clear(self.content)
        self.box_saved = self.box
        self.box = self.content   # self.group() appends to self.box
        try:
            if c is None:
                g = self.group()
                g.add(not_available_row(_("Wi-Fi network"), _("This network is no longer saved")))
                return
            self._shown = c.get_uuid()
            s_con = c.get_setting_connection()
            g = self.group()
            chk = Gtk.CheckButton(label=_("Connect automatically when in range"))
            chk.set_active(bool(s_con.get_autoconnect()))
            chk.connect("toggled", lambda b: self._set(c, autoconnect=b.get_active()))
            r = SettingRow("", None, None)
            r.texts.set_visible(False)
            r.prepend(chk)
            chk.set_hexpand(True)
            r.add_css_class("check-row")
            g.add(r)
            g2 = self.group()
            met = int(s_con.get_metered()) in (1, 3)   # yes / guess-yes
            g2.add(SettingRow(_("Metered connection"),
                              _("Some apps might work differently to reduce data usage when you're "
                                "connected to this network"), None,
                              control=ToggleSwitch(met, lambda v: self._set(c, metered=v))))
            sw = c.get_setting_wireless()
            mac = (sw.get_cloned_mac_address() or "") if sw is not None else ""
            g2.add(SettingRow(_("Random hardware addresses"),
                              _("Help protect your privacy by making it harder for people to track your device "
                                "location when you connect to this network. The setting takes effect the next "
                                "time you connect to this network."), None,
                              control=Dropdown([("off", _("Off")), ("on", _("On"))],
                                               "on" if mac in ("stable", "random") else "off",
                                               lambda v: self._set(c, mac_random=v == "on"))))
            g3 = self.group()
            ip, dns = self.w.ip_summary(c)
            for title, val in ((_("IP assignment:"), ip), (_("DNS server assignment:"), dns)):
                edit = button(_("Edit"), lambda: self._edit(c))
                edit.set_visible(util.have("nm-connection-editor"))
                row = SettingRow(title, None, None, control=edit)
                row.texts.append(label(val, "row-value"))
                g3.add(row)
            g4 = self.group()
            self.props_card = properties_card(self, lambda: self.w.details(c) if self._is_active(c) else [])
            g4.add(self.props_card)
            sec = c.get_setting_wireless_security()
            if sec is not None and (sec.get_key_mgmt() in ("wpa-psk", "sae", "none")):
                g5 = self.group()
                g5.add(SettingRow(_("View Wi-Fi security key"), None, None,
                                  control=button(_("View"), lambda: self._view_key(c))))
        finally:
            self.box = self.box_saved

    def _is_active(self, c):
        ac = self.w.active_connection()
        return ac is not None and ac.get_uuid() == c.get_uuid()

    def _set(self, c, **kw):
        def done(ok):
            if not ok:
                toast(self.content, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("The change was not applied"))
        self.w.update(c, done, **kw)

    def _edit(self, c):
        if not util.launch(["nm-connection-editor", f"--edit={c.get_uuid()}"]) and util.READ_ONLY:
            toast(self.content, _("This action is disabled in read-only mode"))

    def _view_key(self, c):
        def got(key):
            if key is None:
                toast(self.content, _("The security key isn't available"))
                return
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            lb = label(key, ["key-value", "body-strong"], selectable=True)
            box.append(lb)
            dlg = ContentDialog(_("View {0} security key").format(self.tr_title()), None,
                                primary=_("Copy"), close=_("Close"),
                                on_response=lambda r: r == "primary" and _copy(self.content, key), extra=box)
            show_dialog(self.content, dlg)
        self.w.get_key(c, got)


@register
class WifiHardwarePage(Page):
    id = "wifi-hardware"
    parent = "wifi"
    title = "Hardware properties"
    keywords = "adapter driver mac address protocol band channel link speed"

    def build(self, box):
        self.w = wb.Wifi.get()
        g = self.group()
        self.card = properties_card(self, self._detail_rows)
        g.add(self.card)
        self.none = not_available_row(_("Wi-Fi"), _("No Wi-Fi adapter found"))
        g.add(self.none)
        self.w.add_listener(self._live)

    def _detail_rows(self):
        return self.w.details() if self.w.device() is not None else []

    def _live(self):
        self.card.fill()
        self.none.set_visible(self.w.ready and self.w.device() is None)

    def on_show(self):
        self._live()


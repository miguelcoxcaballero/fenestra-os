"""Network pages: Wi-Fi list, offline explanation and "checking for updates"."""

import time

from gi.repository import GLib, Gtk

from ..backends import run_async
from ..i18n import _
from .base import Page


def _signal_icon(signal: int) -> str:
    if signal >= 75:
        level = "excellent"
    elif signal >= 50:
        level = "good"
    elif signal >= 25:
        level = "ok"
    else:
        level = "weak"
    return f"network-wireless-signal-{level}-symbolic"


class WifiRow(Gtk.ListBoxRow):
    def __init__(self, page, net):
        super().__init__(css_classes=["wifi-row"])
        self.page = page
        self.net = net
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top = Gtk.Box(spacing=14)
        top.append(Gtk.Box(css_classes=["indicator"], valign=Gtk.Align.CENTER))
        top.append(Gtk.Image(icon_name=_signal_icon(net.signal), pixel_size=20, css_classes=["wifi-icon"]))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        text.append(Gtk.Label(label=net.ssid, xalign=0, ellipsize=3, css_classes=["wifi-name"]))
        self.status = Gtk.Label(xalign=0, css_classes=["wifi-status"])
        text.append(self.status)
        top.append(text)
        outer.append(top)

        self.revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                     transition_duration=180)
        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, css_classes=["wifi-detail"])
        self.password = None
        if net.secure and not net.in_use:
            detail.append(Gtk.Label(label=_("Enter the network security key"), xalign=0,
                                    css_classes=["field-label"]))
            self.password = Gtk.PasswordEntry(show_peek_icon=True, css_classes=["oobe-entry"])
            self.password.connect("activate", lambda *_: self.connect_clicked())
            self.password.connect("changed", lambda *_: self._sync_button())
            detail.append(self.password)
        self.error = Gtk.Label(xalign=0, wrap=True, css_classes=["error-text"], visible=False)
        detail.append(self.error)
        btns = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        self.spinner = Gtk.Spinner(visible=False)
        btns.append(self.spinner)
        self.button = Gtk.Button(label=_("Connect"), css_classes=["oobe-button", "primary"])
        self.button.connect("clicked", lambda *_: self.connect_clicked())
        btns.append(self.button)
        detail.append(btns)
        self.revealer.set_child(detail)
        outer.append(self.revealer)
        self.set_child(outer)
        self.refresh()

    def refresh(self):
        if self.net.in_use:
            self.status.set_label(_("Connected, secured") if self.net.secure else _("Connected"))
            self.button.set_visible(False)
        else:
            self.status.set_label(_("Secured") if self.net.secure else _("Open"))
        self._sync_button()

    def _sync_button(self):
        if self.password is not None:
            self.button.set_sensitive(len(self.password.get_text()) >= 1)

    def connect_clicked(self):
        if self.net.in_use:
            return
        pw = self.password.get_text() if self.password is not None else None
        if self.password is not None and not pw:
            return
        self.error.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()
        self.button.set_sensitive(False)
        self.status.set_label(_("Connecting…"))
        run_async(self.page.backends.network.connect, self.net.ssid, pw, callback=self._done)

    def _done(self, _result, error):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.button.set_sensitive(True)
        if error is not None:
            self.error.set_label(_("Can't connect to this network. Check the security key and try again."))
            self.error.set_visible(True)
            self.refresh()
            return
        self.net.in_use = True
        self.refresh()
        self.revealer.set_reveal_child(False)
        self.page.on_connected()


class NetworkPage(Page):
    page_id = "network"
    illustration = "network"

    def __init__(self, ctx):
        super().__init__(ctx, _("Let's connect you to a network"),
                         _("You'll need an internet connection to continue setting up your device. "
                           "Once connected, you'll get the latest features and security updates."))
        self.primary_label = _("Next")
        self.link_label = _("I don't have internet")
        self.primary_sensitive = False
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["oobe-list", "wifi-list"])
        self.listbox.connect("row-selected", self._on_row_selected)
        self.listbox.set_placeholder(Gtk.Label(label=_("Looking for networks…"), css_classes=["dim", "placeholder"]))
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
                                           child=self.listbox, css_classes=["oobe-list-frame"])
        self.body.append(self.scroller)
        self._scanning = False
        self._refresh_id = 0

    def should_skip(self):
        net = self.backends.network
        if net.wired_connected() or net.connectivity() == "full":
            self.state.online = True
            return True
        return False

    def on_enter(self, direction):
        self.scan()
        if not self._refresh_id:
            self._refresh_id = GLib.timeout_add_seconds(12, self._periodic)

    def on_leave(self):
        if self._refresh_id:
            GLib.source_remove(self._refresh_id)
            self._refresh_id = 0

    def _periodic(self):
        sel = self.listbox.get_selected_row()
        if sel is None or not sel.revealer.get_reveal_child():
            self.scan()
        return True

    def scan(self):
        if self._scanning:
            return
        self._scanning = True
        if not self.backends.network.has_wifi():
            self._scanning = False
            self.listbox.set_placeholder(Gtk.Label(
                label=_("No Wi‑Fi adapter was found. Plug in a network cable or continue without internet."),
                wrap=True, css_classes=["dim", "placeholder"]))
            return
        run_async(self.backends.network.scan, callback=self._scanned)

    def _scanned(self, nets, error):
        self._scanning = False
        if error is not None or nets is None:
            nets = []
        while (row := self.listbox.get_row_at_index(0)) is not None:
            self.listbox.remove(row)
        if not nets:
            self.listbox.set_placeholder(Gtk.Label(label=_("No networks found"),
                                                   css_classes=["dim", "placeholder"]))
        for net in nets:
            self.listbox.append(WifiRow(self, net))
        if any(n.in_use for n in nets):
            self.state.online = True
            self.set_primary_sensitive(True)

    def _on_row_selected(self, _lb, row):
        i = 0
        while (r := self.listbox.get_row_at_index(i)) is not None:
            r.revealer.set_reveal_child(r is row and not r.net.in_use)
            i += 1
        if row is not None and row.password is not None:
            GLib.idle_add(lambda: (row.password.grab_focus(), False)[1])

    def on_connected(self):
        self.state.online = True
        self.set_primary_sensitive(True)

    def on_link(self):
        self.ctx.goto("network-offline")


class OfflinePage(Page):
    page_id = "network-offline"
    illustration = "network"
    branch = True

    def __init__(self, ctx):
        super().__init__(ctx, _("There's more to discover when you connect to the internet"),
                         _("Connect now to get the latest features and security updates. "
                           "You can still set up your device without an internet connection and connect later."))
        self.primary_label = _("Connect now")
        self.secondary_label = _("Continue with limited setup")
        for icon, text in (
            ("software-update-available-symbolic", _("Get the latest updates and security fixes")),
            ("preferences-system-time-symbolic", _("Set the right date and time automatically")),
            ("system-software-install-symbolic", _("Install apps from the Software center")),
        ):
            row = Gtk.Box(spacing=14, css_classes=["benefit-row"])
            row.append(Gtk.Image(icon_name=icon, pixel_size=20, css_classes=["benefit-icon"]))
            row.append(Gtk.Label(label=text, xalign=0, wrap=True))
            self.body.append(row)

    def on_primary(self):
        self.ctx.back()

    def on_secondary(self):
        self.state.online = False
        self.ctx.next()


class UpdatesPage(Page):
    page_id = "updates"
    illustration = "updates"
    can_go_back = False
    transient = True
    MIN_SECONDS = 3.0

    def __init__(self, ctx):
        super().__init__(ctx, "")
        self.make_spinner_layout(_("Checking for updates"))

    def should_skip(self):
        return not self.state.online

    def on_enter(self, direction):
        if self.ctx.screenshot_mode:
            return
        self.spinner.start()
        start = time.monotonic()

        def check():
            result = self.backends.network.connectivity(check=True)
            elapsed = time.monotonic() - start
            if elapsed < self.MIN_SECONDS:
                time.sleep(self.MIN_SECONDS - elapsed)
            return result

        run_async(check, callback=self._done)

    def _done(self, result, _error):
        self.spinner.stop()
        if self.ctx.current_page is self:
            self.ctx.next()

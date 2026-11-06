"""Home page (device hero + recommendation cards)."""
from __future__ import annotations

from gi.repository import Gtk

from .. import theme
from ..backends import appearance, bluetooth
from ..i18n import _
from ..widgets import SettingRow, button, clear, label, link
from .base import Page, register
from .common import device_hero, theme_preview

@register
class HomePage(Page):
    id = "home"
    title = "Home"
    keywords = "start overview recommended"

    def build(self, box):
        box.append(device_hero(self))
        cols = Gtk.Box(spacing=16, homogeneous=True)
        cols.add_css_class("home-grid")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        cols.append(left)
        cols.append(right)
        box.append(cols)
        left.append(self._recommended())
        left.append(self._personalize())
        right.append(self._bluetooth())
        right.append(self._update_card())

    def _card(self, title, text=None):
        c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        c.add_css_class("home-card")
        c.set_valign(Gtk.Align.FILL)
        c.append(label(title, "home-card-title"))
        if text:
            c.append(label(text, "home-card-text", wrap=True))
        return c

    def _recommended(self):
        c = self._card(_("Recommended settings"), _("Recent and commonly used settings"))
        items = [
            ("display", _("Display"), "fs-desktop-symbolic"),
            ("sound", _("Sound"), "fs-speaker-2-symbolic"),
            ("power", _("Power & battery"), "fs-battery-charge-symbolic"),
            ("wifi", _("Wi-Fi"), "fs-wifi-1-symbolic"),
        ]
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        inner.set_margin_top(8)
        for pid, t, ic in items:
            inner.append(SettingRow(t, None, ic, chevron=True, on_click=lambda p=pid: self.go(p)))
        c.append(inner)
        return c

    def _bluetooth(self):
        c = self._card(_("Bluetooth devices"), _("Manage, add, and remove devices"))
        self.bt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.bt_box.set_margin_top(8)
        c.append(self.bt_box)
        foot = Gtk.Box(spacing=16)
        foot.set_margin_top(8)
        foot.append(link(_("View all devices"), lambda: self.go("devices")))
        foot.append(link(_("Add device"), lambda: self.go("bt-devices")))
        c.append(foot)
        self._load_bt()
        return c

    def _load_bt(self):
        def got(adapter, powered, devs):
            clear(self.bt_box)
            if adapter is None:
                self.bt_box.append(SettingRow(_("Bluetooth"), _("Not available on this device"),
                                              "fs-bluetooth-symbolic"))
                return
            sw_row = SettingRow(_("Bluetooth"), _("Discoverable as \"{0}\"").format(
                __import__("fenestra_settings.backends.system_info", fromlist=["x"]).hostname()) if powered else _("Off"), "fs-bluetooth-symbolic")
            from ..widgets import ToggleSwitch
            sw_row.set_control(ToggleSwitch(powered, lambda v: bluetooth.set_powered(
                adapter, v, lambda *_: self._load_bt())))
            self.bt_box.append(sw_row)
            for d in [d for d in devs if d.paired][:3]:
                self.bt_box.append(SettingRow(d.name, _("Connected") if d.connected else _("Paired"),
                                              d.kind_icon))
        bluetooth.state(got)

    def _personalize(self):
        c = self._card(_("Personalize your device"), _("Select a theme to apply"))
        row = Gtk.Box(spacing=12)
        row.set_margin_top(12)
        dark_now = theme.get().dark
        for dark in (False, True):
            b = Gtk.Button()
            b.add_css_class("theme-thumb")
            if dark == dark_now:
                b.add_css_class("selected")
            b.set_child(theme_preview(dark, 132, 84))
            b.set_tooltip_text(_("Dark") if dark else _("Light"))
            b.connect("clicked", lambda _b, d=dark: appearance.set_color_scheme("dark" if d else "light"))
            row.append(b)
        c.append(row)
        from ..widgets import Dropdown
        mode = Dropdown([("light", _("Light")), ("dark", _("Dark"))], "dark" if dark_now else "light",
                        appearance.set_color_scheme)
        r = SettingRow(_("Color mode"), None, "fs-dark-theme-symbolic", control=mode)
        r.set_margin_top(8)
        c.append(r)
        foot = Gtk.Box(spacing=16)
        foot.set_margin_top(4)
        foot.append(link(_("Browse more backgrounds"), lambda: self.go("background")))
        foot.append(link(_("Colors"), lambda: self.go("colors")))
        c.append(foot)
        return c

    def _update_card(self):
        from ..backends import packages
        c = self._card(_("Fenestra Update"))
        t = packages.last_checked()
        if packages.offline_pending():
            txt = _("Updates are ready. Restart to finish installing.")
        elif t:
            txt = _("Last checked: {0}").format(
                __import__("gi").repository.GLib.DateTime.new_from_unix_local(int(t)).format("%x %H:%M"))
        else:
            txt = _("Keep your device up to date with the latest features and security fixes.")
        c.append(label(txt, "home-card-text", wrap=True))
        b = button(_("Check for updates"), lambda: self.go("update"), accent=True)
        b.set_halign(Gtk.Align.START)
        b.set_margin_top(16)
        c.append(b)
        return c

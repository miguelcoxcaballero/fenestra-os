"""Bluetooth & devices."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import util
from ..backends import bluetooth, system_info
from ..i18n import _
from ..widgets import (Dropdown, SettingRow, Slider, ToggleSwitch, button, clear, icon, label,
                       not_available_row, spinner, toast)
from .base import Page, register
from .common import gsetting_dropdown, gsetting_toggle

MOUSE = "org.gnome.desktop.peripherals.mouse"
TOUCHPAD = "org.gnome.desktop.peripherals.touchpad"
MEDIA = "org.gnome.desktop.media-handling"


class BluetoothMixin:
    """Shared Bluetooth state rendering used by the landing page and the Devices page."""

    def bt_init(self, group, list_group=None, show_all=False):
        self.bt_group = group
        self.bt_list = list_group
        self.bt_show_all = show_all
        self.bt_adapter = None
        self.bt_row = SettingRow(_("Bluetooth"), _("Checking…"), "fs-bluetooth-symbolic", key="bluetooth")
        self.remember("bluetooth", self.bt_row)
        group.add(self.bt_row)
        self.bt_refresh()

    def bt_refresh(self):
        bluetooth.state(self._bt_got)

    def _bt_got(self, adapter, powered, devs):
        self.bt_adapter = adapter
        if adapter is None:
            self.bt_row.set_subtitle(_("No Bluetooth adapter found"))
            self.bt_row.set_control(label(_("Not available"), "row-value"))
            if self.bt_list is not None:
                clear(self.bt_list.rows)
            return
        self.bt_row.set_subtitle(_("Discoverable as \"{0}\"").format(system_info.hostname()) if powered
                                 else _("Off"))
        self.bt_row.set_control(ToggleSwitch(powered, lambda v: bluetooth.set_powered(
            adapter, v, lambda *_: GLib.timeout_add(600, lambda: (self.bt_refresh(), False)[1]))))
        if self.bt_list is None:
            return
        self.bt_list.clear()
        shown = [d for d in devs if d.paired or self.bt_show_all]
        if not powered:
            self.bt_list.add(SettingRow(_("Turn on Bluetooth to see your devices"), None, "fs-info-symbolic"))
            return
        if not shown:
            self.bt_list.add(SettingRow(_("No devices paired yet"), _("Select \"Add device\" to pair one"),
                                        "fs-info-symbolic"))
        for d in shown:
            sub = _("Connected") if d.connected else (_("Paired") if d.paired else _("Available"))
            if d.battery is not None:
                sub += f" · {d.battery}%"
            ctrl = Gtk.Box(spacing=8)
            if d.paired:
                ctrl.append(button(_("Disconnect") if d.connected else _("Connect"),
                                   lambda dev=d: self._bt_toggle(dev), css="small"))
                ctrl.append(button(_("Remove"), lambda dev=d: self._bt_remove(dev), css="small"))
            else:
                ctrl.append(button(_("Pair"), lambda dev=d: self._bt_pair(dev), css="small"))
            self.bt_list.add(SettingRow(d.name, sub, d.kind_icon, control=ctrl))

    def _bt_done(self, ok, msg=None):
        if not ok:
            toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                  else _("The operation did not complete"))
        GLib.timeout_add(800, lambda: (self.bt_refresh(), False)[1])

    def _bt_toggle(self, d):
        (bluetooth.disconnect if d.connected else bluetooth.connect)(d, lambda ok, *_: self._bt_done(ok))

    def _bt_remove(self, d):
        from ..widgets import confirm
        confirm(self.box, _("Remove this device?"), d.name, _("Yes"),
                lambda: bluetooth.remove(self.bt_adapter, d, lambda ok, *_: self._bt_done(ok)))

    def _bt_pair(self, d):
        bluetooth.pair(d, lambda ok, *_: self._bt_done(ok))


@register
class DevicesPage(BluetoothMixin, Page):
    id = "devices"
    title = "Bluetooth & devices"
    keywords = "bluetooth mouse touchpad printers keyboard pen usb camera"
    index = [("bluetooth", "Bluetooth", "on off wireless")]

    def build(self, box):
        tiles = Gtk.FlowBox()
        tiles.set_selection_mode(Gtk.SelectionMode.NONE)
        tiles.set_homogeneous(True)
        tiles.set_min_children_per_line(1)
        tiles.set_max_children_per_line(4)
        tiles.set_column_spacing(8)
        tiles.set_row_spacing(8)
        tiles.add_css_class("device-tiles")
        self.tiles = tiles
        box.append(tiles)
        g = self.group()
        self.bt_init(g)
        self.nav_row(g, "bt-devices", _("Devices"), _("Mouse, keyboard, pen, audio, displays and docks, other devices"),
                     "fs-phone-laptop-symbolic")
        self.ext_row(g, _("Printers & scanners"), _("Preferences, troubleshoot"), "fs-print-symbolic",
                     ["gnome-control-center", "printers"], key="printers")
        self.nav_row(g, "cameras", _("Cameras"), _("Connected cameras, default image settings"),
                     "fs-camera-symbolic")
        self.nav_row(g, "mouse", _("Mouse"), _("Buttons, mouse pointer speed, scrolling"), "fs-cursor-symbolic")
        self.nav_row(g, "touchpad", _("Touchpad"), _("Taps, gestures, scrolling, zooming"), "fs-hand-left-symbolic")
        self.ext_row(g, _("Pen & tablet"), _("Wacom tablets and styluses"), "fs-pen-symbolic",
                     ["gnome-control-center", "wacom"])
        self.nav_row(g, "autoplay", _("AutoPlay"), _("Defaults for removable drives and memory cards"),
                     "fs-arrow-sync-symbolic")
        self.ext_row(g, _("Keyboard"), _("Shortcuts, special characters"), "fs-keyboard-symbolic",
                     ["gnome-control-center", "keyboard"])

    def _bt_got(self, adapter, powered, devs):
        super()._bt_got(adapter, powered, devs)
        clear(self.tiles)
        if not powered:
            self.tiles.set_visible(False)
            return
        paired = [d for d in devs if d.paired][:3]
        self.tiles.set_visible(True)
        for d in paired:
            t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            t.add_css_class("device-tile")
            ic = icon(d.kind_icon, 32, "row-icon")
            ic.set_halign(Gtk.Align.START)
            t.append(ic)
            t.append(label(d.name, "body-strong", ellipsize=True))
            t.append(label(_("Connected") if d.connected else _("Not connected"), "caption"))
            self.tiles.append(t)
        add = Gtk.Button()
        add.add_css_class("device-tile")
        add.add_css_class("add-tile")
        ab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        ab.append(icon("fs-bluetooth-symbolic", 24, "accent-icon"))
        ab.append(label(_("Add device"), xalign=0.5))
        add.set_child(ab)
        add.connect("clicked", lambda *_: self.go("bt-devices"))
        self.tiles.append(add)

    def on_show(self):
        self.bt_refresh()


@register
class BtDevicesPage(BluetoothMixin, Page):
    id = "bt-devices"
    parent = "devices"
    title = "Devices"
    keywords = "pair add bluetooth device headphones"
    index = [("add-device", "Add device", "pair bluetooth new")]

    def build(self, box):
        g = self.group()
        self.add_row = SettingRow(_("Add device"), _("Search for nearby Bluetooth devices"),
                                  "fs-bluetooth-symbolic",
                                  control=button(_("Add device"), self._scan, accent=True), key="add-device")
        self.remember("add-device", self.add_row)
        g.add(self.add_row)
        lg = self.group(_("Devices"))
        self.bt_init(g, lg, show_all=False)
        self.found_group = self.group(_("Available devices"))
        self.found_group.set_visible(False)

    def _scan(self):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        self.add_row.set_control(spinner())
        self.add_row.set_subtitle(_("Searching for devices…"))

        def done(*_a):
            self.add_row.set_control(button(_("Add device"), self._scan, accent=True))
            self.add_row.set_subtitle(_("Search for nearby Bluetooth devices"))
            bluetooth.state(self._found)
        bluetooth.scan(10, done)

    def _found(self, adapter, powered, devs):
        self.found_group.clear()
        new = [d for d in devs if not d.paired]
        self.found_group.set_visible(True)
        if not new:
            self.found_group.add(SettingRow(_("No new devices found"), None, "fs-info-symbolic"))
        for d in new:
            self.found_group.add(SettingRow(d.name, d.address, d.kind_icon,
                                            control=button(_("Pair"), lambda dev=d: self._bt_pair(dev),
                                                           css="small")))

    def on_show(self):
        self.bt_refresh()


@register
class MousePage(Page):
    id = "mouse"
    parent = "devices"
    title = "Mouse"
    keywords = "pointer speed scroll primary button left right acceleration"
    index = [
        ("primary", "Primary mouse button", "left right handed"),
        ("speed", "Mouse pointer speed", "sensitivity"),
        ("accel", "Enhance pointer precision", "acceleration"),
        ("natural", "Scrolling direction", "natural reverse"),
    ]

    def build(self, box):
        g = self.group()
        if not util.has_key(MOUSE, "left-handed"):
            g.add(not_available_row(_("Mouse")))
            return
        dd = Dropdown([(False, _("Left")), (True, _("Right"))], util.gget(MOUSE, "left-handed"),
                      lambda v: util.gset(MOUSE, "left-handed", v))
        g.add(self.remember("primary", SettingRow(_("Primary mouse button"), None, "fs-cursor-symbolic",
                                                  control=dd)))
        sl = Slider(-1, 1, util.gget(MOUSE, "speed", 0.0), lambda v: util.gset(MOUSE, "speed", v), step=0.05,
                    show_value=False, width=200)
        g.add(self.remember("speed", SettingRow(_("Mouse pointer speed"), None, "fs-top-speed-symbolic",
                                                control=sl)))
        if util.has_key(MOUSE, "accel-profile"):
            t = ToggleSwitch(util.gget(MOUSE, "accel-profile") != "flat",
                             lambda v: util.gset(MOUSE, "accel-profile", "default" if v else "flat"))
            g.add(self.remember("accel", SettingRow(_("Enhance pointer precision"),
                                                    _("Mouse acceleration"), "fs-cursor-symbolic", control=t)))
        g2 = self.group(_("Scrolling"))
        nat = gsetting_dropdown(MOUSE, "natural-scroll", [(False, _("Down motion scrolls down")),
                                                          (True, _("Down motion scrolls up"))])
        if nat:
            g2.add(self.remember("natural", SettingRow(_("Scrolling direction"), None, "fs-arrow-sync-symbolic",
                                                       control=nat)))
        g3 = self.group(_("Related settings"))
        g3.add(SettingRow(_("Mouse pointer"), _("Pointer size and style"), "fs-cursor-symbolic", chevron=True,
                          on_click=lambda: self.go("pointer")))


@register
class TouchpadPage(Page):
    id = "touchpad"
    parent = "devices"
    title = "Touchpad"
    keywords = "tap click gestures scroll two finger trackpad"
    index = [
        ("touchpad", "Touchpad", "enable disable"),
        ("tap", "Tap to click", "taps"),
        ("tp-speed", "Cursor speed", "touchpad speed"),
        ("tp-natural", "Natural scrolling", "scroll direction"),
        ("two-finger", "Two-finger scrolling", "edge scroll"),
    ]

    def build(self, box):
        g = self.group()
        if not util.has_key(TOUCHPAD, "send-events"):
            g.add(not_available_row(_("Touchpad")))
            return
        t = ToggleSwitch(util.gget(TOUCHPAD, "send-events") != "disabled",
                         lambda v: util.gset(TOUCHPAD, "send-events", "enabled" if v else "disabled"))
        g.add(self.remember("touchpad", SettingRow(_("Touchpad"), None, "fs-hand-left-symbolic", control=t)))
        sl = Slider(-1, 1, util.gget(TOUCHPAD, "speed", 0.0), lambda v: util.gset(TOUCHPAD, "speed", v),
                    step=0.05, show_value=False, width=200)
        g.add(self.remember("tp-speed", SettingRow(_("Cursor speed"), None, "fs-top-speed-symbolic", control=sl)))
        g2 = self.group(_("Taps"))
        tap = gsetting_toggle(TOUCHPAD, "tap-to-click")
        if tap:
            g2.add(self.remember("tap", SettingRow(_("Tap with a single finger to single-click"), None,
                                                   "fs-hand-left-symbolic", control=tap)))
        dis = gsetting_toggle(TOUCHPAD, "disable-while-typing")
        if dis:
            g2.add(SettingRow(_("Disable touchpad while typing"), None, "fs-keyboard-symbolic", control=dis))
        g3 = self.group(_("Scroll & zoom"))
        tf = gsetting_toggle(TOUCHPAD, "two-finger-scrolling-enabled")
        if tf:
            g3.add(self.remember("two-finger", SettingRow(_("Drag two fingers to scroll"), None,
                                                          "fs-hand-left-symbolic", control=tf)))
        nat = gsetting_dropdown(TOUCHPAD, "natural-scroll", [(False, _("Down motion scrolls down")),
                                                             (True, _("Down motion scrolls up"))])
        if nat:
            g3.add(self.remember("tp-natural", SettingRow(_("Scrolling direction"), None,
                                                          "fs-arrow-sync-symbolic", control=nat)))


@register
class CamerasPage(Page):
    id = "cameras"
    parent = "devices"
    title = "Cameras"
    keywords = "webcam video"

    def build(self, box):
        import glob
        g = self.group(_("Connected cameras"))
        names = ["Integrated Camera"] if util.DEMO else []
        for d in ([] if util.DEMO else sorted(glob.glob("/sys/class/video4linux/video*"))):
            n = util.read_file(d + "/name")
            if n and n not in names:
                names.append(n)
        if not names:
            g.add(SettingRow(_("No cameras found"), None, "fs-camera-symbolic"))
        for n in names:
            g.add(SettingRow(n, None, "fs-camera-symbolic"))
        g2 = self.group(_("Related settings"))
        g2.add(SettingRow(_("Camera privacy settings"), None, "fs-shield-symbolic", chevron=True,
                          on_click=lambda: self.go("camera")))


@register
class AutoPlayPage(Page):
    id = "autoplay"
    parent = "devices"
    title = "AutoPlay"
    keywords = "removable drive usb autorun media"

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(MEDIA, "autorun-never", invert=True)
        if t:
            g.add(SettingRow(_("Use AutoPlay for all media and devices"), None, "fs-arrow-sync-symbolic",
                             control=t))
        else:
            g.add(not_available_row(_("AutoPlay")))
        auto = gsetting_toggle(MEDIA, "automount-open")
        if auto:
            g.add(SettingRow(_("Open a window when a drive is connected"), None, "fs-folder-symbolic",
                             control=auto))

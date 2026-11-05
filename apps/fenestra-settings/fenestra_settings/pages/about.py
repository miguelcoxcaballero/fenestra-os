"""System › About."""
from __future__ import annotations

from gi.repository import Gdk, Gtk

from .. import util
from ..backends import system_info
from ..i18n import _
from ..widgets import ExpanderRow, SettingRow, button, label, link, toast
from .base import Page, register
from .common import rename_dialog, wallpaper_thumb


class SpecGrid(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("spec-grid")
        self.set_hexpand(True)
        self.values = []

    def add(self, key, value):
        row = Gtk.Box(spacing=24)
        k = label(key, "spec-key")
        k.set_valign(Gtk.Align.START)
        k.set_size_request(150, -1)
        v = label(value, "spec-value", wrap=True, selectable=True)
        v.set_hexpand(True)
        row.append(k)
        row.append(v)
        self.append(row)
        self.values.append((key, v))
        return v

    def text(self):
        return "\n".join(f"{k}\t{v.get_label()}" for k, v in self.values)


@register
class AboutPage(Page):
    id = "about"
    parent = "system"
    title = "About"
    keywords = "specifications specs version cpu ram memory processor gpu device name hostname rename"
    index = [
        ("device-specs", "Device specifications", "processor ram cpu memory system type"),
        ("os-specs", "Fenestra specifications", "version edition build kernel"),
        ("rename", "Rename this PC", "hostname device name computer name"),
    ]

    def build(self, box):
        head = Gtk.Box(spacing=16)
        head.add_css_class("card")
        head.add_css_class("about-head")
        head.append(wallpaper_thumb(96, 60, "hero-thumb"))
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        self.name_lbl = label(system_info.hostname(), "subtitle-text", ellipsize=True)
        tb.append(self.name_lbl)
        mdl = system_info.model()
        if mdl:
            tb.append(label(mdl, "caption"))
        head.append(tb)
        rb = button(_("Rename this PC"), lambda: rename_dialog(self, self.name_lbl))
        head.append(rb)
        head.key = "rename"
        self._rows["rename"] = head
        box.append(head)

        g = self.group()
        g.set_margin_top(4)
        dev = ExpanderRow(_("Device specifications"), None, "fs-laptop-symbolic", key="device-specs",
                          control=button(_("Copy"), lambda: self._copy(self.dev_grid), css="small"),
                          expanded=True)
        self.remember("device-specs", dev)
        grid = SpecGrid()
        self.dev_grid = grid
        grid.add(_("Device name"), system_info.hostname())
        grid.add(_("Processor"), system_info.cpu())
        grid.add(_("Installed RAM"), system_info.ram_usable_str())
        self.gpu_lbl = grid.add(_("Graphics"), _("Detecting…"))
        did = system_info.device_id()
        if did:
            grid.add(_("Device ID"), did)
        grid.add(_("System type"), system_info.system_type())
        grid.add(_("Pen and touch"), system_info.pen_touch())
        wrap = Gtk.Box()
        wrap.add_css_class("plain")
        wrap.append(grid)
        dev.add(wrap)
        links = Gtk.Box(spacing=24)
        links.add_css_class("plain")
        links.append(label(_("Related links"), "caption"))
        links.append(link(_("Advanced system settings"), lambda: util.open_control_center("system")))
        links.append(link(_("System monitor"), lambda: util.launch(["gnome-system-monitor"])))
        dev.add(links)
        g.add(dev)
        system_info.gpu(lambda names: self.gpu_lbl.set_label("\n".join(names) if names else _("Unknown")))

        osi = system_info.os_info()
        osx = ExpanderRow(_("Fenestra specifications"), None, "fs-window-symbolic", key="os-specs",
                          control=button(_("Copy"), lambda: self._copy(self.os_grid), css="small"),
                          expanded=True)
        self.remember("os-specs", osx)
        grid2 = SpecGrid()
        self.os_grid = grid2
        grid2.add(_("Edition"), osi["edition"])
        grid2.add(_("Version"), osi["version"])
        if osi["installed"]:
            grid2.add(_("Installed on"), osi["installed"])
        grid2.add(_("Based on"), osi["base"])
        grid2.add(_("Kernel"), osi["kernel"])
        grid2.add(_("Uptime"), system_info.uptime())
        w2 = Gtk.Box()
        w2.add_css_class("plain")
        w2.append(grid2)
        osx.add(w2)
        g.add(osx)

        g2 = self.group(_("Related"))
        g2.add(SettingRow(_("Fenestra Update"), _("Check for updates and install them"),
                          "fs-arrow-sync-symbolic", chevron=True, on_click=lambda: self.go("update")))
        g2.add(SettingRow(_("Storage"), _("Disk usage and cleanup"), "fs-hard-drive-symbolic",
                          chevron=True, on_click=lambda: self.go("storage")))
        if osi.get("support_url") or osi.get("home_url"):
            url = osi.get("support_url") or osi.get("home_url")
            g2.add(SettingRow(_("Get help"), url, "fs-info-symbolic", external=True,
                              on_click=lambda: util.open_uri(url)))

    def _copy(self, grid):
        Gdk.Display.get_default().get_clipboard().set(grid.text())
        toast(self.box, _("Copied to clipboard"))

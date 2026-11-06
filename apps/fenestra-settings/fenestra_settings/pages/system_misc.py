"""Smaller System sub-pages: Nearby sharing, Multitasking, Troubleshoot, Recovery,
Projecting to this PC, Clipboard."""
from __future__ import annotations

import os

from gi.repository import Gdk, GLib

from .. import util
from ..i18n import _
from ..widgets import SettingRow, button, label, not_available_row, toast
from .base import Page, register
from .common import gsetting_dropdown, gsetting_toggle, infobar

MUTTER = "org.gnome.mutter"
WM = "org.gnome.desktop.wm.preferences"
SHELL_APP_SWITCHER = "org.gnome.shell.app-switcher"
IFACE = "org.gnome.desktop.interface"


@register
class NearbyPage(Page):
    id = "nearby"
    parent = "system"
    title = "Nearby sharing"
    keywords = "share files bluetooth wifi send receive"

    def build(self, box):
        g = self.group()
        g.add(SettingRow(_("Nearby sharing"),
                         _("Share files with nearby devices using Bluetooth or the local network"),
                         "fs-share-symbolic"))
        self.ext_row(g, _("File sharing"), _("Share your Public folder on the local network"),
                     "fs-folder-symbolic", ["gnome-control-center", "sharing"])
        self.ext_row(g, _("Send files via Bluetooth"), _("Choose a paired device and send files"),
                     "fs-bluetooth-symbolic", ["bluetooth-sendto"])
        g2 = self.group(_("Save files I receive to"))
        dl = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        if util.DEMO or not dl:
            dl = "~/Downloads"
        else:
            dl = dl.replace(GLib.get_home_dir(), "~", 1)
        g2.add(SettingRow(dl or "~/Downloads", None, "fs-folder-symbolic"))


@register
class MultitaskingPage(Page):
    id = "multitasking"
    parent = "system"
    title = "Multitasking"
    keywords = "snap windows desktops workspaces alt tab title bar shake"
    index = [
        ("snap", "Snap windows", "edge tiling drag"),
        ("desktops", "Desktops", "workspaces virtual"),
        ("dynamic", "Dynamic workspaces", "automatic desktops"),
        ("alttab", "Alt + Tab", "switcher current workspace"),
        ("hot-corner", "Hot corner", "activities top left"),
    ]

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(MUTTER, "edge-tiling")
        r = SettingRow(_("Snap windows"), _("Drag windows to the edges of the screen to resize them"),
                       "fs-window-multiple-symbolic", control=t, key="snap") if t else \
            not_available_row(_("Snap windows"))
        self.remember("snap", r)
        g.add(r)
        t2 = gsetting_toggle(IFACE, "enable-hot-corners")
        if t2:
            r = SettingRow(_("Hot corner"), _("Touch the top-left corner to open the activities overview"),
                           "fs-window-apps-symbolic", control=t2, key="hot-corner")
            self.remember("hot-corner", r)
            g.add(r)

        g2 = self.group(_("Desktops"))
        g2.key = "desktops"
        self._rows["desktops"] = g2
        dyn = gsetting_toggle(MUTTER, "dynamic-workspaces")
        if dyn:
            r = SettingRow(_("Dynamic workspaces"), _("Automatically remove empty desktops"),
                           "fs-window-multiple-symbolic", control=dyn, key="dynamic")
            self.remember("dynamic", r)
            g2.add(r)
        if util.has_key(WM, "num-workspaces"):
            dd = gsetting_dropdown(WM, "num-workspaces", [(i, str(i)) for i in range(1, 9)], cast=int)
            g2.add(SettingRow(_("Number of desktops"), _("Used when dynamic workspaces are off"),
                              "fs-grid-symbolic", control=dd))
        wo = gsetting_toggle(MUTTER, "workspaces-only-on-primary")
        if wo:
            g2.add(SettingRow(_("Desktops on all displays"), _("Only switch desktops on the primary display"),
                              "fs-dual-screen-symbolic", control=wo))
        if util.has_key(SHELL_APP_SWITCHER, "current-workspace-only"):
            dd = gsetting_dropdown(SHELL_APP_SWITCHER, "current-workspace-only",
                                   [(True, _("Only the desktop I'm using")), (False, _("All desktops"))])
            r = SettingRow(_("Alt + Tab"), _("Show windows from"), "fs-window-apps-symbolic", control=dd,
                           key="alttab")
            self.remember("alttab", r)
            g2.add(r)


@register
class TroubleshootPage(Page):
    id = "troubleshoot"
    parent = "system"
    title = "Troubleshoot"
    keywords = "fix problems logs diagnostics"

    def build(self, box):
        box.append(infobar(_("Troubleshooters can find and fix many common problems."), None))
        g = self.group(_("Other troubleshooters"))
        g.set_margin_top(18)
        items = [
            (_("Internet connections"), _("Check your network status and connections"),
             "fs-wifi-1-symbolic", lambda: self.go("network")),
            (_("Audio"), _("Check sound devices and volume"), "fs-speaker-2-symbolic",
             lambda: self.go("sound")),
            (_("Fenestra Update"), _("Check for and install updates"), "fs-arrow-sync-symbolic",
             lambda: self.go("update")),
            (_("Bluetooth"), _("Check Bluetooth adapters and devices"), "fs-bluetooth-symbolic",
             lambda: self.go("bt-devices")),
        ]
        for t, s, ic, cb in items:
            g.add(SettingRow(t, s, ic, control=button(_("Run"), cb, css="small")))
        g2 = self.group(_("Logs"))
        self.ext_row(g2, _("System logs"), _("View the system journal"), "fs-document-symbolic",
                     ["gnome-logs"])
        self.ext_row(g2, _("System monitor"), _("Processes and resources"), "fs-data-usage-symbolic",
                     ["gnome-system-monitor"])


@register
class RecoveryPage(Page):
    id = "recovery"
    parent = "system"
    title = "Recovery"
    keywords = "reset restart firmware uefi bios advanced startup snapshot"

    def build(self, box):
        box.append(infobar(_("If you're having problems with your PC, these recovery options might help."),
                           None))
        g = self.group(_("Recovery options"))
        g.set_margin_top(18)
        g.add(SettingRow(_("Fix problems without resetting your PC"),
                         _("Resetting can take a while — first, try resolving issues by running a troubleshooter"),
                         "fs-wrench-symbolic", chevron=True, on_click=lambda: self.go("troubleshoot")))

        def fw():
            if util.READ_ONLY:
                toast(self.box, _("This action is disabled in read-only mode"))
                return
            from ..widgets import confirm
            confirm(self.box, _("Restart to firmware settings?"),
                    _("Your PC will restart into the UEFI firmware setup. Save your work first."),
                    _("Restart now"),
                    lambda: util.run_async(["systemctl", "reboot", "--firmware-setup"], None, mutating=True))
        g.add(SettingRow(_("Advanced startup"),
                         _("Restart your device to change startup settings, including firmware settings"),
                         "fs-arrow-counterclockwise-symbolic",
                         control=button(_("Restart now"), fw)))
        if util.have("snapper") or util.have("timeshift"):
            tool = "timeshift-launcher" if util.have("timeshift-launcher") else "timeshift"
            self.ext_row(g, _("System snapshots"), _("Go back to an earlier state of the system"),
                         "fs-history-symbolic", [tool])
        g.add(SettingRow(_("Reset this PC"),
                         _("Choose to keep or remove your personal files, then reset Fenestra without reinstalling"),
                         "fs-arrow-reset-symbolic", control=button(_("Reset PC"), self._reset)))

    RESET = "/usr/libexec/fenestra/fenestra-reset"

    def _reset(self):
        """Like the reference: choose an option, confirm, then restart to reset."""
        from ..widgets import ContentDialog, show_dialog
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        if not os.path.exists(self.RESET) or not util.have("pkexec"):
            toast(self.box, _("Resetting is not available on this system"))
            return

        def chosen(resp):
            if resp not in ("primary", "secondary"):
                return
            mode = "keep" if resp == "primary" else "all"
            if mode == "keep":
                title = _("Ready to reset this PC")
                body = _("Resetting will:\n• Remove all apps you installed (Flatpak)\n"
                         "• Change settings back to their defaults\n"
                         "• Keep your personal files\n\nYour PC will restart. This might take a few minutes.")
            else:
                title = _("Ready to reset this PC")
                body = _("Resetting will:\n• Remove all user accounts and all personal files\n"
                         "• Remove all apps you installed (Flatpak), saved Wi-Fi networks, fingerprints and face data\n"
                         "• Change settings back to their defaults\n\n"
                         "Your PC will restart and set up again as new. This can't be undone.")

            def go():
                util.run_async(["pkexec", self.RESET, "request", mode], None, mutating=True)
            from ..widgets import confirm
            confirm(self.box, title, body, _("Reset"), go, destructive=True)

        show_dialog(self.box, ContentDialog(
            _("Choose an option"),
            _("Keep my files: removes apps and settings, but keeps your personal files.\n\n"
              "Remove everything: removes all of your personal files, apps, and settings."),
            primary=_("Keep my files"), secondary=_("Remove everything"), close=_("Cancel"),
            on_response=chosen))


@register
class ProjectingPage(Page):
    id = "projecting"
    parent = "system"
    title = "Projecting to this PC"
    keywords = "cast miracast screen mirror remote desktop"

    def build(self, box):
        g = self.group()
        g.add(SettingRow(_("Projecting to this PC"),
                         _("Receiving wireless displays is not supported. Use Remote Desktop to share this screen."),
                         "fs-phone-desktop-symbolic"))
        self.ext_row(g, _("Remote Desktop"), _("Let other devices connect to this PC"), "fs-desktop-mac-symbolic",
                     ["gnome-control-center", "system"])
        if util.have("gnome-network-displays"):
            self.ext_row(g, _("Cast to a wireless display"), _("Project this PC to a TV or monitor"),
                         "fs-tv-symbolic", ["gnome-network-displays"])


@register
class ClipboardPage(Page):
    id = "clipboard"
    parent = "system"
    title = "Clipboard"
    keywords = "copy paste history clear"
    index = [("clear", "Clear clipboard data", "erase copy")]

    def build(self, box):
        g = self.group()
        hist = SettingRow(_("Clipboard history"),
                          _("Save multiple items to the clipboard to use later"),
                          "fs-clipboard-symbolic")
        if util.have("gnome-extensions"):
            hist.set_control(label(_("Managed by the clipboard extension"), "row-value"))
        g.add(hist)

        def clear():
            Gdk.Display.get_default().get_clipboard().set("")
            Gdk.Display.get_default().get_primary_clipboard().set("")
            toast(self.box, _("Clipboard cleared"))
        r = SettingRow(_("Clear clipboard data"), _("Clear everything (except pinned items) on this device"),
                       "fs-delete-symbolic", control=button(_("Clear"), clear), key="clear")
        self.remember("clear", r)
        g.add(r)


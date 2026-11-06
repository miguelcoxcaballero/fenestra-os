"""Fenestra section: Linux-only settings the reference UI doesn't have, rendered natively."""
from __future__ import annotations

from gi.repository import Gdk, Gtk

from .. import util
from ..backends import linux, system_info
from ..i18n import N_, _
from ..widgets import (ContentDialog, SettingRow, ToggleSwitch, button, confirm, icon, label,
                       not_available_row, show_dialog, spinner, toast)
from .base import Page, register
from .common import gsetting_dropdown, gsetting_toggle

MUTTER = "org.gnome.mutter"
WM = "org.gnome.desktop.wm.preferences"
IFACE = "org.gnome.desktop.interface"
SHELL = "org.gnome.shell"
SEARCH = "org.gnome.desktop.search-providers"
DING = "org.gnome.shell.extensions.ding"
SWITCHER = "org.gnome.shell.app-switcher"
WMKEYS = "org.gnome.desktop.wm.keybindings"
SHELLKEYS = "org.gnome.shell.keybindings"
MEDIAKEYS = "org.gnome.settings-daemon.plugins.media-keys"
MUTTERKEYS = "org.gnome.mutter.keybindings"


def ro_toast(page, ok=True):
    if not ok:
        toast(page.box, _("This action is disabled in read-only mode") if util.READ_ONLY
              else _("The change was not applied"))


@register
class FenestraPage(Page):
    id = "fenestra"
    title = "Fenestra"
    keywords = "linux gnome advanced extensions workspaces shortcuts sharing search online accounts"
    ROWS_DESKTOP = [
        ("fx-workspaces", N_("Workspaces"), N_("Dynamic workspaces, number of desktops, hot corner"),
         "fs-window-multiple-symbolic"),
        ("fx-windows", N_("Window behavior"), N_("Focus mode, title bar actions and buttons"), "fs-window-symbolic"),
        ("fx-desktop-icons", N_("Desktop icons"), N_("Home, trash and drives on the desktop, icon size"),
         "fs-desktop-symbolic"),
        ("fx-extensions", N_("Extensions"), N_("Turn shell extensions on or off and change their settings"),
         "fs-apps-symbolic"),
    ]
    ROWS_SYSTEM = [
        ("fx-search", N_("Search"), N_("Which apps show results in search"), "fs-search-symbolic"),
        ("fx-online-accounts", N_("Online accounts"), N_("Mail, calendar, contacts and files from online services"),
         "fs-mail-symbolic"),
        ("fx-sharing", N_("Sharing"), N_("Remote desktop and file sharing"), "fs-share-symbolic"),
        ("fx-shortcuts", N_("Keyboard shortcuts"), N_("View and change desktop shortcuts"), "fs-keyboard-symbolic"),
        ("fx-hardware", N_("Printers, tablets & color"), N_("Printers, drawing tablets and color profiles"),
         "fs-print-symbolic"),
    ]

    def build(self, box):
        g = self.group(_("Desktop"))
        for pid, t, s, ic in self.ROWS_DESKTOP:
            self.nav_row(g, pid, _(t), _(s), ic)
        g2 = self.group(_("System"))
        for pid, t, s, ic in self.ROWS_SYSTEM:
            self.nav_row(g2, pid, _(t), _(s), ic)
        g3 = self.group(_("More"))
        self.ext_row(g3, _("Advanced (GNOME Settings)"), _("Open GNOME Settings for anything not available here"),
                     "fs-settings-symbolic", ["gnome-control-center"], key="gnome-settings")


@register
class WorkspacesPage(Page):
    id = "fx-workspaces"
    parent = "fenestra"
    title = "Workspaces"
    keywords = "virtual desktops dynamic number primary display hot corner"

    def build(self, box):
        g = self.group()
        for schema, key, title, sub, ic, inv in (
                (MUTTER, "dynamic-workspaces", _("Dynamic workspaces"), _("Automatically remove empty desktops"),
                 "fs-window-multiple-symbolic", False),
                (MUTTER, "workspaces-only-on-primary", _("Workspaces on all displays"),
                 _("Switch desktops on every display, not only the primary one"), "fs-dual-screen-symbolic", True),
                (IFACE, "enable-hot-corners", _("Hot corner"), _("Touch the top-left corner to open the overview"),
                 "fs-window-apps-symbolic", False),
                (MUTTER, "edge-tiling", _("Snap windows"), _("Drag windows to screen edges to tile them"),
                 "fs-window-multiple-symbolic", False)):
            t = gsetting_toggle(schema, key, invert=inv)
            if t:
                g.add(SettingRow(title, sub, ic, control=t))
        dd = gsetting_dropdown(WM, "num-workspaces", [(i, str(i)) for i in range(1, 13)], cast=int)
        if dd:
            g.add(SettingRow(_("Number of desktops"), _("Used when dynamic workspaces are off"), "fs-grid-symbolic",
                             control=dd))
        sw = gsetting_dropdown(SWITCHER, "current-workspace-only",
                               [(True, _("Only the desktop I'm using")), (False, _("All desktops"))])
        if sw:
            g.add(SettingRow(_("Alt + Tab shows windows from"), None, "fs-window-apps-symbolic", control=sw))


@register
class WindowBehaviorPage(Page):
    id = "fx-windows"
    parent = "fenestra"
    title = "Window behavior"
    keywords = "focus follows mouse titlebar double click buttons minimize maximize close center new windows"

    TITLEBAR = [("toggle-maximize", N_("Maximize")), ("toggle-maximize-horizontally", N_("Maximize horizontally")),
                ("toggle-maximize-vertically", N_("Maximize vertically")), ("minimize", N_("Minimize")),
                ("toggle-shade", N_("Shade")), ("lower", N_("Lower")), ("menu", N_("Window menu")),
                ("none", N_("Nothing"))]
    LAYOUTS = [("appmenu:minimize,maximize,close", N_("Right: minimize, maximize, close")),
               ("appmenu:close", N_("Right: close only")),
               ("close,minimize,maximize:appmenu", N_("Left: close, minimize, maximize"))]

    def build(self, box):
        g = self.group(_("Focus"))
        fm = gsetting_dropdown(WM, "focus-mode", [("click", _("Click to focus")), ("sloppy", _("Focus on hover")),
                                                   ("mouse", _("Focus follows mouse"))])
        if fm:
            g.add(SettingRow(_("Activate windows"), None, "fs-cursor-symbolic", control=fm, key="focus-mode"))
        ar = gsetting_toggle(WM, "auto-raise")
        if ar:
            g.add(SettingRow(_("Raise windows when they are focused"), None, "fs-window-symbolic", control=ar,
                             key="auto-raise"))
        g2 = self.group(_("Title bars"))
        opts = [(k, _(v)) for k, v in self.TITLEBAR]
        for key, rkey, title in (("action-double-click-titlebar", "titlebar-double", _("Double-click")),
                                 ("action-middle-click-titlebar", "titlebar-middle", _("Middle-click")),
                                 ("action-right-click-titlebar", "titlebar-right", _("Secondary click"))):
            dd = gsetting_dropdown(WM, key, opts)
            if dd:
                g2.add(SettingRow(title, None, "fs-window-symbolic", control=dd, key=rkey))
        # button-layout is also read by GTK (client-side decorations), so it works in both sessions
        bl = gsetting_dropdown(WM, "button-layout", [(k, _(v)) for k, v in self.LAYOUTS])
        if bl:
            g2.add(SettingRow(_("Title bar buttons"), None, "fs-window-symbolic", control=bl, key="button-layout"))
        g3 = self.group(_("Windows"))
        for schema, key, rkey, title in (
                (MUTTER, "center-new-windows", "center-new", _("Center new windows")),
                (MUTTER, "attach-modal-dialogs", "attach-modal", _("Attach dialogs to their parent window")),
                (WM, "resize-with-right-button", "resize-right", _("Resize windows with the secondary button"))):
            t = gsetting_toggle(schema, key)
            if t:
                g3.add(SettingRow(title, None, "fs-window-symbolic", control=t, key=rkey))
        mod = gsetting_dropdown(WM, "mouse-button-modifier", [("<Super>", "Super"), ("<Alt>", "Alt"),
                                                               ("", _("Disabled"))])
        if mod:
            g3.add(SettingRow(_("Key to move windows with the mouse"), None, "fs-keyboard-symbolic", control=mod,
                              key="move-modifier"))


@register
class DesktopIconsPage(Page):
    id = "fx-desktop-icons"
    parent = "fenestra"
    title = "Desktop icons"
    keywords = "ding home trash volumes drives icon size desktop"
    SIZES = {"tiny": N_("Tiny"), "small": N_("Small"), "standard": N_("Medium"), "large": N_("Large")}
    CORNERS = {"top-left": N_("Top left"), "top-right": N_("Top right"), "bottom-left": N_("Bottom left"),
               "bottom-right": N_("Bottom right")}

    def build(self, box):
        g = self.group()
        if util.settings(DING) is None:
            g.add(not_available_row(_("Desktop icons"), _("The desktop icons extension is not installed")))
            return
        for key, title, ic in (("show-home", _("Show the personal folder"), "fs-home-symbolic"),
                               ("show-trash", _("Show the trash"), "fs-delete-symbolic"),
                               ("show-volumes", _("Show external drives"), "fs-hard-drive-symbolic"),
                               ("show-network-volumes", _("Show network drives"), "fs-globe-symbolic"),
                               ("keep-arranged", _("Keep icons arranged"), "fs-grid-symbolic")):
            t = gsetting_toggle(DING, key)
            if t:
                g.add(SettingRow(title, None, ic, control=t))
        for key, title, labels in (("icon-size", _("Icon size"), self.SIZES),
                                   ("start-corner", _("New icons start at"), self.CORNERS)):
            ch = util.key_choices(DING, key)
            if ch:
                dd = gsetting_dropdown(DING, key, [(c, _(labels.get(c, c.replace("-", " ").title()))) for c in ch])
                g.add(SettingRow(title, None, "fs-desktop-symbolic", control=dd))


@register
class ExtensionsPage(Page):
    id = "fx-extensions"
    parent = "fenestra"
    title = "Extensions"
    keywords = "gnome shell extensions plugins addons"

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(SHELL, "disable-user-extensions", invert=True)
        if t:
            g.add(SettingRow(_("Use extensions"), _("Turn all user extensions on or off"), "fs-apps-symbolic",
                             control=t))
        self.list = self.group(_("Installed extensions"))
        self.list.add(SettingRow(_("Loading…"), None, None, control=spinner()))
        g3 = self.group(_("Related"))
        for cmd in ("extension-manager", "gnome-extensions-app"):
            if util.have(cmd):
                self.ext_row(g3, _("Get more extensions"), None, "fs-arrow-download-symbolic", [cmd])
                break
        self.refresh()

    def on_show(self):
        if hasattr(self, "list"):
            self.refresh()

    def refresh(self):
        linux.extensions(self._got)

    def _got(self, exts):
        self.list.clear()
        if exts is None:
            self.list.add(not_available_row(_("Extensions"), _("GNOME Shell is not running")))
            return
        for e in exts:
            ctrl = Gtk.Box(spacing=12)
            if e.has_prefs:
                ctrl.append(button(_("Settings"), lambda u=e.uuid: linux.open_extension_prefs(
                    u, lambda ok, *_: ro_toast(self, ok)), css="small"))
            ctrl.append(ToggleSwitch(e.enabled, lambda v, u=e.uuid: linux.set_extension_enabled(
                u, v, lambda ok, *_: (ro_toast(self, ok), self.refresh()))))
            sub = e.uuid if not e.description else e.description.splitlines()[0][:90]
            self.list.add(SettingRow(e.name, sub, "fs-apps-symbolic", control=ctrl))


@register
class SearchPage(Page):
    id = "fx-search"
    parent = "fenestra"
    title = "Search"
    keywords = "search providers results overview apps"

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(SEARCH, "disable-external", invert=True, on_after=lambda v: self._fill())
        if t is None:
            g.add(not_available_row(_("Search")))
            return
        g.add(SettingRow(_("App search results"), _("Let apps show results when you search"), "fs-search-symbolic",
                         control=t))
        self.list = self.group(_("Search locations"))
        util.gconnect(SEARCH, "sort-order", self._fill)
        util.gconnect(SEARCH, "disabled", self._fill)
        self._fill()

    def _order(self, provs):
        order = list(util.gget(SEARCH, "sort-order", []) or [])
        rank = {d: i for i, d in enumerate(order)}
        return sorted(provs, key=lambda p: (rank.get(p.desktop_id, 999), p.name.lower()))

    def _fill(self):
        self.list.clear()
        disabled = set(util.gget(SEARCH, "disabled", []) or [])
        off_all = util.gget(SEARCH, "disable-external", False)
        provs = self._order(linux.search_providers())
        for i, p in enumerate(provs):
            img = Gtk.Image.new_from_gicon(p.icon) if p.icon else icon("fs-app-generic-symbolic")
            img.set_pixel_size(24)
            ctrl = Gtk.Box(spacing=6)
            up = button("↑", lambda idx=i, ps=provs: self._move(ps, idx, -1), css="small", sensitive=i > 0)
            down = button("↓", lambda idx=i, ps=provs: self._move(ps, idx, 1), css="small",
                          sensitive=i < len(provs) - 1)
            ctrl.append(up)
            ctrl.append(down)
            ctrl.append(ToggleSwitch(p.desktop_id not in disabled, lambda v, d=p.desktop_id: self._toggle(d, v),
                                     sensitive=not off_all))
            self.list.add(SettingRow(p.name, None, image=img, control=ctrl))

    def _toggle(self, did, on):
        disabled = list(util.gget(SEARCH, "disabled", []) or [])
        enabled = list(util.gget(SEARCH, "enabled", []) or [])
        if on:
            disabled = [d for d in disabled if d != did]
            if did not in enabled:
                enabled.append(did)
        else:
            if did not in disabled:
                disabled.append(did)
            enabled = [d for d in enabled if d != did]
        ok = util.gset(SEARCH, "disabled", disabled) and util.gset(SEARCH, "enabled", enabled)
        ro_toast(self, ok)

    def _move(self, provs, idx, delta):
        ids = [p.desktop_id for p in provs]
        j = idx + delta
        if 0 <= j < len(ids):
            ids[idx], ids[j] = ids[j], ids[idx]
            ro_toast(self, util.gset(SEARCH, "sort-order", ids))


@register
class OnlineAccountsPage(Page):
    id = "fx-online-accounts"
    parent = "fenestra"
    title = "Online accounts"
    keywords = "google microsoft nextcloud email calendar contacts goa"

    def build(self, box):
        g = self.group()
        g.add(SettingRow(_("Add an account"), _("Connect mail, calendar, contacts and files"), "fs-people-symbolic",
                         control=button(_("Add account"), self._add, accent=True), key="add-account"))
        self.list = self.group(_("Your accounts"))
        self.refresh()

    def on_show(self):
        if hasattr(self, "list"):
            self.refresh()

    def refresh(self):
        linux.online_accounts(self._got)

    def _got(self, accts):
        self.list.clear()
        if accts is None:
            self.list.add(not_available_row(_("Online accounts"), _("GNOME Online Accounts is not running")))
            return
        if not accts:
            self.list.add(SettingRow(_("No accounts yet"), None, "fs-info-symbolic"))
        for a in accts:
            sub = a.identity + (" · " + _("Needs attention") if a.attention else "")
            self.list.add(SettingRow(a.provider, sub, "fs-mail-symbolic",
                                     control=button(_("Remove"), lambda acct=a: self._remove(acct), css="small")))

    def _remove(self, a):
        confirm(self.box, _("Remove this account?"), f"{a.provider} — {a.identity}", _("Remove"),
                lambda: linux.remove_online_account(a, lambda ok, *_: (ro_toast(self, ok), self.refresh())))

    def _add(self):
        # The only external window we accept: GNOME's online-accounts sign-in dialog.
        if not util.launch(["gnome-control-center", "online-accounts"]):
            ro_toast(self, False)


@register
class SharingPage(Page):
    id = "fx-sharing"
    parent = "fenestra"
    title = "Sharing"
    keywords = "remote desktop rdp vnc file sharing webdav device name"

    def build(self, box):
        g = self.group()
        g.add(SettingRow(_("Device name"), system_info.hostname(), "fs-laptop-symbolic", chevron=True,
                         on_click=lambda: self.go("about", "rename")))
        self.rdp = SettingRow(_("Remote desktop"), _("Let other devices control this desktop with RDP"),
                              "fs-desktop-mac-symbolic", control=spinner(), key="remote-desktop")
        g.add(self.rdp)
        self.files = SettingRow(_("File sharing"), _("Share your Public folder on the local network"),
                                "fs-folder-symbolic", control=spinner())
        g.add(self.files)
        self.refresh()

    def on_show(self):
        if hasattr(self, "rdp"):
            self.refresh()

    def refresh(self):
        if "remote-desktop" not in self.hidden_keys():
            linux.remote_desktop_status(self._rdp)
        linux.file_sharing_status(self._fs)

    def _rdp(self, st):
        if not st.get("available"):
            self.rdp.set_control(label(_("Not available"), "row-value"))
            return
        on = st["rdp_enabled"]
        self.rdp.set_subtitle(_("Let other devices control this desktop with RDP") +
                              (f" · {_('Port')} {st.get('port', '3389')}" if on else ""))
        self.rdp.set_control(ToggleSwitch(on, lambda v: linux.set_remote_desktop(
            v, lambda ok, *_: (ro_toast(self, ok), linux.remote_desktop_status(self._rdp)))))

    def _fs(self, st):
        if not st.get("available"):
            self.files.set_control(label(_("Not installed"), "row-value"))
            return
        self.files.set_control(ToggleSwitch(st["active"], lambda v: linux.set_file_sharing(
            v, lambda ok, *_: (ro_toast(self, ok), linux.file_sharing_status(self._fs)))))


SHORTCUTS = [
    (N_("Windows"), [(WMKEYS, "close", N_("Close window")), (WMKEYS, "minimize", N_("Minimize window")),
                     (WMKEYS, "toggle-maximized", N_("Maximize or restore window")),
                     (WMKEYS, "toggle-fullscreen", N_("Full screen")),
                     (WMKEYS, "show-desktop", N_("Show desktop")),
                     (WMKEYS, "switch-applications", N_("Switch apps")),
                     (WMKEYS, "switch-windows", N_("Switch windows")),
                     (MUTTERKEYS, "toggle-tiled-left", N_("Snap window left")),
                     (MUTTERKEYS, "toggle-tiled-right", N_("Snap window right"))]),
    (N_("Desktops"), [(WMKEYS, "switch-to-workspace-left", N_("Switch to the desktop on the left")),
                      (WMKEYS, "switch-to-workspace-right", N_("Switch to the desktop on the right")),
                      (WMKEYS, "move-to-workspace-left", N_("Move window one desktop to the left")),
                      (WMKEYS, "move-to-workspace-right", N_("Move window one desktop to the right"))]),
    (N_("System"), [(SHELLKEYS, "toggle-overview", N_("Show the overview")),
                    (SHELLKEYS, "toggle-message-tray", N_("Show the notification list")),
                    (SHELLKEYS, "toggle-quick-settings", N_("Open quick settings")),
                    (SHELLKEYS, "show-screenshot-ui", N_("Take a screenshot")),
                    (WMKEYS, "panel-run-dialog", N_("Run a command")),
                    (WMKEYS, "switch-input-source", N_("Switch keyboard layout")),
                    (MEDIAKEYS, "screensaver", N_("Lock screen")),
                    (MEDIAKEYS, "logout", N_("Sign out")),
                    (MEDIAKEYS, "home", N_("Open the home folder")),
                    (MEDIAKEYS, "control-center", N_("Open Settings"))]),
]


def accel_label(accels):
    out = []
    for a in accels:
        if not a:
            continue
        ok, key, mods = Gtk.accelerator_parse(a)
        out.append(Gtk.accelerator_get_label(key, mods) if ok and key else a)
    return ", ".join(out) if out else _("Disabled")


@register
class ShortcutsPage(Page):
    id = "fx-shortcuts"
    parent = "fenestra"
    title = "Keyboard shortcuts"
    keywords = "keybindings hotkeys keys accelerators"

    def build(self, box):
        self.rows = []
        for section, items in SHORTCUTS:
            g = self.group(_(section))
            for schema, key, title in items:
                if not util.has_key(schema, key):
                    continue
                r = SettingRow(_(title), None, "fs-keyboard-symbolic")
                ctrl = Gtk.Box(spacing=8)
                val = label("", "row-value", ellipsize=True, xalign=1.0)
                val.set_max_width_chars(22)
                val.set_width_chars(10)
                ctrl.append(val)
                ctrl.append(button(_("Edit"), lambda s=schema, k=key, t=title: self._edit(s, k, t), css="small"))
                ctrl.append(button(_("Reset"), lambda s=schema, k=key: ro_toast(self, util.greset(s, k)), css="small"))
                r.set_control(ctrl)
                g.add(r)
                self._show(val, schema, key)
                util.gconnect(schema, key, lambda v=val, s=schema, k=key: self._show(v, s, k))

    @staticmethod
    def _get(schema, key):
        v = util.gget(schema, key)
        return [v] if isinstance(v, str) else list(v or [])

    def _show(self, lbl, schema, key):
        text = accel_label(self._get(schema, key))
        lbl.set_label(text)
        lbl.set_tooltip_text(text)

    def _edit(self, schema, key, title):
        shown = label(_("Press the new shortcut, Backspace to disable it, or Esc to cancel."), wrap=True)
        captured = {"value": None}
        dlg = ContentDialog(_(title), None, primary=_("Set"), close=_("Cancel"), extra=shown,
                            on_response=lambda r: self._apply(schema, key, captured["value"]) if r == "primary"
                            else None)
        ctl = Gtk.EventControllerKey()

        def pressed(_c, keyval, _code, state):
            mods = state & Gtk.accelerator_get_default_mod_mask()
            if keyval == Gdk.KEY_Escape and not mods:
                dlg.respond("close")
                return True
            if keyval == Gdk.KEY_BackSpace and not mods:
                captured["value"] = ""
                shown.set_label(_("Disabled"))
                return True
            if keyval in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R, Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Alt_L,
                          Gdk.KEY_Alt_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R):
                return True
            captured["value"] = Gtk.accelerator_name(Gdk.keyval_to_lower(keyval), mods)
            shown.set_label(Gtk.accelerator_get_label(Gdk.keyval_to_lower(keyval), mods))
            return True
        ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ctl.connect("key-pressed", pressed)
        dlg.add_controller(ctl)
        dlg.set_focusable(True)
        show_dialog(self.box, dlg)
        dlg.grab_focus()

    def _apply(self, schema, key, value):
        if value is None:
            return
        cur = util.gget(schema, key)
        if isinstance(cur, str):
            ok = util.gset(schema, key, value)
        else:
            ok = util.gset(schema, key, [value] if value else [])
        ro_toast(self, ok)


@register
class HardwarePage(Page):
    id = "fx-hardware"
    parent = "fenestra"
    title = "Printers, tablets & color"
    keywords = "printer cups wacom tablet stylus color profile icc calibration"

    def build(self, box):
        self.pg = self.group(_("Printers"))
        self.tg = self.group(_("Drawing tablets"))
        self.cg = self.group(_("Color profiles"))
        linux.printers(lambda r: self._fill(self.pg, r, "fs-print-symbolic", _("No printers found"), True))
        linux.tablets(lambda r: self._fill(self.tg, [(n, None) for n in r] if r is not None else None,
                                           "fs-pen-symbolic", _("No drawing tablets connected")))
        linux.color_devices(lambda r: self._fill(self.cg, r, "fs-color-symbolic", _("No color-managed devices")))
        g = self.group(_("More"))
        self.ext_row(g, _("Manage printers"), _("Add printers and change print options"), "fs-print-symbolic",
                     ["gnome-control-center", "printers"])
        self.ext_row(g, _("Tablet and color settings"), _("Map tablets and calibrate displays"), "fs-color-symbolic",
                     ["gnome-control-center", "wacom"])

    def _fill(self, g, rows, ic, empty, printers=False):
        if rows is None:
            g.add(not_available_row(empty))
            return
        if not rows:
            g.add(SettingRow(empty, None, ic))
        states = {"idle": _("Ready"), "busy": _("Printing"), "disabled": _("Paused")}
        for name, sub in rows:
            g.add(SettingRow(name, states.get(sub, sub) if printers else sub, ic))


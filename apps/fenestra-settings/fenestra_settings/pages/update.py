"""Fenestra Update (PackageKit + Flatpak)."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import util
from ..backends import fenestra_update, packages
from ..i18n import _
from ..widgets import (ExpanderRow, SettingRow, ToggleSwitch, button, clear, confirm, icon, label,
                       not_available_row, spinner, toast)
from .base import Page, register

UPD = "org.gnome.software"


def _fmt_time(t):
    if not t:
        return _("Never")
    dt = GLib.DateTime.new_from_unix_local(int(t))
    today = GLib.DateTime.new_now_local()
    if dt.format("%Y%m%d") == today.format("%Y%m%d"):
        return _("today, {0}").format(dt.format("%H:%M"))
    return dt.format("%x, %H:%M")


@register
class UpdatePage(Page):
    id = "update"
    title = "Fenestra Update"
    keywords = "updates upgrade patch security dnf packagekit flatpak restart"
    index = [("check", "Check for updates", "search updates refresh"),
             ("advanced-update", "Advanced options", "automatic download"),
             ("history", "Update history", "installed updates log")]

    def build(self, box):
        self.state = "idle"
        self.updates = []
        hero = Gtk.Box(spacing=20)
        hero.add_css_class("update-hero")
        self.hero_icon_box = Gtk.Overlay()
        big = icon("fs-arrow-sync-symbolic", 56, "update-hero-icon")
        big.set_size_request(80, 80)
        self.hero_icon_box.set_child(big)
        hero.append(self.hero_icon_box)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True, spacing=2)
        self.title_lbl = label("", "subtitle-text", wrap=True)
        self.sub_lbl = label("", "caption", wrap=True)
        tb.append(self.title_lbl)
        tb.append(self.sub_lbl)
        hero.append(tb)
        self.action_box = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        hero.append(self.action_box)
        hero.key = "check"
        self._rows["check"] = hero
        box.append(hero)

        self.list_group = self.group()
        self.list_group.set_visible(False)

        g = self.group(_("More options"))
        g.set_margin_top(18)
        if util.has_key(UPD, "download-updates"):
            g.add(SettingRow(_("Get the latest updates as soon as they're available"),
                             _("Download updates automatically in the background"), "fs-arrow-download-symbolic",
                             control=self._gs_toggle("download-updates")))
        g.add(SettingRow(_("Pause updates"), _("Updates are only installed when you choose to"), "fs-pause-symbolic",
                         control=label(_("Manual"), "row-value")))
        hr = SettingRow(_("Update history"), None, "fs-history-symbolic", chevron=True,
                        on_click=lambda: self.go("update-history"), key="history")
        self.remember("history", hr)
        g.add(hr)
        ar = SettingRow(_("Advanced options"), _("Automatic downloads, notifications, other update settings"),
                        "fs-options-symbolic", chevron=True, on_click=lambda: self.go("update-advanced"),
                        key="advanced-update")
        self.remember("advanced-update", ar)
        g.add(ar)
        if util.have("gnome-software"):
            self.ext_row(g, _("Software center"), _("Firmware and app updates"), "fs-apps-symbolic",
                         ["gnome-software", "--mode=updates"])
        self._render()

    def _gs_toggle(self, key):
        t = ToggleSwitch(bool(util.gget(UPD, key)), lambda v: util.gset(UPD, key, v))
        return t

    # ---------------------------------------------------------------- state machine
    def _render(self):
        clear(self.action_box)
        last = packages.last_checked()
        if not util.have("pkcon") and not fenestra_update.available():
            self.title_lbl.set_label(_("Updates are not available"))
            self.sub_lbl.set_label(_("PackageKit (pkcon) is not installed"))
            return
        if (packages.offline_pending() or fenestra_update.restart_pending()) and self.state not in ("checking", "downloading"):
            self.title_lbl.set_label(_("Restart required"))
            self.sub_lbl.set_label(_("Your device will restart to finish installing updates."))
            self.action_box.append(button(_("Restart now"), self._restart, accent=True))
            return
        if self.state == "checking":
            self.title_lbl.set_label(_("Checking for updates…"))
            self.sub_lbl.set_label(_("This might take a few minutes"))
            self.action_box.append(spinner(24))
        elif self.state == "downloading":
            self.title_lbl.set_label(_("Downloading updates…"))
            self.sub_lbl.set_label(_("You can keep using your device while updates download"))
            self.action_box.append(spinner(24))
        elif self.state == "available":
            n = len(self.updates)
            self.title_lbl.set_label(_("Updates available") if n != 1 else _("Update available"))
            self.sub_lbl.set_label((_("{0} updates · Last checked: {1}") if n != 1 else _("{0} update · Last checked: {1}"))
                                   .format(n, _fmt_time(last)))
            has_rpm = any(u.kind in ("rpm", "fenestra") for u in self.updates)
            self.action_box.append(button(_("Download & install all") if has_rpm else _("Install all"),
                                          self._install, accent=True))
        elif self.state == "error":
            self.title_lbl.set_label(_("We couldn't check for updates"))
            self.sub_lbl.set_label(self.error or "")
            self.action_box.append(button(_("Retry"), self._check, accent=True))
        else:
            self.title_lbl.set_label(_("You're up to date") if last else _("Check for updates"))
            self.sub_lbl.set_label(_("Last checked: {0}").format(_fmt_time(last)))
            self.action_box.append(button(_("Check for updates"), self._check, accent=True))

    def _check(self):
        self.state = "checking"
        self._render()
        self.fenestra = None

        def fenestra_checked(ok, upd, _err):
            # Fedora's updates are still listed when GitHub can't be reached.
            self.fenestra = upd if ok else None
            if util.have("pkcon"):
                packages.check(self._checked)
            else:
                if not util.READ_ONLY:
                    packages.set_state("last_checked", GLib.get_real_time() / 1e6)
                self._checked(ok, [], _err)
        if fenestra_update.available():
            fenestra_update.check(fenestra_checked)
        else:
            fenestra_checked(False, None, "")

    def _checked(self, ok, ups, err):
        fen = [self.fenestra] if getattr(self, "fenestra", None) else []
        if not ok and not fen:
            self.state, self.error = "error", err
            self._render()
            return
        self.updates = fen + list(ups)
        self.state = "available" if self.updates else "idle"
        self._render()
        self._fill_list()

    def _fill_list(self):
        self.list_group.clear()
        if not self.updates:
            self.list_group.set_visible(False)
            return
        self.list_group.set_visible(True)
        for u in self.updates:
            if u.kind != "fenestra":
                continue
            exp = ExpanderRow(_("Fenestra {0}").format(u.version),
                              _("{0} changes · new features and fixes").format(u.total) if u.total
                              else _("New features and fixes"),
                              "fs-arrow-sync-symbolic", expanded=True)
            for c in u.changes[:50]:
                exp.add(SettingRow(c, None, None))
            if u.total > min(len(u.changes), 50):
                exp.add(SettingRow(_("…and {0} more").format(u.total - min(len(u.changes), 50)), None, None))
            self.list_group.add(exp)
        rpm = [u for u in self.updates if u.kind == "rpm"]
        fp = [u for u in self.updates if u.kind == "flatpak"]
        if rpm:
            sec = [u for u in rpm if u.severity.lower() in ("security", "critical", "important")]
            exp = ExpanderRow(_("System updates ({0})").format(len(rpm)),
                              _("{0} security updates").format(len(sec)) if sec else None,
                              "fs-shield-checkmark-symbolic", expanded=len(rpm) <= 12)
            for u in rpm[:200]:
                exp.add(SettingRow(u.name, f"{u.version}.{u.arch} · {u.repo}", None,
                                   control=label(_(u.severity) if u.severity != "Normal" else "", "row-value")))
            if len(rpm) > 200:
                exp.add(SettingRow(_("…and {0} more").format(len(rpm) - 200), None, None))
            self.list_group.add(exp)
        if fp:
            exp = ExpanderRow(_("App updates ({0})").format(len(fp)), _("Flatpak"), "fs-apps-symbolic",
                              expanded=len(fp) <= 12)
            for u in fp:
                exp.add(SettingRow(u.name, u.version or None, None))
            self.list_group.add(exp)

    def _install(self):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        self.state = "downloading"
        self._render()
        has_rpm = any(u.kind == "rpm" for u in self.updates)
        has_fp = any(u.kind == "flatpak" for u in self.updates)
        fen = next((u for u in self.updates if u.kind == "fenestra"), None)

        def after_fp(ok, _msg=None):
            if has_rpm:
                packages.download_and_prepare(after_rpm)
            else:
                self.state = "idle"
                self.updates = []
                self._fill_list()
                self._render()
                toast(self.box, _("Updates installed") if ok else _("Some updates failed to install"))

        def after_rpm(ok, msg):
            if ok:
                self.state = "idle"
                self._render()
            else:
                self.state, self.error = "error", msg.splitlines()[-1] if msg else ""
                self._render()
        def apps_and_system():
            if has_fp:
                packages.update_flatpaks(after_fp)
            else:
                after_fp(True)

        def after_fenestra(ok, msg):
            if not ok:
                self.state, self.error = "error", (_("Fenestra update failed: {0}").format(msg.splitlines()[-1])
                                                   if msg else _("Fenestra update failed"))
                self._render()
                return
            self.updates = [u for u in self.updates if u.kind != "fenestra"]
            apps_and_system()
        if fen:
            fenestra_update.install(fen, after_fenestra)
        else:
            apps_and_system()

    def _restart(self):
        confirm(self.box, _("Restart now?"), _("Save your work before restarting. Updates will be installed "
                                                 "during the restart."), _("Restart now"),
                lambda: packages.reboot(lambda ok, *_: ok or toast(self.box, _("This action is disabled in "
                                                                                 "read-only mode")
                                                                       if util.READ_ONLY else _("Couldn't restart"))))


@register
class UpdateAdvancedPage(Page):
    id = "update-advanced"
    parent = "update"
    title = "Advanced options"
    keywords = "automatic updates notifications offline"

    def build(self, box):
        g = self.group(_("Additional options"))
        any_ = False
        for key, title, sub in (("download-updates", _("Download updates automatically"),
                                 _("Updates are downloaded in the background when you're on an unmetered network")),
                                ("download-updates-notify", _("Notify me when updates are ready"), None),
                                ("allow-updates", _("Allow software updates"), None)):
            if util.has_key(UPD, key):
                any_ = True
                g.add(SettingRow(title, sub, "fs-arrow-download-symbolic",
                                 control=ToggleSwitch(bool(util.gget(UPD, key)),
                                                      lambda v, k=key: util.gset(UPD, k, v))))
        if not any_:
            g.add(not_available_row(_("Automatic updates"), _("GNOME Software is not installed")))
        g2 = self.group(_("Related"))
        g2.add(SettingRow(_("Recovery options"), None, "fs-arrow-counterclockwise-symbolic", chevron=True,
                          on_click=lambda: self.go("recovery")))


@register
class UpdateHistoryPage(Page):
    id = "update-history"
    parent = "update"
    title = "Update history"
    keywords = "installed updates log transactions"

    def build(self, box):
        self.g = self.group(_("Recent transactions"))
        self.g.add(SettingRow(_("Loading…"), None, None, control=spinner()))
        packages.history(self._got)

    def _got(self, rows):
        self.g.clear()
        if not rows:
            self.g.add(SettingRow(_("No update history"), None, "fs-history-symbolic"))
        for date, cmd, n in rows:
            sub = date + (f" · {n} " + _("packages") if n else "")
            self.g.add(SettingRow(cmd, sub, "fs-history-symbolic"))


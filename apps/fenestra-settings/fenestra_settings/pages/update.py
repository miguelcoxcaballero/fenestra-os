"""Fenestra Update (PackageKit + Flatpak)."""
from __future__ import annotations

import os

from gi.repository import GLib, Gtk

from .. import util
from ..backends import fenestra_update, migrate, packages, release, session
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

        # New Fedora release (whole-system upgrade, see fenestra-release-upgrade).
        self.rel_group = self.group()
        self.rel_group.set_visible(False)
        self._rel_next = None
        self._rel_timer = 0
        self._render_release()
        release.available(self._got_release)

        # «Migrar a KDE»: the Fenestra session on KWin (fenestra-migrate).
        self.mig_group = self.group()
        self.mig_group.set_visible(False)
        self._mig_timer = 0
        self._mig_open = False
        self._render_migrate()

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

    # ------------------------------------------------------------ release upgrade
    def _got_release(self, info):
        self._rel_next = info.get("next")
        self._rel_login_off = info.get("login_unvalidated") or []
        self._rel_gnome = info.get("gnome")
        self._render_release()

    def _stop_rel_timer(self):
        if self._rel_timer:
            GLib.source_remove(self._rel_timer)
            self._rel_timer = 0

    def _poll_release(self):
        if self.rel_group.get_root() is None:      # page closed
            self._rel_timer = 0
            return GLib.SOURCE_REMOVE
        self._render_release()
        return GLib.SOURCE_CONTINUE if self._rel_timer else GLib.SOURCE_REMOVE

    def _render_release(self):
        g = self.rel_group
        g.clear()
        st = release.state()
        status = st.get("status", "")
        cur = release.current_version()
        target = st.get("target") or self._rel_next
        busy = release.running() or status == "preparing"
        pct, step_text, last, warns, err = release.progress()
        if busy:
            if not self._rel_timer:
                self._rel_timer = GLib.timeout_add(1000, self._poll_release)
            bar = Gtk.ProgressBar(fraction=max(0.0, min(1.0, pct / 100)), hexpand=True)
            bar.set_size_request(220, -1)
            g.add(SettingRow(_("Upgrading to Fedora {0}").format(target), _(step_text) if step_text else
                             _("Starting…"), "fs-arrow-sync-symbolic", control=bar))
            if last:
                g.add(SettingRow(_("Details"), last[-160:], None))
            g.add(SettingRow(_("You can keep using your device. Don't turn it off."), None,
                             "fs-info-symbolic"))
        else:
            self._stop_rel_timer()
            if status == "ready-to-reboot" and cur < int(target or 0):
                g.add(SettingRow(_("Fedora {0} is ready to install").format(target),
                                 _("Your device will restart and install it. This takes 20–40 minutes; "
                                   "your files, apps and settings stay."),
                                 "fs-arrow-sync-symbolic",
                                 control=button(_("Restart now"), self._release_reboot, accent=True)))
            elif status == "failed":
                g.add(SettingRow(_("The upgrade to Fedora {0} didn't finish").format(target),
                                 st.get("message") or err or "", "fs-alert-symbolic",
                                 control=button(_("Try again"), self._release_start, accent=True)))
            elif status in ("done", "post-failed") and cur >= int(target or 0):
                ok = status == "done"
                g.add(SettingRow(_("Your device runs Fedora {0}").format(cur),
                                 _("Everything was set up for the new version") if ok else
                                 (st.get("message") or _("Some drivers need attention")),
                                 "fs-checkmark-symbolic" if ok else "fs-alert-symbolic"))
                if self._rel_next and self._rel_next > cur:
                    self._offer(self._rel_next)
            elif self._rel_next and self._rel_next > cur:
                self._offer(self._rel_next)
            for w in warns[-3:]:
                if status in ("failed", "ready-to-reboot"):
                    g.add(SettingRow(w, None, "fs-alert-symbolic"))
        g.set_visible(g.rows.get_first_child() is not None)

    def _offer(self, target):
        self.rel_group.add(SettingRow(
            _("Fedora {0} is available").format(target),
            _("Upgrade the whole system. Fenestra, your drivers, files, apps and settings are kept."),
            "fs-arrow-sync-symbolic", control=button(_("Upgrade"), self._release_start, accent=True)))
        off = getattr(self, "_rel_login_off", [])
        if off:
            # Login / lock-screen extensions not validated for the new GNOME: turned off before
            # the restart, so the standard sign-in is always there (fenestra-login-guard).
            self.rel_group.add(SettingRow(
                _("Some sign-in screen customizations will be turned off"),
                _("Not yet checked with GNOME {0}: {1}. The standard sign-in screen is used until a "
                  "Fenestra update supports them.").format(getattr(self, "_rel_gnome", "") or "", ", ".join(off)),
                "fs-shield-checkmark-symbolic"))

    def _release_start(self):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        target = release.state().get("target") if release.state().get("status") == "failed" else self._rel_next
        target = target or self._rel_next
        if not target:
            return

        def go():
            def started(ok, msg):
                if not ok:
                    toast(self.box, _("Couldn't start the upgrade"))
                self._render_release()
            release.start(target, started)
            GLib.timeout_add(1500, lambda: (self._render_release(), False)[1])
        confirm(self.box, _("Upgrade to Fedora {0}?").format(target),
                _("Fenestra checks that everything will keep working, downloads the new version and then asks "
                  "you to restart. Keep the device plugged in."), _("Upgrade"), go)

    def _release_reboot(self):
        confirm(self.box, _("Restart now?"), _("Save your work before restarting. The new version is installed "
                                                 "during the restart."), _("Restart now"),
                lambda: release.reboot(lambda ok, *_: ok or toast(self.box, _("Couldn't restart"))))

    # ------------------------------------------------------------ «Migrar a KDE»
    def _render_migrate(self):
        g = self.mig_group
        g.clear()
        if not migrate.available():
            g.set_visible(False)
            return
        st = migrate.state()
        status = st.get("status", "idle")
        running = status == "running"
        if running and not self._mig_timer:
            self._mig_timer = GLib.timeout_add(1000, self._poll_migrate)
        title = _("Migrar a KDE")
        desc = _("Actualiza Fenestra a su nueva arquitectura basada en KWin y Wayland, con una interfaz propia "
                 "optimizada para mejorar el rendimiento, la estabilidad y la eficiencia energética. Conserva tus "
                 "aplicaciones, archivos y configuración.")
        if running:
            phase = st.get("phase") or "detect"
            bar = Gtk.ProgressBar(fraction=max(0.02, min(1.0, st.get("progress", 0) / 100)), hexpand=True)
            bar.set_size_request(220, -1)
            g.add(SettingRow(title, _(migrate.PHASE_TEXT.get(phase, "")), "fs-arrow-sync-symbolic", control=bar))
            g.add(SettingRow(_("You can keep using your device. Don't turn it off."), None, "fs-info-symbolic"))
        elif status == "failed":
            g.add(SettingRow(_("The migration didn't finish"), st.get("error", "")[-300:], "fs-alert-symbolic",
                             control=button(_("Try again"), self._migrate_start, accent=True)))
            g.add(SettingRow(_("Go back to the previous desktop"), _("Removes what the migration installed"),
                             "fs-arrow-undo-symbolic", control=button(_("Go back"), self._migrate_rollback)))
        elif status == "done" or migrate.installed():
            if session.is_fenestra():
                if migrate.session_ok() and st.get("default_for") is not None and os.environ.get("USER") not in st.get("default_for", []):
                    g.add(SettingRow(_("Use the new desktop every time"), _("Make it the default when you sign in. GNOME stays available."),
                                     "fs-checkmark-symbolic", control=button(_("Make default"), self._migrate_default, accent=True)))
            else:
                g.add(SettingRow(_("The new desktop is installed"),
                                 _("Sign out, choose «Fenestra» with the gear button on the sign-in screen and sign in. "
                                   "This desktop stays available."), "fs-checkmark-symbolic",
                                 control=button(_("Sign out"), self._migrate_signout, accent=True)))
            g.add(SettingRow(_("Go back to the previous desktop"), _("Removes the new desktop and uses this one again"),
                             "fs-arrow-undo-symbolic", control=button(_("Go back"), self._migrate_rollback)))
        else:
            g.add(SettingRow(title, desc, "fs-arrow-sync-symbolic",
                             control=button(_("Hide details") if self._mig_open else _("Details"), self._migrate_toggle,
                                            accent=not self._mig_open)))
            if self._mig_open:
                g.add(SettingRow(_("Requirements"), _("Fedora 45 or later, an internet connection, about 1.5 GB of free space, "
                                                      "and the device plugged in"), "fs-info-symbolic"))
                g.add(SettingRow(_("What changes"), _("A new desktop is added to the sign-in screen. The current desktop, "
                                                      "your apps, files and settings stay; you choose when to switch."),
                                 "fs-info-symbolic"))
                mb = st.get("download_mb")
                checked = status == "dry-run-ok"
                g.add(SettingRow(_("Checks"), (_("Everything is ready. Download: {0} MB").format(mb) if checked and mb is not None
                                               else _("Not checked yet")),
                                 "fs-checkmark-symbolic" if checked else "fs-shield-checkmark-symbolic",
                                 control=button(_("Check"), self._migrate_check)))
                g.add(SettingRow(_("Start the migration"), _("The new desktop is tested before it is offered"),
                                 "fs-arrow-sync-symbolic", control=button(_("Start"), self._migrate_start, accent=True)))
        g.set_visible(True)

    def _poll_migrate(self):
        if self.mig_group.get_root() is None:
            self._mig_timer = 0
            return GLib.SOURCE_REMOVE
        running = migrate.state().get("status") == "running"
        self._render_migrate()
        if not running:
            self._mig_timer = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _migrate_toggle(self):
        self._mig_open = not self._mig_open
        self._render_migrate()

    def _migrate_check(self):
        def done(ok, msg):
            if not ok and migrate.state().get("status") != "failed":
                toast(self.box, _("Couldn't check: {0}").format(msg[-120:] if msg else _("cancelled")))
            self._render_migrate()
        migrate.check(done)

    def _migrate_start(self):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return

        def go():
            migrate.start(lambda ok, msg: self._render_migrate())
            GLib.timeout_add(1500, lambda: (self._render_migrate(), False)[1])
        confirm(self.box, _("Migrar a KDE?"),
                _("Fenestra installs and tests the new desktop. Nothing is removed and your current desktop stays "
                  "available. Keep the device plugged in."), _("Start"), go)

    def _migrate_signout(self):
        confirm(self.box, _("Sign out now?"), _("Save your work first. On the sign-in screen, choose «Fenestra» with the "
                                                "gear button."), _("Sign out"),
                lambda: util.run_async(["gnome-session-quit", "--logout", "--no-prompt"]))

    def _migrate_default(self):
        migrate.set_default(lambda ok, msg: (toast(self.box, _("The new desktop is now the default") if ok else msg), self._render_migrate()))

    def _migrate_rollback(self):
        confirm(self.box, _("Go back to the previous desktop?"),
                _("The new desktop and what it installed are removed. Your files, apps and settings stay."), _("Go back"),
                lambda: migrate.rollback(lambda ok, msg: (toast(self.box, _("Done. The previous desktop is the default again.") if ok else msg),
                                                          self._render_migrate())))

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


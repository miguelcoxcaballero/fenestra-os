"""System › Notifications and System › Focus."""
from __future__ import annotations

from gi.repository import Gio, GLib, Gtk

from .. import util
from ..backends import notifications as notif
from ..i18n import _
from ..widgets import SettingRow, ToggleSwitch, button, icon, label, not_available_row, toast
from .base import Page, register
from .common import gsetting_toggle

NOTIF = "org.gnome.desktop.notifications"
APP_SCHEMA = "org.gnome.desktop.notifications.application"


def _app_settings(app_id):
    path = "/org/gnome/desktop/notifications/application/" + app_id.lower().replace(".", "-") + "/"
    src = Gio.SettingsSchemaSource.get_default()
    if not src or not src.lookup(APP_SCHEMA, True):
        return None
    return Gio.Settings.new_with_path(APP_SCHEMA, path)


def _dnd_toggle():
    """Do not disturb switch on the session's notification backend, following outside changes
    (the shell's quick settings, other apps)."""
    t = ToggleSwitch(notif.dnd(), notif.set_dnd)
    notif.connect_dnd(lambda: t.set_active(notif.dnd()))
    return t


@register
class NotificationsPage(Page):
    id = "notifications"
    parent = "system"
    title = "Notifications"
    keywords = "alerts banners do not disturb dnd toast"
    index = [
        ("notifications", "Notifications", "banners alerts"),
        ("dnd", "Do not disturb", "silence quiet banners"),
        ("lock", "Show notifications on the lock screen", "lock screen privacy"),
        ("apps", "Notifications from apps and other senders", "per app"),
    ]

    def build(self, box):
        g = self.group()
        if not notif.available():
            g.add(not_available_row(_("Notifications")))
            return
        # In the reference UI "Notifications" on/off is the master switch; the closest
        # equivalent is do not disturb (GNOME: the inverse of show-banners; Fenestra Shell:
        # shell.conf [Notifications] DoNotDisturb).
        dnd = _dnd_toggle()
        r = SettingRow(_("Do not disturb"),
                       _("Notifications will be sent directly to the notification center"),
                       "fs-alert-symbolic", control=dnd, key="dnd")
        self.remember("dnd", r)
        g.add(r)
        lt = gsetting_toggle(NOTIF, "show-in-lock-screen")
        if lt:
            r2 = SettingRow(_("Show notifications on the lock screen"), None, "fs-lock-closed-symbolic",
                            control=lt, key="lock")
            self.remember("lock", r2)
            g.add(r2)
        self.nav_row(g, "focus", _("Turn on do not disturb automatically"), _("Focus sessions and schedules"),
                     "fs-timer-symbolic", key="focus-link")

        apps_group = self.group(_("Notifications from apps and other senders"))
        apps_group.key = "apps"
        self._rows["apps"] = apps_group
        if "apps" in self.hidden_keys():
            return  # the per-app list belonged to GNOME Shell
        apps = util.gget(NOTIF, "application-children", []) or []
        infos = {}
        for info in Gio.AppInfo.get_all():
            aid = (info.get_id() or "").removesuffix(".desktop")
            infos[aid.lower().replace(".", "-")] = info
        shown = 0
        for child in sorted(apps):
            info = infos.get(child)
            if info is None:
                continue
            if util.DEMO and not (getattr(info, "get_filename", lambda: "")() or "").startswith("/usr/share/applications/"):
                continue
            s = _app_settings((info.get_id() or "").removesuffix(".desktop"))
            if s is None:
                continue
            t = ToggleSwitch(s.get_boolean("enable"),
                             lambda v, st=s: util.READ_ONLY or (util.record("gsettings", f"{APP_SCHEMA} enable", v)
                                                                   if util.SANDBOX else None,
                                                                   st.set_boolean("enable", v)))
            sub = _("Banners, Sounds") if s.get_boolean("show-banners") else _("Off")
            img = Gtk.Image.new_from_gicon(info.get_icon()) if info.get_icon() else icon("fs-app-generic-symbolic")
            img.set_pixel_size(24)
            apps_group.add(SettingRow(info.get_display_name(), sub, image=img, control=t))
            shown += 1
            if shown > 40:
                break
        if shown == 0:
            apps_group.add(SettingRow(_("No apps have sent notifications yet"), None, "fs-info-symbolic"))


@register
class FocusPage(Page):
    id = "focus"
    parent = "system"
    title = "Focus"
    keywords = "timer concentrate session pomodoro"
    index = [("start-focus", "Start focus session", "timer")]

    def build(self, box):
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        hero.add_css_class("home-card")
        hero.set_halign(Gtk.Align.FILL)
        self.time_lbl = label("30", "big-number", xalign=0.5)
        hero.append(self.time_lbl)
        hero.append(label(_("mins"), "caption", xalign=0.5))
        self.focus_minutes = 30
        bb = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        bb.append(button("−", lambda: self._adj(-5), css="small"))
        bb.append(button("+", lambda: self._adj(5), css="small"))
        hero.append(bb)
        self.start_btn = button(_("Start focus session"), self._start, accent=True)
        self.start_btn.set_halign(Gtk.Align.CENTER)
        hero.append(self.start_btn)
        self.remember("start-focus", hero)
        box.append(hero)
        self._timer = 0
        g = self.group(_("Focus settings"))
        g.set_margin_top(18)
        dnd = _dnd_toggle() if notif.available() else None
        if dnd:
            g.add(SettingRow(_("Turn on do not disturb"), _("Silence notifications during a focus session"),
                             "fs-alert-symbolic", control=dnd))

    def _adj(self, d):
        if self._timer:
            return
        self.focus_minutes = max(5, min(240, self.focus_minutes + d))
        self.time_lbl.set_label(str(self.focus_minutes))

    def _start(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
            notif.set_dnd(False)
            self.start_btn.set_label(_("Start focus session"))
            self.time_lbl.set_label(str(self.focus_minutes))
            return
        notif.set_dnd(True)
        self.remaining = self.focus_minutes * 60
        self.start_btn.set_label(_("Stop session"))
        self._timer = GLib.timeout_add_seconds(1, self._tick)
        toast(self.box, _("Focus session started"))

    def _tick(self):
        self.remaining -= 1
        m, s = divmod(max(0, self.remaining), 60)
        self.time_lbl.set_label(f"{m:02d}:{s:02d}")
        if self.remaining <= 0:
            self._timer = 0
            notif.set_dnd(False)
            self.start_btn.set_label(_("Start focus session"))
            self.time_lbl.set_label(str(self.focus_minutes))
            return False
        return True

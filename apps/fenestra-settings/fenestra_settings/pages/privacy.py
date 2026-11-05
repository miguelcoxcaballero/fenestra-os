"""Privacy & security."""
from __future__ import annotations

from .. import util
from ..i18n import N_, _
from ..widgets import Dropdown, SettingRow, button, not_available_row, toast
from .base import Page, register
from .common import gsetting_toggle

PRIV = "org.gnome.desktop.privacy"
LOC = "org.gnome.system.location"
SS = "org.gnome.desktop.screensaver"
SESSION = "org.gnome.desktop.session"


@register
class PrivacyPage(Page):
    id = "privacy"
    title = "Privacy & security"
    keywords = "permissions security lock location camera microphone diagnostics"
    SECURITY = [
        ("screenlock", N_("Screen lock"), N_("Automatic lock, lock delay"), "fs-lock-shield-symbolic"),
    ]
    PERMISSIONS = [
        ("general", N_("General"), N_("Recent files, usage history, trash"), "fs-shield-symbolic"),
        ("diagnostics", N_("Diagnostics & feedback"), N_("Problem reporting, technical reports"),
         "fs-data-usage-symbolic"),
    ]
    APP_PERMS = [
        ("location", N_("Location"), N_("Location services"), "fs-location-symbolic"),
        ("camera", N_("Camera"), N_("Camera access for apps"), "fs-camera-symbolic"),
        ("microphone", N_("Microphone"), N_("Microphone access for apps"), "fs-mic-symbolic"),
    ]

    def build(self, box):
        g = self.group(_("Security"))
        for pid, t, s, ic in self.SECURITY:
            self.nav_row(g, pid, _(t), _(s), ic)
        if util.have("firewall-config"):
            self.ext_row(g, _("Firewall & network protection"), _("Zones and services"), "fs-shield-checkmark-symbolic",
                         ["firewall-config"])
        g2 = self.group(_("Fenestra permissions"))
        for pid, t, s, ic in self.PERMISSIONS:
            self.nav_row(g2, pid, _(t), _(s), ic)
        g3 = self.group(_("App permissions"))
        for pid, t, s, ic in self.APP_PERMS:
            self.nav_row(g3, pid, _(t), _(s), ic)
        self.ext_row(g3, _("All app permissions"), _("Per-app access to files, devices and portals"),
                     "fs-apps-symbolic", ["gnome-control-center", "applications"])


def _toggle_page(page, schema, key, title, sub, icon, invert=False, rkey=None):
    g = page.group()
    t = gsetting_toggle(schema, key, invert=invert)
    if t is None:
        r = not_available_row(title)
    else:
        r = SettingRow(title, sub, icon, control=t)
    if rkey:
        page.remember(rkey, r)
    g.add(r)
    return g


@register
class GeneralPrivacyPage(Page):
    id = "general"
    parent = "privacy"
    title = "General"
    keywords = "recent files history trash temporary"
    index = [("recent", "Remember recent files", "history activity"),
             ("trash-auto", "Automatically empty trash", "old files"),
             ("temp-auto", "Automatically delete temporary files", "cleanup")]

    def build(self, box):
        g = self.group(_("Change privacy options"))
        for key, sk, title, sub, ic in (
                ("recent", "remember-recent-files", _("Remember recent files"),
                 _("Let apps show the files you opened recently"), "fs-history-symbolic"),
                ("trash-auto", "remove-old-trash-files", _("Automatically empty trash"),
                 _("Delete files that have been in the trash for a while"), "fs-delete-symbolic"),
                ("temp-auto", "remove-old-temp-files", _("Automatically delete temporary files"),
                 _("Remove old temporary files"), "fs-delete-symbolic"),
                ("names", "show-full-name-in-top-bar", _("Show my name in the top bar"), None,
                 "fs-person-symbolic")):
            t = gsetting_toggle(PRIV, sk)
            if t:
                r = SettingRow(title, sub, ic, control=t, key=key)
                self.remember(key, r)
                g.add(r)
        if util.has_key(PRIV, "recent-files-max-age"):
            age = util.gget(PRIV, "recent-files-max-age", -1)
            opts = [(1, _("1 day")), (7, _("7 days")), (30, _("30 days")), (-1, _("Forever"))]
            if age not in [o[0] for o in opts]:
                opts.insert(0, (age, str(age)))
            g.add(SettingRow(_("Keep recent file history for"), None, "fs-history-symbolic",
                             control=Dropdown(opts, age, lambda v: util.gset(PRIV, "recent-files-max-age", int(v)))))

        def clear_hist():
            if util.READ_ONLY:
                toast(self.box, _("This action is disabled in read-only mode"))
                return
            import os
            p = os.path.expanduser("~/.local/share/recently-used.xbel")
            try:
                with open(p, "w") as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<xbel version="1.0"/>\n')
                toast(self.box, _("History cleared"))
            except OSError:
                toast(self.box, _("The change was not applied"))
        g.add(SettingRow(_("Clear activity history"), None, "fs-delete-symbolic",
                         control=button(_("Clear history"), clear_hist)))


@register
class LocationPage(Page):
    id = "location"
    parent = "privacy"
    title = "Location"
    keywords = "gps geoclue position"
    index = [("location-services", "Location services", "gps geoclue")]

    def build(self, box):
        _toggle_page(self, LOC, "enabled", _("Location services"),
                     _("Apps can use your location when you allow it"), "fs-location-symbolic",
                     rkey="location-services")


@register
class CameraPage(Page):
    id = "camera"
    parent = "privacy"
    title = "Camera"
    keywords = "webcam access privacy"
    index = [("camera-access", "Camera access", "webcam allow")]

    def build(self, box):
        _toggle_page(self, PRIV, "disable-camera", _("Camera access"),
                     _("Let apps access your camera"), "fs-camera-symbolic", invert=True, rkey="camera-access")


@register
class MicrophonePage(Page):
    id = "microphone"
    parent = "privacy"
    title = "Microphone"
    keywords = "mic audio recording access privacy"
    index = [("mic-access", "Microphone access", "allow mic")]

    def build(self, box):
        _toggle_page(self, PRIV, "disable-microphone", _("Microphone access"),
                     _("Let apps access your microphone"), "fs-mic-symbolic", invert=True, rkey="mic-access")


@register
class DiagnosticsPage(Page):
    id = "diagnostics"
    parent = "privacy"
    title = "Diagnostics & feedback"
    keywords = "abrt problem reporting crash technical reports telemetry"
    index = [("problem-reports", "Automatic problem reporting", "abrt crash reports"),
             ("tech-reports", "Send technical problem reports", "report")]

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(PRIV, "report-technical-problems")
        if t:
            r = SettingRow(_("Send technical problem reports"),
                           _("Help improve Fenestra by sending anonymous crash reports"), "fs-data-usage-symbolic",
                           control=t, key="tech-reports")
            self.remember("tech-reports", r)
            g.add(r)
        if util.have("abrt-auto-reporting"):
            r = SettingRow(_("Automatic problem reporting"), _("ABRT uploads crash reports automatically"),
                           "fs-alert-symbolic", key="problem-reports")
            self.remember("problem-reports", r)
            g.add(r)
            from ..widgets import ToggleSwitch

            def got(ok, out, _e):
                on = "enabled" in out.lower() and "disabled" not in out.lower()

                def set_(v):
                    util.run_async(["pkexec", "abrt-auto-reporting", "enabled" if v else "disabled"],
                                   lambda o, *_: o or toast(self.box, _("The change was not applied")),
                                   mutating=True)
                r.set_control(ToggleSwitch(on, set_))
            util.run_async(["abrt-auto-reporting"], got)
        elif not t:
            g.add(not_available_row(_("Diagnostics & feedback")))
        if util.have("gnome-abrt"):
            self.ext_row(g, _("View problem reports"), None, "fs-document-symbolic", ["gnome-abrt"])


@register
class ScreenLockPage(Page):
    id = "screenlock"
    parent = "privacy"
    title = "Screen lock"
    keywords = "lock automatic password delay idle screensaver"
    index = [("auto-lock", "Automatic screen lock", "lock when idle"),
             ("lock-delay", "Lock screen after the screen turns off", "delay")]

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(SS, "lock-enabled")
        if t:
            r = SettingRow(_("Automatic screen lock"), _("Lock the screen when it turns off"), "fs-lock-closed-symbolic",
                           control=t, key="auto-lock")
            self.remember("auto-lock", r)
            g.add(r)
        if util.has_key(SS, "lock-delay"):
            cur = util.gget(SS, "lock-delay", 0)
            opts = [(0, _("Immediately")), (30, _("30 seconds")), (60, _("1 minute")), (120, _("2 minutes")),
                    (300, _("5 minutes")), (1800, _("30 minutes")), (3600, _("1 hour"))]
            if cur not in [o[0] for o in opts]:
                opts.insert(0, (cur, f"{cur} s"))
            r = SettingRow(_("Lock screen after the screen turns off"), None, "fs-timer-symbolic",
                           control=Dropdown(opts, cur, lambda v: util.gset(SS, "lock-delay", int(v))), key="lock-delay")
            self.remember("lock-delay", r)
            g.add(r)
        g.add(SettingRow(_("Screen timeout"), None, "fs-desktop-symbolic", chevron=True,
                         on_click=lambda: self.go("power", "screen-sleep")))

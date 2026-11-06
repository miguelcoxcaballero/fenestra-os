"""Time & language: date & time, language & region, typing."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import i18n, util
from ..backends import timedate
from ..i18n import N_, _
from ..widgets import (Dropdown, ExpanderRow, SettingRow, ToggleSwitch, button, label, not_available_row,
                       toast, value_label)
from .base import Page, register
from .common import gsetting_dropdown, gsetting_toggle

IFACE = "org.gnome.desktop.interface"
INPUT = "org.gnome.desktop.input-sources"
DT = "org.gnome.desktop.datetime"


@register
class TimePage(Page):
    id = "time"
    title = "Time & language"
    keywords = "clock date timezone language region keyboard"
    ROWS = [
        ("datetime", N_("Date & time"), N_("Time zones, automatic clock settings, calendar display"), "fs-clock-symbolic"),
        ("language", N_("Language & region"), N_("Fenestra and some apps format dates and time based on your region"),
         "fs-local-language-symbolic"),
        ("typing", N_("Typing"), N_("Touch keyboard, text suggestions, preferences"), "fs-keyboard-symbolic"),
    ]

    def build(self, box):
        from .common import _status_item
        hero = Gtk.Box(spacing=24)
        hero.add_css_class("time-hero")
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.clock = label("", "time-clock")
        self.date = label("", "time-date")
        col.append(self.clock)
        col.append(self.date)
        hero.append(col)
        info = timedate.info()
        tz = _status_item("fs-globe-clock-symbolic", _("Time zone"), timedate.tz_label(info["timezone"]),
                          lambda: self.go("datetime"))
        lang = _status_item("fs-globe-symbolic", _("Language"),
                            timedate.locale_label(timedate.locale_info().get("LANG", "")),
                            lambda: self.go("language"))
        for it in (tz, lang):
            it.ic.remove_css_class("accent-icon")
            it.set_valign(Gtk.Align.CENTER)
            hero.append(it)
        box.append(hero)
        self._tick()
        GLib.timeout_add_seconds(1, self._tick)
        g = self.group()
        for pid, t, s, ic in self.ROWS:
            self.nav_row(g, pid, _(t), _(s), ic)
        self.ext_row(g, _("Speech"), _("Speech language, voices"), "fs-mic-symbolic",
                     ["gnome-control-center", "accessibility"])

    def _tick(self):
        now = GLib.DateTime.new_now_local()
        fmt = "%H:%M" if util.gget(IFACE, "clock-format", "24h") == "24h" else "%I:%M %p"
        self.clock.set_label(now.format(fmt))
        self.date.set_label(now.format("%A, %e %B %Y"))
        return True


@register
class DateTimePage(Page):
    id = "datetime"
    parent = "time"
    title = "Date & time"
    keywords = "clock timezone ntp automatic sync 24 hour"
    index = [("auto-time", "Set time automatically", "ntp sync network time"),
             ("auto-tz", "Set time zone automatically", "location"),
             ("timezone", "Time zone", "utc offset region"),
             ("clock-format", "Time format", "24-hour 12-hour")]

    def build(self, box):
        info = timedate.info()
        hero = Gtk.Box()
        hero.add_css_class("hero")
        self.now_lbl = label("", "subtitle-text")
        hero.append(self.now_lbl)
        box.append(hero)
        self._tick()
        GLib.timeout_add_seconds(1, self._tick)
        g = self.group()
        if info["ntp"] is not None:
            t = ToggleSwitch(bool(info["ntp"]), lambda v: timedate.set_ntp(v, self._done), sensitive=info["can_ntp"])
            r = SettingRow(_("Set time automatically"), None, "fs-arrow-sync-symbolic", control=t, key="auto-time")
        else:
            r = not_available_row(_("Set time automatically"), _("systemd-timedated is not available"))
            r.key = "auto-time"
        self.remember("auto-time", r)
        g.add(r)
        atz = gsetting_toggle(DT, "automatic-timezone")
        if atz:
            r = SettingRow(_("Set time zone automatically"), None, "fs-location-symbolic", control=atz,
                           key="auto-tz")
            self.remember("auto-tz", r)
            g.add(r)
        self.tz_row = SettingRow(_("Time zone"), None, "fs-globe-clock-symbolic",
                                 control=Dropdown([(info["timezone"], timedate.tz_label(info["timezone"]))],
                                                  info["timezone"]), key="timezone")
        self.remember("timezone", self.tz_row)
        g.add(self.tz_row)
        timedate.timezones(lambda zones: self._zones(zones, info["timezone"]))
        fmt = gsetting_dropdown(IFACE, "clock-format", [("24h", _("24-hour")), ("12h", _("12-hour"))])
        if fmt:
            r = SettingRow(_("Time format"), None, "fs-clock-symbolic", control=fmt, key="clock-format")
            self.remember("clock-format", r)
            g.add(r)
        g2 = self.group(_("Additional settings"))
        g2.add(SettingRow(_("Synchronize now"), None, "fs-arrow-clockwise-symbolic",
                          control=button(_("Sync now"), self._sync)))
        if util.has_key("org.gnome.desktop.calendar", "show-weekdate"):
            g2.add(SettingRow(_("Show week numbers in the calendar"), None, "fs-calendar-symbolic",
                              control=gsetting_toggle("org.gnome.desktop.calendar", "show-weekdate"),
                              key="week-numbers"))

    def _tick(self):
        now = GLib.DateTime.new_now_local()
        fmt = "%H:%M:%S" if util.gget(IFACE, "clock-format", "24h") == "24h" else "%I:%M:%S %p"
        self.now_lbl.set_label(now.format(fmt + "   %A, %e %B %Y"))
        return True

    def _zones(self, zones, cur):
        opts = [(z, timedate.tz_label(z)) for z in zones]
        if cur not in zones:
            opts.insert(0, (cur, timedate.tz_label(cur)))
        dd = Dropdown(opts, cur, lambda v: timedate.set_timezone(v, self._done), width=300)
        dd.set_enable_search(True)
        expr = Gtk.PropertyExpression.new(Gtk.StringObject, None, "string")
        dd.set_expression(expr)
        self.tz_row.set_control(dd)

    def _done(self, ok, _r=None):
        if not ok:
            toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                  else _("The change was not applied"))

    def _sync(self):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        timedate.set_ntp(False, lambda *_: timedate.set_ntp(True, lambda ok, *_: toast(
            self.box, _("Time synchronized") if ok else _("The change was not applied"))))


@register
class LanguagePage(Page):
    id = "language"
    parent = "time"
    title = "Language & region"
    keywords = "locale display language country format"
    index = [("display-language", "Fenestra display language", "ui language"),
             ("system-locale", "Regional format", "locale dates numbers")]

    def build(self, box):
        g = self.group(_("Language"))
        cur_ui = i18n.LANG
        r = SettingRow(_("Fenestra display language"),
                       _("Settings app language follows your session language (LANG)"),
                       "fs-local-language-symbolic",
                       control=value_label({"es": "Español", "en": "English"}.get(cur_ui, cur_ui)),
                       key="display-language")
        self.remember("display-language", r)
        g.add(r)
        loc = timedate.locale_info()
        self.loc_row = SettingRow(_("Regional format"), _("Fenestra formats dates and times based on your regional format"),
                                  "fs-globe-symbolic", control=value_label(timedate.locale_label(loc.get("LANG", ""))),
                                  key="system-locale")
        self.remember("system-locale", self.loc_row)
        g.add(self.loc_row)
        timedate.locales(lambda items: self._locales(items, loc.get("LANG", "")))
        g2 = self.group(_("Related settings"))
        self.ext_row(g2, _("Administrative language settings"), _("Login screen and new user accounts"),
                     "fs-options-symbolic", ["gnome-control-center", "system", "region"])
        self.nav_row(g2, "typing", _("Typing"), None, "fs-keyboard-symbolic", key="typing-link")

    def _locales(self, items, cur):
        opts = [(x, f"{timedate.locale_label(x)} — {x}") for x in items if "utf" in x.lower() or "." not in x]
        if not opts:
            return
        ids = [o[0] for o in opts]
        sel = cur if cur in ids else next((i for i in ids if i.lower().replace("utf-8", "utf8") ==
                                           cur.lower().replace("utf-8", "utf8")), None)
        if sel is None:
            opts.insert(0, (cur, timedate.locale_label(cur)))
            sel = cur

        def changed(v):
            def done(ok, _r):
                toast(self.box, _("Sign out to apply the new regional format") if ok else
                      _("This action is disabled in read-only mode") if util.READ_ONLY else
                      _("The change was not applied"))
            timedate.set_system_locale(v, done)
        dd = Dropdown(opts, sel, changed, width=280)
        dd.set_enable_search(True)
        dd.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        self.loc_row.set_control(dd)


@register
class TypingPage(Page):
    id = "typing"
    parent = "time"
    title = "Typing"
    keywords = "keyboard layout input sources language switch"
    index = [("layouts", "Keyboard layouts", "input sources language"),
             ("per-window", "Let me use a different input method for each app window", "switch")]

    def build(self, box):
        g = self.group(_("Keyboard layouts"))
        exp = ExpanderRow(_("Keyboard layouts"), _("Installed layouts, switch with Super+Space"),
                          "fs-keyboard-symbolic", key="layouts", expanded=True)
        self.remember("layouts", exp)
        g.add(exp)
        self.exp = exp
        self.names = _xkb_names()
        self._fill()
        util.gconnect(INPUT, "sources", self._fill)
        pw = gsetting_toggle(INPUT, "per-window")
        if pw:
            r = SettingRow(_("Let me use a different input method for each app window"), None,
                           "fs-window-multiple-symbolic", control=pw, key="per-window")
            self.remember("per-window", r)
            g.add(r)
        g2 = self.group(_("Related settings"))
        self.nav_row(g2, "fx-shortcuts", _("Keyboard shortcuts"), None, "fs-keyboard-symbolic")
        self.nav_row(g2, "a11y-keyboard", _("On-screen keyboard"), None, "fs-keyboard-symbolic", focus="osk")

    def _fill(self):
        exp = self.exp
        exp.clear()
        sources = util.gget(INPUT, "sources")
        if util.DEMO:
            from ..backends import demo
            sources = demo.INPUT_SOURCES
        if sources is None:
            exp.add(SettingRow(_("Not available"), None, None))
            return
        for i, (kind, ident) in enumerate(sources):
            ctrl = button(_("Remove"), lambda i=i: self._remove(i), css="small") if len(sources) > 1 else None
            exp.add(SettingRow(self.names.get(ident, ident), f"{kind}: {ident}", None, control=ctrl))
        exp.add(SettingRow(_("Add a keyboard"), None, None, control=button(_("Add a keyboard"), self._add)))

    def _add(self):
        have = {i for _k, i in (util.gget(INPUT, "sources") or [])}
        opts = sorted(((k, v) for k, v in self.names.items() if k not in have), key=lambda kv: kv[1].lower())
        if not opts:
            return
        dd = Dropdown(opts, opts[0][0], None, width=380)
        dd.set_enable_search(True)
        dd.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))

        def resp(r):
            if r != "primary":
                return
            ident = dd.selected_id()
            src = list(util.gget(INPUT, "sources") or [])
            if ident and ("xkb", ident) not in src:
                src.append(("xkb", ident))
                if not util.gset(INPUT, "sources", src):
                    toast(self.box, _("This action is disabled in read-only mode"))
        from ..widgets import ContentDialog, show_dialog
        show_dialog(self.box, ContentDialog(_("Add a keyboard"), _("Choose a keyboard layout"), primary=_("Add"),
                                            close=_("Cancel"), on_response=resp, extra=dd))

    def _remove(self, i):
        src = list(util.gget(INPUT, "sources") or [])
        if 0 <= i < len(src) and len(src) > 1:
            del src[i]
            if not util.gset(INPUT, "sources", src):
                toast(self.box, _("This action is disabled in read-only mode"))


def _xkb_names():
    names = {}
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse("/usr/share/X11/xkb/rules/evdev.xml").getroot()
        for layout in root.iter("layout"):
            ci = layout.find("configItem")
            if ci is None:
                continue
            name = ci.findtext("name")
            desc = ci.findtext("description")
            names[name] = desc
            vl = layout.find("variantList")
            if vl is not None:
                for v in vl.iter("variant"):
                    vci = v.find("configItem")
                    if vci is not None:
                        names[f"{name}+{vci.findtext('name')}"] = vci.findtext("description")
    except Exception:  # noqa: BLE001 - optional nicety
        pass
    return names

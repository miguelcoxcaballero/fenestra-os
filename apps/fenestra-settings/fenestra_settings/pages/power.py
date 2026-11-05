"""System › Power & battery."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..backends import power
from ..i18n import _
from ..widgets import Dropdown, ExpanderRow, SettingRow, label, not_available_row, progress
from .base import Page, register
from .common import gsetting_toggle

SESSION = "org.gnome.desktop.session"
PWR = "org.gnome.settings-daemon.plugins.power"
IFACE = "org.gnome.desktop.interface"

TIMEOUTS = [(60, "1 minute"), (120, "2 minutes"), (180, "3 minutes"), (300, "5 minutes"),
            (600, "10 minutes"), (900, "15 minutes"), (1200, "20 minutes"), (1800, "30 minutes"),
            (2700, "45 minutes"), (3600, "1 hour"), (7200, "2 hours"), (0, "Never")]

PROFILE_LABELS = {
    "power-saver": ("Best power efficiency", "fs-leaf"),
    "balanced": ("Balanced", ""),
    "performance": ("Best performance", ""),
}


def _timeout_opts():
    return [(v, _(t)) for v, t in TIMEOUTS]


@register
class PowerPage(Page):
    id = "power"
    parent = "system"
    title = "Power & battery"
    keywords = "battery sleep power mode energy saver screen off timeout charging"
    index = [
        ("battery", "Battery level", "charge percentage"),
        ("screen-sleep", "Screen and sleep", "timeout turn off display sleep suspend"),
        ("power-mode", "Power mode", "performance balanced power saver profile"),
        ("battery-percentage", "Show battery percentage", "top bar"),
        ("lid", "Lid & power button controls", "close lid"),
    ]

    def build(self, box):
        bat = power.battery()
        self.bat = bat
        if bat and bat["present"]:
            hero = Gtk.Box(spacing=24)
            hero.add_css_class("hero")
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            pct = f"{bat['percent']:.0f}%"
            top = Gtk.Box(spacing=12)
            top.append(label(pct, "big-number"))
            col.append(top)
            pb = progress(bat["percent"] / 100.0, "usage")
            pb.set_size_request(220, -1)
            col.append(pb)
            st = bat["state"]
            if st == 1:
                txt = _("Charging") + (f" · {power.fmt_duration(bat['time_to_full'])} " + _("until full")
                                       if bat["time_to_full"] else "")
            elif st == 4:
                txt = _("Fully charged")
            elif st == 2:
                txt = _("On battery") + (f" · {power.fmt_duration(bat['time_to_empty'])} " + _("remaining")
                                         if bat["time_to_empty"] else "")
            else:
                txt = _("Plugged in")
            col.append(label(txt, "caption"))
            hero.append(col)
            hero.key = "battery"
            self._rows["battery"] = hero
            box.append(hero)

        g = self.group(_("Power"))
        exp = ExpanderRow(_("Screen and sleep"), None, "fs-battery-charge-symbolic", key="screen-sleep",
                          expanded=True)
        self.remember("screen-sleep", exp)
        if util.has_key(SESSION, "idle-delay"):
            cur = util.gget(SESSION, "idle-delay", 300)
            opts = _timeout_opts()
            if cur not in [o[0] for o in opts]:
                opts.insert(0, (cur, f"{cur // 60} min"))
            exp.add(SettingRow(_("Turn off my screen after"), None, None,
                               control=Dropdown(opts, cur, lambda v: util.gset(SESSION, "idle-delay", int(v)))))
        for src, key in ((_("On battery power, put my device to sleep after"), "battery"),
                         (_("When plugged in, put my device to sleep after"), "ac")):
            if key == "battery" and not (bat and bat["present"]):
                continue
            tkey = f"sleep-inactive-{key}-timeout"
            typekey = f"sleep-inactive-{key}-type"
            if not util.has_key(PWR, tkey):
                continue
            stype = util.gget(PWR, typekey, "suspend")
            cur = util.gget(PWR, tkey, 900) if stype != "nothing" else 0
            opts = _timeout_opts()
            if cur not in [o[0] for o in opts]:
                opts.insert(0, (cur, f"{cur // 60} min"))

            def setter(v, tkey=tkey, typekey=typekey):
                v = int(v)
                if v == 0:
                    util.gset(PWR, typekey, "nothing")
                else:
                    util.gset(PWR, typekey, "suspend")
                    util.gset(PWR, tkey, v)
            exp.add(SettingRow(src, None, None, control=Dropdown(opts, cur, setter)))
        g.add(exp)

        active, profs = power.profiles()
        if active:
            opts = [(p, _(PROFILE_LABELS.get(p, (p.title(), ""))[0])) for p in profs]
            dd = Dropdown(opts, active, lambda v: power.set_profile(v))
            r = SettingRow(_("Power mode"), _("Optimize your device based on power use and performance"),
                           "fs-gauge-symbolic", control=dd, key="power-mode")
        else:
            r = not_available_row(_("Power mode"), _("power-profiles-daemon is not running"),
                                  "fs-gauge-symbolic")
            r.key = "power-mode"
        self.remember("power-mode", r)
        g.add(r)

        if bat and bat["present"]:
            gb = self.group(_("Battery"))
            t = gsetting_toggle(IFACE, "show-battery-percentage")
            if t:
                r = SettingRow(_("Show battery percentage"), _("Show the percentage next to the battery icon"),
                               "fs-battery-10-symbolic", control=t, key="battery-percentage")
                self.remember("battery-percentage", r)
                gb.add(r)
            saver = util.gget(PWR, "power-saver-profile-on-low-battery")
            if saver is not None:
                gb.add(SettingRow(_("Battery saver"),
                                  _("Turn battery saver on automatically when battery is low"),
                                  "fs-battery-10-symbolic",
                                  control=gsetting_toggle(PWR, "power-saver-profile-on-low-battery")))
        g2 = self.group(_("Related settings"))
        if util.has_key(PWR, "power-button-action"):
            dd = Dropdown([("suspend", _("Sleep")), ("hibernate", _("Hibernate")),
                           ("interactive", _("Ask me")), ("nothing", _("Do nothing"))],
                          util.gget(PWR, "power-button-action"),
                          lambda v: util.gset(PWR, "power-button-action", v))
            r = SettingRow(_("Pressing the power button will make my PC"), None, "fs-power-symbolic",
                           control=dd, key="lid")
            self.remember("lid", r)
            g2.add(r)
        self.ext_row(g2, _("More power options"), _("Automatic suspend, dim screen"), "fs-options-symbolic",
                     ["gnome-control-center", "power"])

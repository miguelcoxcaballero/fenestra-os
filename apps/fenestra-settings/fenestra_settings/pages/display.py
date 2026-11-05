"""System › Display."""
from __future__ import annotations

from gi.repository import Gdk

from .. import util
from ..backends import power
from ..i18n import _
from ..widgets import (Dropdown, ExpanderRow, SettingRow, Slider, button, label,
                       not_available_row, value_label)
from .base import Page, register
from .common import gsetting_toggle

COLOR = "org.gnome.settings-daemon.plugins.color"
IFACE = "org.gnome.desktop.interface"


@register
class DisplayPage(Page):
    id = "display"
    parent = "system"
    title = "Display"
    keywords = "monitor screen resolution scale brightness night light hdr refresh"
    index = [
        ("brightness", "Brightness", "screen backlight dim"),
        ("night-light", "Night light", "blue light warm color temperature"),
        ("scale", "Scale", "zoom size dpi text apps"),
        ("resolution", "Display resolution", "pixels screen size"),
        ("orientation", "Display orientation", "rotate landscape portrait"),
        ("multiple", "Multiple displays", "monitors extend duplicate"),
        ("advanced", "Advanced display", "refresh rate hz"),
    ]

    def build(self, box):
        g = self.group(_("Brightness & color"))
        self.bright_row = SettingRow(_("Brightness"), _("Adjust the brightness of the built-in display"),
                                     "fs-brightness-high-symbolic", key="brightness")
        self.remember("brightness", self.bright_row)
        g.add(self.bright_row)
        self._load_brightness()

        nl = gsetting_toggle(COLOR, "night-light-enabled")
        if nl is not None:
            exp = ExpanderRow(_("Night light"), _("Use warmer colors to help block blue light"),
                              "fs-weather-moon-symbolic", control=nl, key="night-light")
            self.remember("night-light", exp)
            if util.has_key(COLOR, "night-light-temperature"):
                temp = util.gget(COLOR, "night-light-temperature", 4000)
                # 6500K (off) .. 1700K (strongest). Strength 0..100.
                strength = round((6500 - temp) / (6500 - 1700) * 100)
                sl = Slider(0, 100, max(0, min(100, strength)),
                            lambda v: util.gset(COLOR, "night-light-temperature",
                                                int(6500 - v / 100 * (6500 - 1700))), width=220)
                exp.add(SettingRow(_("Strength"), None, None, control=sl))
            if util.has_key(COLOR, "night-light-schedule-automatic"):
                sched = Dropdown([("auto", _("Sunset to sunrise")), ("manual", _("Set hours"))],
                                 "auto" if util.gget(COLOR, "night-light-schedule-automatic") else "manual",
                                 lambda v: util.gset(COLOR, "night-light-schedule-automatic", v == "auto"))
                exp.add(SettingRow(_("Schedule night light"), None, None, control=sched))
                f = util.gget(COLOR, "night-light-schedule-from", 20.0)
                t = util.gget(COLOR, "night-light-schedule-to", 6.0)
                exp.add(SettingRow(_("Turn on"), None, None, control=value_label(_fmt_hour(f))))
                exp.add(SettingRow(_("Turn off"), None, None, control=value_label(_fmt_hour(t))))
            g.add(exp)
        else:
            g.add(not_available_row(_("Night light")))

        hdr = SettingRow(_("HDR"), _("More about HDR"), "fs-brightness-high-symbolic", chevron=True,
                         on_click=lambda: util.open_control_center("display"))
        g.add(hdr)

        g2 = self.group(_("Scale & layout"))
        mon = self._primary_monitor()
        scale_now = mon.get_scale() if mon else 1.0
        scales = [1.0, 1.25, 1.5, 1.75, 2.0]
        opts = [(str(s), f"{int(s * 100)}%" + (_(" (Recommended)") if s == 1.0 else "")) for s in scales]
        cur = min(scales, key=lambda s: abs(s - scale_now))
        sd = Dropdown(opts, str(cur), lambda _v: util.open_control_center("display"))
        r = SettingRow(_("Scale"), _("Change the size of text, apps, and other items"),
                       "fs-zoom-fit-symbolic", control=sd, key="scale")
        self.remember("scale", r)
        g2.add(r)
        res = "—"
        if mon:
            geo = mon.get_geometry()
            res = f"{int(geo.width * mon.get_scale())} × {int(geo.height * mon.get_scale())}"
        rd = Dropdown([("cur", res + _(" (Recommended)"))], "cur",
                      lambda _v: util.open_control_center("display"))
        rr = SettingRow(_("Display resolution"), _("Adjust the resolution to fit your connected display"),
                        "fs-resize-symbolic", control=rd, key="resolution")
        self.remember("resolution", rr)
        g2.add(rr)
        od = Dropdown([("l", _("Landscape")), ("p", _("Portrait")), ("lf", _("Landscape (flipped)")),
                       ("pf", _("Portrait (flipped)"))], "l",
                      lambda _v: util.open_control_center("display"))
        ro = SettingRow(_("Display orientation"), None, "fs-phone-laptop-symbolic", control=od,
                        key="orientation")
        self.remember("orientation", ro)
        g2.add(ro)

        monitors = Gdk.Display.get_default().get_monitors()
        n = monitors.get_n_items()
        mr = SettingRow(_("Multiple displays"),
                        _("{0} display(s) connected. Choose the presentation mode for your displays").format(n),
                        "fs-dual-screen-symbolic", chevron=True,
                        on_click=lambda: util.open_control_center("display"), key="multiple")
        self.remember("multiple", mr)
        g2.add(mr)

        g3 = self.group(_("Related settings"))
        adv = ExpanderRow(_("Advanced display"), _("Display information, refresh rate"),
                          "fs-desktop-symbolic", key="advanced")
        self.remember("advanced", adv)
        for i in range(n):
            m = monitors.get_item(i)
            geo = m.get_geometry()
            name = m.get_description() or m.get_model() or m.get_connector() or _("Display")
            hz = m.get_refresh_rate() / 1000.0
            sub = f"{int(geo.width * m.get_scale())} × {int(geo.height * m.get_scale())} · {hz:.2f} Hz"
            if m.get_connector():
                sub += f" · {m.get_connector()}"
            adv.add(SettingRow(name, sub, None))
        adv.add(SettingRow(_("Open advanced display settings"), None, None,
                           control=button(_("Open"), lambda: util.open_control_center("display"))))
        g3.add(adv)
        self.ext_row(g3, _("Graphics"), _("Default GPU, per-app GPU preference"), "fs-developer-board-symbolic",
                     ["gnome-control-center", "display"])
        g3.add(SettingRow(_("Text size"), _("Change the size of text that appears throughout the system"),
                          "fs-text-font-size-symbolic", chevron=True, on_click=lambda: self.go("textsize")))

    def _primary_monitor(self):
        mons = Gdk.Display.get_default().get_monitors()
        return mons.get_item(0) if mons.get_n_items() else None

    def _load_brightness(self):
        b = power.brightness()
        if b is None:
            self.bright_row.set_control(label(_("Not available"), "row-value"))
            self.bright_row.set_subtitle(_("This display does not support brightness control"))
            return
        sl = Slider(0, 100, b, lambda v: power.set_brightness(v), width=220)
        self.bright_row.set_control(sl)
        self.bright_slider = sl

    def on_show(self):
        if getattr(self, "bright_slider", None) is not None:
            b = power.brightness()
            if b is not None:
                self.bright_slider.set_value(b)


def _fmt_hour(h):
    hh = int(h)
    mm = int(round((h - hh) * 60))
    return f"{hh:02d}:{mm:02d}"


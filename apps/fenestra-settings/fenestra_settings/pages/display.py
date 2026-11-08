"""System › Display."""
from __future__ import annotations

from gi.repository import Gdk, GLib

from .. import util
from ..backends import adaptive_color
from ..backends import display as displayb
from ..backends import power, session
from ..i18n import _
from ..widgets import (ContentDialog, Dropdown, ExpanderRow, SettingRow, Slider, ToggleSwitch, button, label,
                       show_dialog, spinner, toast,
                       not_available_row, value_label)
from .base import Page, register
from .common import gsetting_dropdown, gsetting_toggle

COLOR = "org.gnome.settings-daemon.plugins.color"
IFACE = "org.gnome.desktop.interface"


@register
class DisplayPage(Page):
    id = "display"
    parent = "system"
    title = "Display"
    keywords = "monitor screen resolution scale brightness night light adaptive color hdr refresh"
    index = [
        ("brightness", "Brightness", "screen backlight dim"),
        ("adaptive-color", "Adaptive color", "ambient light sensor white point true tone color temperature"),
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

        # Windows 11 shows "Adaptive color" here on PCs with an ambient colour sensor, on by
        # default; Fenestra Shell follows the switch live (shell.conf [Display] AdaptiveColor).
        if session.supports("adaptive-color"):
            ac = SettingRow(_("Adaptive color"),
                            _("Automatically adjust the color of your screen based on lighting conditions"),
                            "fs-color-symbolic", key="adaptive-color",
                            control=ToggleSwitch(adaptive_color.enabled(), self._set_adaptive_color))
            self.remember("adaptive-color", ac)
            g.add(ac)

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
                hours = [(h / 2.0, _fmt_hour(h / 2.0)) for h in range(48)]
                for key, title, cur in (("night-light-schedule-from", _("Turn on"), f),
                                        ("night-light-schedule-to", _("Turn off"), t)):
                    opts = list(hours)
                    if cur not in [o[0] for o in opts]:
                        opts.append((cur, _fmt_hour(cur)))
                    exp.add(SettingRow(title, None, None, control=gsetting_dropdown(COLOR, key, opts, cast=float)))
            g.add(exp)
        else:
            g.add(not_available_row(_("Night light")))

        hdr = SettingRow(_("HDR"), _("More about HDR"), "fs-brightness-high-symbolic", chevron=True,
                         on_click=lambda: session.open_panel("display", self.window), key="hdr")
        g.add(hdr)

        g2 = self.group(_("Scale & layout"))
        self.scale_row = SettingRow(_("Scale"), _("Change the size of text, apps, and other items"),
                                    "fs-zoom-fit-symbolic", control=spinner(), key="scale")
        self.remember("scale", self.scale_row)
        g2.add(self.scale_row)
        self.res_row = SettingRow(_("Display resolution"), _("Adjust the resolution to fit your connected display"),
                                  "fs-resize-symbolic", control=spinner(), key="resolution")
        self.remember("resolution", self.res_row)
        g2.add(self.res_row)
        self.orient_row = SettingRow(_("Display orientation"), None, "fs-phone-laptop-symbolic", control=spinner(),
                                     key="orientation")
        self.remember("orientation", self.orient_row)
        g2.add(self.orient_row)
        self.rate_row = SettingRow(_("Refresh rate"), _("A higher rate gives smoother motion, but uses more power"),
                                   "fs-desktop-symbolic", control=spinner(), key="refresh")
        self.remember("refresh", self.rate_row)
        g2.add(self.rate_row)

        monitors = Gdk.Display.get_default().get_monitors()
        n = monitors.get_n_items()
        mr = SettingRow(_("Multiple displays"),
                        _("{0} display(s) connected. Choose the presentation mode for your displays").format(n),
                        "fs-dual-screen-symbolic", chevron=True,
                        on_click=lambda: session.open_panel("display", self.window), key="multiple")
        self.remember("multiple", mr)
        g2.add(mr)
        displayb.get_state(self._got_state)

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
                           control=button(_("Open"), lambda: session.open_panel("display", self.window)),
                           key="advanced-open"))
        g3.add(adv)
        self.ext_row(g3, _("Graphics"), _("Default GPU, per-app GPU preference"), "fs-developer-board-symbolic",
                     ["gnome-control-center", "display"])
        g3.add(SettingRow(_("Text size"), _("Change the size of text that appears throughout the system"),
                          "fs-text-font-size-symbolic", chevron=True, on_click=lambda: self.go("textsize")))

    # ------------------------------------------------------------------ mutter display config
    def _got_state(self, st):
        self.state = st
        if st is None or st.monitor() is None:
            for r in (self.scale_row, self.res_row, self.orient_row, self.rate_row):
                r.set_control(label(_("Not available"), "row-value"))
            return
        mon = st.monitor()
        lm = st.logical_for(mon.connector)
        cur = mon.current_mode
        pref = mon.preferred_mode
        scales = cur.scales if cur and cur.scales else [1.0, 2.0]
        rec = pref.preferred_scale if pref else 1.0
        opts = [(round(sc, 4), f"{round(sc * 100)}%" + (_(" (Recommended)") if abs(sc - rec) < 0.01 else ""))
                for sc in scales]
        now = min((o[0] for o in opts), key=lambda v: abs(v - (lm.scale if lm else 1.0)))
        self.scale_row.set_control(Dropdown(opts, now, lambda v: self._apply(scale=float(v))))
        res = displayb.resolutions(mon)
        ropts = [(mid, lab + (_(" (Recommended)") if pref and (m.width, m.height) == (pref.width, pref.height)
                              else "")) for mid, lab, m in res]
        cur_id = next((mid for mid, _l, m in res if cur and (m.width, m.height) == (cur.width, cur.height)), None)
        self.res_row.set_control(Dropdown(ropts, cur_id, lambda v: self._apply(mode_id=v), width=240))
        tr = {0: "landscape", 1: "portrait", 2: "landscape-flipped", 3: "portrait-flipped"}.get(
            lm.transform if lm else 0, "landscape")
        self.orient_row.set_control(Dropdown(
            [("landscape", _("Landscape")), ("portrait", _("Portrait")), ("landscape-flipped", _("Landscape (flipped)")),
             ("portrait-flipped", _("Portrait (flipped)"))], tr,
            lambda v: self._apply(transform=displayb.TRANSFORMS[v])))
        rates = displayb.refresh_rates(mon)
        self.rate_row.set_control(Dropdown([(m.id, f"{m.refresh:.2f} Hz" + (" (VRR)" if "+vrr" in m.id else ""))
                                            for m in rates], cur.id if cur else None,
                                           lambda v: self._apply(mode_id=v)))

    def _apply(self, **changes):
        st = self.state
        if st is None:
            return
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        mon = st.monitor()

        def done(ok, err):
            if not ok:
                toast(self.box, _("The change was not applied"))
                displayb.get_state(self._got_state)
                return
            self._keep_dialog(st)
        displayb.apply(st, mon.connector, done, **changes)

    def _keep_dialog(self, old_state):
        secs = [15]
        body = label("", wrap=True)

        def upd():
            body.set_label(_("Reverting to the previous display settings in {0} seconds.").format(secs[0]))
        upd()

        def revert():
            displayb.restore(old_state, lambda *_: displayb.get_state(self._got_state))

        def resp(r):
            GLib.source_remove(timer[0]) if timer[0] else None
            timer[0] = 0
            if r == "primary":
                displayb.get_state(self._got_state)
            else:
                revert()
        dlg = ContentDialog(_("Keep these display settings?"), None, primary=_("Keep changes"),
                            close=_("Revert"), on_response=resp, extra=body)

        def tick():
            secs[0] -= 1
            if secs[0] <= 0:
                timer[0] = 0
                dlg.respond("close")
                return False
            upd()
            return True
        timer = [GLib.timeout_add_seconds(1, tick)]
        show_dialog(self.box, dlg)

    def _set_adaptive_color(self, on):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        if not adaptive_color.set_enabled(on):
            toast(self.box, _("The change was not applied"))

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


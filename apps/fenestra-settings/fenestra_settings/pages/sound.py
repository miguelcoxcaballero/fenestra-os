"""System › Sound (PipeWire via wpctl)."""
from __future__ import annotations

from gi.repository import Gtk

from ..backends import audio
from ..i18n import _
from ..widgets import (ExpanderRow, SettingRow, Slider, ToggleSwitch, label,
                       not_available_row)
from .base import Page, register
from .common import gsetting_toggle

SOUND = "org.gnome.desktop.sound"


@register
class SoundPage(Page):
    id = "sound"
    parent = "system"
    title = "Sound"
    keywords = "audio volume speakers headphones microphone output input"
    index = [
        ("output", "Choose where to play sound", "output speakers headphones device"),
        ("volume", "Volume", "loud output level"),
        ("input", "Choose a device for speaking or recording", "input microphone mic"),
        ("input-volume", "Input volume", "microphone level"),
        ("alerts", "Alert sounds", "system sounds event beep"),
        ("overamplify", "Over-amplification", "volume above 100"),
    ]

    def build(self, box):
        if not audio.available():
            g = self.group(_("Output"))
            g.add(not_available_row(_("Sound"), _("wpctl (WirePlumber) is not installed")))
            return
        self.out_group = self.group(_("Output"))
        self.in_group = self.group(_("Input"))
        self.out_exp = ExpanderRow(_("Choose where to play sound"),
                                   _("Apps might have their own settings"),
                                   "fs-speaker-2-symbolic", key="output", expanded=True)
        self.remember("output", self.out_exp)
        self.out_group.add(self.out_exp)
        self.vol_row = SettingRow(_("Volume"), None, "fs-speaker-2-symbolic", key="volume")
        self.remember("volume", self.vol_row)
        self.out_group.add(self.vol_row)
        self.mute_row = SettingRow(_("Mute"), None, "fs-speaker-mute-symbolic")
        self.out_group.add(self.mute_row)

        self.in_exp = ExpanderRow(_("Choose a device for speaking or recording"),
                                  _("Apps might have their own settings"), "fs-mic-symbolic",
                                  key="input", expanded=True)
        self.remember("input", self.in_exp)
        self.in_group.add(self.in_exp)
        self.in_vol_row = SettingRow(_("Volume"), None, "fs-mic-symbolic", key="input-volume")
        self.remember("input-volume", self.in_vol_row)
        self.in_group.add(self.in_vol_row)

        adv = self.group(_("Advanced"))
        t = gsetting_toggle(SOUND, "event-sounds")
        if t:
            r = SettingRow(_("Alert sounds"), _("Play sounds for system events and alerts"),
                           "fs-alert-symbolic", control=t, key="alerts")
            self.remember("alerts", r)
            adv.add(r)
        t2 = gsetting_toggle(SOUND, "allow-volume-above-100-percent")
        if t2:
            r = SettingRow(_("Over-amplification"), _("Allow volume above 100%. May reduce quality"),
                           "fs-speaker-2-symbolic", control=t2, key="overamplify")
            self.remember("overamplify", r)
            adv.add(r)
        self.ext_row(adv, _("More sound settings"), _("Per-app volume, sound theme, balance"),
                     "fs-options-symbolic", ["gnome-control-center", "sound"])
        self.refresh()

    def on_show(self):
        if hasattr(self, "out_exp"):
            self.refresh()

    def refresh(self):
        audio.status(self._got)

    def _device_rows(self, exp, nodes, kind):
        exp.clear()
        if not nodes:
            exp.add(SettingRow(_("No devices found"), None, None))
            return None
        group = None
        default = None
        for n in nodes:
            rb = Gtk.CheckButton()
            if group is None:
                group = rb
            else:
                rb.set_group(group)
            rb.set_active(n.default)
            if n.default:
                default = n
            rb.connect("toggled", lambda b, nid=n.id: b.get_active() and audio.set_default(
                nid, lambda *_: self.refresh()))
            row = SettingRow(audio.pretty_name(n.name), None, None, image=rb)
            row.add_css_class("radio-row")
            exp.add(row)
        return default

    def _got(self, sinks, sources):
        out_def = self._device_rows(self.out_exp, sinks, "sink")
        in_def = self._device_rows(self.in_exp, sources, "source")
        if out_def:
            self.out_exp.header.set_subtitle(audio.pretty_name(out_def.name))
            sl = Slider(0, 100, out_def.volume * 100,
                        lambda v, nid=out_def.id: audio.set_volume(nid, v / 100.0), width=220,
                        icon_name="fs-speaker-2-symbolic")
            self.vol_row.set_control(sl)
            mt = ToggleSwitch(out_def.muted, lambda v, nid=out_def.id: audio.set_mute(nid, v))
            self.mute_row.set_control(mt)
        else:
            self.vol_row.set_control(label(_("Not available"), "row-value"))
        if in_def:
            self.in_exp.header.set_subtitle(audio.pretty_name(in_def.name))
            sl = Slider(0, 100, in_def.volume * 100,
                        lambda v, nid=in_def.id: audio.set_volume(nid, v / 100.0), width=220,
                        icon_name="fs-mic-symbolic")
            self.in_vol_row.set_control(sl)
        else:
            self.in_vol_row.set_control(label(_("Not available"), "row-value"))


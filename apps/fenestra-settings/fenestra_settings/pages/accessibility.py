"""Accessibility."""
from __future__ import annotations

from gi.repository import Gtk, Pango

from .. import util
from ..i18n import N_, _
from ..widgets import Dropdown, SettingRow, Slider, button, label
from .base import Page, register
from .common import gsetting_toggle

IFACE = "org.gnome.desktop.interface"
A11Y_APPS = "org.gnome.desktop.a11y.applications"
A11Y_IF = "org.gnome.desktop.a11y.interface"
A11Y_KB = "org.gnome.desktop.a11y.keyboard"
A11Y = "org.gnome.desktop.a11y"
WM = "org.gnome.desktop.wm.preferences"
MAG = "org.gnome.desktop.a11y.magnifier"


@register
class AccessibilityPage(Page):
    id = "accessibility"
    title = "Accessibility"
    keywords = "a11y vision hearing interaction"
    VISION = [
        ("textsize", N_("Text size"), N_("Text size throughout the system and apps"), "fs-text-font-size-symbolic"),
        ("visualeffects", N_("Visual effects"), N_("Scrollbars, transparency, animations, notification timeout"),
         "fs-sparkle-symbolic"),
        ("pointer", N_("Mouse pointer and touch"), N_("Mouse pointer color, size"), "fs-cursor-symbolic"),
        ("magnifier", N_("Magnifier"), N_("Zoom level, zoom increments"), "fs-zoom-fit-symbolic"),
        ("contrast", N_("Contrast themes"), N_("Color themes for low vision, light sensitivity"),
         "fs-dark-theme-symbolic"),
        ("narrator", N_("Narrator"), N_("Voice, verbosity, keyboard, braille"), "fs-speaker-2-symbolic"),
    ]
    HEARING = [
        ("a11y-audio", N_("Audio"), N_("Mono audio, audio notifications"), "fs-headphones-symbolic"),
    ]
    INTERACTION = [
        ("a11y-keyboard", N_("Keyboard"), N_("Sticky, filter, and toggle keys, on-screen keyboard"),
         "fs-keyboard-symbolic"),
    ]

    def build(self, box):
        for title, rows in ((_("Vision"), self.VISION), (_("Hearing"), self.HEARING),
                            (_("Interaction"), self.INTERACTION)):
            g = self.group(title)
            for pid, t, s, ic in rows:
                self.nav_row(g, pid, _(t), _(s), ic)


@register
class TextSizePage(Page):
    id = "textsize"
    parent = "accessibility"
    title = "Text size"
    keywords = "font scaling bigger larger text"
    index = [("text-size", "Text size", "scaling factor bigger")]

    def build(self, box):
        prev = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        prev.add_css_class("card")
        prev.add_css_class("padded")
        prev.append(label(_("Text size preview"), "caption"))
        self.preview = label(_("Drag the slider until the text here is easy for you to read"), wrap=True)
        self.preview.set_margin_top(12)
        self.preview.set_margin_bottom(12)
        prev.append(self.preview)
        box.append(prev)
        g = self.group()
        g.set_margin_top(4)
        cur = util.gget(IFACE, "text-scaling-factor", 1.0)
        sl = Slider(100, 225, round(cur * 100), None, step=5, width=280, fmt="{:.0f}%")
        sl.scale.connect("value-changed", lambda s: self._preview(s.get_value()))
        apply = button(_("Apply"), lambda: util.gset(IFACE, "text-scaling-factor", round(sl.get_value()) / 100.0))
        sl.apply_button = apply  # like the reference UI, the size is applied with "Apply"
        ctrl = Gtk.Box(spacing=12)
        ctrl.append(sl)
        ctrl.append(apply)
        r = SettingRow(_("Text size"), None, "fs-text-font-size-symbolic", control=ctrl, key="text-size")
        self.remember("text-size", r)
        g.add(r)
        self._preview(cur * 100)

    def _preview(self, v):
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_scale_new(v / 100.0))
        self.preview.set_attributes(attrs)


@register
class VisualEffectsPage(Page):
    id = "visualeffects"
    parent = "accessibility"
    title = "Visual effects"
    keywords = "animations transparency scrollbars motion"
    index = [("animations", "Animation effects", "motion reduce"),
             ("scrollbars", "Always show scrollbars", "overlay scrollbars")]

    def build(self, box):
        g = self.group()
        sb = gsetting_toggle(IFACE, "overlay-scrolling", invert=True)
        if sb:
            r = SettingRow(_("Always show scrollbars"), None, "fs-options-symbolic", control=sb, key="scrollbars")
            self.remember("scrollbars", r)
            g.add(r)
        an = gsetting_toggle(IFACE, "enable-animations")
        if an:
            r = SettingRow(_("Animation effects"), None, "fs-sparkle-symbolic", control=an, key="animations")
            self.remember("animations", r)
            g.add(r)
        rm = gsetting_toggle(A11Y_IF, "show-status-shapes")
        if rm:
            g.add(SettingRow(_("Show status shapes"), _("Add shapes to on/off indicators"), "fs-circle-half-fill-symbolic",
                             control=rm))


@register
class PointerPage(Page):
    id = "pointer"
    parent = "accessibility"
    title = "Mouse pointer and touch"
    keywords = "cursor size bigger pointer locate"
    index = [("cursor-size", "Size", "pointer size bigger cursor"),
             ("locate", "Locate pointer", "ctrl highlight")]

    SIZES = [(24, N_("Default")), (32, N_("Medium")), (48, N_("Large")), (64, N_("Larger")), (96, N_("Largest"))]

    def build(self, box):
        g = self.group(_("Mouse pointer"))
        cur = util.gget(IFACE, "cursor-size", 24)
        opts = [(v, _(t)) for v, t in self.SIZES]
        if cur not in [o[0] for o in opts]:
            opts.insert(0, (cur, str(cur)))
        r = SettingRow(_("Size"), None, "fs-cursor-symbolic",
                       control=Dropdown(opts, cur, lambda v: util.gset(IFACE, "cursor-size", int(v))), key="cursor-size")
        self.remember("cursor-size", r)
        g.add(r)
        lp = gsetting_toggle(IFACE, "locate-pointer")
        if lp:
            r = SettingRow(_("Locate pointer"), _("Show the location of the pointer when you press Ctrl"),
                           "fs-cursor-symbolic", control=lp, key="locate")
            self.remember("locate", r)
            g.add(r)


@register
class MagnifierPage(Page):
    id = "magnifier"
    parent = "accessibility"
    title = "Magnifier"
    keywords = "zoom screen magnify"
    index = [("magnifier", "Magnifier", "zoom")]

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(A11Y_APPS, "screen-magnifier-enabled")
        if t:
            r = SettingRow(_("Magnifier"), _("Zoom in on parts of the screen (Super+Alt+8)"), "fs-zoom-fit-symbolic",
                           control=t, key="magnifier")
            self.remember("magnifier", r)
            g.add(r)
        if util.has_key(MAG, "mag-factor"):
            g.add(SettingRow(_("Zoom level"), None, "fs-zoom-fit-symbolic",
                             control=Slider(1, 8, util.gget(MAG, "mag-factor", 2.0),
                                            lambda v: util.gset(MAG, "mag-factor", float(v)), step=0.25,
                                            fmt="{:.2f}×", width=200)))


@register
class ContrastPage(Page):
    id = "contrast"
    parent = "accessibility"
    title = "Contrast themes"
    keywords = "high contrast colors"
    index = [("high-contrast", "High contrast", "contrast theme")]

    def build(self, box):
        g = self.group()
        t = gsetting_toggle(A11Y_IF, "high-contrast")
        if t:
            r = SettingRow(_("High contrast"), _("Use distinct colors for text and controls"), "fs-dark-theme-symbolic",
                           control=t, key="high-contrast")
            self.remember("high-contrast", r)
            g.add(r)


@register
class NarratorPage(Page):
    id = "narrator"
    parent = "accessibility"
    title = "Narrator"
    keywords = "screen reader orca speech blind"
    index = [("screen-reader", "Narrator", "screen reader orca")]

    def build(self, box):
        g = self.group(_("Use Narrator"))
        t = gsetting_toggle(A11Y_APPS, "screen-reader-enabled")
        if t:
            r = SettingRow(_("Narrator"), _("Read aloud what's on the screen (Super+Alt+S)"), "fs-speaker-2-symbolic",
                           control=t, key="screen-reader")
            self.remember("screen-reader", r)
            g.add(r)
        if util.have("orca"):
            self.ext_row(g, _("Narrator settings"), _("Voice, speed and verbosity"), "fs-options-symbolic",
                         ["orca", "-s"])


@register
class A11yAudioPage(Page):
    id = "a11y-audio"
    parent = "accessibility"
    title = "Audio"
    keywords = "mono visual alerts flash hearing"
    index = [("visual-bell", "Flash the screen during audio notifications", "visual alert")]

    def build(self, box):
        g = self.group()
        vb = gsetting_toggle(WM, "visual-bell")
        if vb:
            r = SettingRow(_("Flash the screen during audio notifications"), None, "fs-alert-symbolic",
                           control=vb, key="visual-bell")
            self.remember("visual-bell", r)
            g.add(r)
        g.add(SettingRow(_("Sound settings"), None, "fs-speaker-2-symbolic", chevron=True,
                         on_click=lambda: self.go("sound")))


@register
class A11yKeyboardPage(Page):
    id = "a11y-keyboard"
    parent = "accessibility"
    title = "Keyboard"
    keywords = "sticky keys slow keys bounce on-screen keyboard osk"
    index = [("osk", "On-screen keyboard", "touch keyboard virtual"),
             ("sticky", "Sticky keys", "modifier"), ("slow", "Filter keys", "slow keys bounce")]

    def build(self, box):
        g = self.group()
        for key, schema, sk, title, sub in (
                ("osk", A11Y_APPS, "screen-keyboard-enabled", _("On-screen keyboard"),
                 _("Use a keyboard on the screen")),
                ("sticky", A11Y_KB, "stickykeys-enable", _("Sticky keys"),
                 _("Press one key at a time for keyboard shortcuts")),
                ("slow", A11Y_KB, "slowkeys-enable", _("Filter keys"),
                 _("Ignore brief or repeated keystrokes")),
                ("toggle", A11Y_KB, "togglekeys-enable", _("Toggle keys"),
                 _("Play a sound when you press Caps lock or Num lock"))):
            t = gsetting_toggle(schema, sk)
            if t:
                r = SettingRow(title, sub, "fs-keyboard-symbolic", control=t, key=key)
                self.remember(key, r)
                g.add(r)

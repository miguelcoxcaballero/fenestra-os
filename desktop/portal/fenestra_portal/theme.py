# SPDX-License-Identifier: GPL-3.0-or-later
"""Light/dark + accent for the portal dialogs; same rules as Fenestra Settings and Store.

The accent follows GNOME's accent-color, or Fenestra's custom accent
(org.fenestra.desktop accent-color-custom) when set. Colours reach style.css as CSS
custom properties; the portal is long-lived, so changes are followed live.
"""
from __future__ import annotations

import colorsys
import os

from gi.repository import Gdk, Gio, Gtk

from . import metrics

IFACE = "org.gnome.desktop.interface"
FENESTRA = "org.fenestra.desktop"
HERE = os.path.dirname(os.path.abspath(__file__))

_settings_cache: dict[str, Gio.Settings | None] = {}


def _gsettings(schema_id: str):
    if schema_id not in _settings_cache:
        src = Gio.SettingsSchemaSource.get_default()
        schema = src.lookup(schema_id, True) if src else None
        _settings_cache[schema_id] = Gio.Settings.new(schema_id) if schema else None
    return _settings_cache[schema_id]


def gget(schema_id, key, default):
    s = _gsettings(schema_id)
    if s is None or not s.props.settings_schema.has_key(key):
        return default
    try:
        return s.get_value(key).unpack()
    except Exception:  # noqa: BLE001 - a broken key must not break printing
        return default


def gconnect(schema_id, key, cb):
    s = _gsettings(schema_id)
    if s is not None and s.props.settings_schema.has_key(key):
        s.connect(f"changed::{key}", cb)


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(h):
    c = [v / 255 for v in _hex_to_rgb(h)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b):
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def custom_variants(base):
    """(light-mode accent, dark-mode accent) for a custom hex; mirrors Fenestra Settings."""
    r, g, b = (v / 255 for v in _hex_to_rgb(base))
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    def to_hex(l_):
        return "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l_, s))
    lt = l - 0.08
    while lt > 0.05 and _contrast(to_hex(lt), "#ffffff") < 4.5:
        lt -= 0.01
    dark = base.lower()
    while _contrast(dark, "#202020") < 3:
        dr, dg, db = _hex_to_rgb(dark)
        dark = "#%02x%02x%02x" % tuple(round(v + (255 - v) * 0.1) for v in (dr, dg, db))
    return to_hex(lt), dark


def on_accent(h):
    return "#000000" if _lum(h) > 0.25 else "#ffffff"


class ThemeManager:
    def __init__(self, override: str | None = None, fixed_accent: bool = False):
        self.override = override
        self.fixed_accent = fixed_accent
        self.listeners = []
        self.provider = Gtk.CssProvider()
        self.base = Gtk.CssProvider()
        display = Gdk.Display.get_default()
        self.base.connect("parsing-error", self._on_css_error)
        self.base.load_from_path(os.path.join(HERE, "style.css"))
        Gtk.StyleContext.add_provider_for_display(display, self.base, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        Gtk.StyleContext.add_provider_for_display(display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
        Gtk.IconTheme.get_for_display(display).add_search_path(os.path.join(HERE, "icons"))
        for schema, key in ((IFACE, "color-scheme"), (IFACE, "accent-color"), (FENESTRA, "accent-color-custom")):
            gconnect(schema, key, self.apply)
        self.apply()

    @staticmethod
    def _on_css_error(_prov, section, error):
        loc = section.get_start_location()
        print(f"style.css:{loc.lines + 1}:{loc.line_chars}: {error.message}")

    @property
    def dark(self) -> bool:
        if self.override:
            return self.override == "dark"
        return gget(IFACE, "color-scheme", "default") == "prefer-dark"

    def accent_name(self) -> str:
        if self.fixed_accent:
            return "blue"
        c = gget(FENESTRA, "accent-color-custom", "") or ""
        return c if len(c) == 7 and c.startswith("#") else gget(IFACE, "accent-color", "blue")

    def accent_hex(self) -> str:
        name = self.accent_name()
        if name.startswith("#"):
            light_hex, dark_hex = custom_variants(name)
        else:
            light_hex, dark_hex = metrics.ACCENTS.get(name, metrics.ACCENTS["blue"])
        return dark_hex if self.dark else light_hex

    def apply(self, *_):
        dark = self.dark
        pal = dict(metrics.DARK if dark else metrics.LIGHT)
        acc = self.accent_hex()
        r, g, b = _hex_to_rgb(acc)
        pal["accent"] = acc
        pal["accent-hover"] = f"rgba({r},{g},{b},0.9)"
        pal["accent-press"] = f"rgba({r},{g},{b},0.8)"
        pal["on-accent"] = on_accent(acc)
        name = self.accent_name()
        if name in metrics.ACCENT_TEXT:
            pal["accent-text"] = metrics.ACCENT_TEXT[name][1 if dark else 0]
        else:
            pal["accent-text"] = acc
        self.pal = pal
        css = ":root {\n" + "".join(f"  --{k}: {v};\n" for k, v in pal.items()) + "}\n"
        css += geometry_css()
        self.provider.load_from_string(css)
        gs = Gtk.Settings.get_default()
        if gs is not None:
            try:
                if gs.find_property("gtk-interface-color-scheme") is not None:
                    gs.set_property("gtk-interface-color-scheme",
                                    Gtk.InterfaceColorScheme.DARK if dark else Gtk.InterfaceColorScheme.LIGHT)
                else:
                    gs.set_property("gtk-application-prefer-dark-theme", dark)
            except (TypeError, AttributeError):
                pass
            if gs.props.gtk_theme_name != "Default":
                gs.props.gtk_theme_name = "Default"
        for cb in list(self.listeners):
            cb()

    def connect(self, cb):
        self.listeners.append(cb)


def geometry_css() -> str:
    """Every size of style.css, from metrics.py."""
    m = metrics
    ring = f"0 0 0 {m.FOCUS_GAP}px var(--focus-gap), 0 0 0 {m.FOCUS_GAP + m.FOCUS_RING}px var(--focus)"
    ch, ich = m.CONTROL_HEIGHT - 2, m.ICON_CONTROL_HEIGHT - 2
    pill_w, pill_h = m.FOCUS_PILL
    mp_w, mp_h = m.MENU_PILL
    tw, th = m.TOGGLE_SIZE
    knob_m = (th - m.TOGGLE_KNOB) // 2
    hover_m = (th - m.TOGGLE_KNOB_HOVER) // 2
    return f"""
window.fenestra-print {{ font-family: {m.FONT_TEXT}; font-size: {m.TEXT_SIZE}px; }}
.print-title {{ font-size: {m.HEADING_SIZE}px; font-weight: {m.HEADING_WEIGHT}; }}
button.print-close {{ min-width: {m.CLOSE_BOX[2]}px; min-height: {m.CLOSE_BOX[3]}px; }}
button.print-nav {{ min-width: {m.HEADER_BUTTON}px; min-height: {m.HEADER_BUTTON}px; }}
dropdown.print-dropdown > button {{
  min-height: {ch}px; padding: 0 {m.CHEVRON_PAD}px 0 {m.CONTROL_PAD_X}px; border-width: 1px;
  border-radius: {m.CONTROL_RADIUS}px;
}}
dropdown.print-dropdown.print-icon-combo > button {{ min-height: {ich}px; padding-left: {m.ICON_CONTROL_PAD_X}px; }}
dropdown.print-dropdown > button:focus-visible {{
  box-shadow: {ring}; background-size: {pill_w}px {pill_h}px; background-position: 0 center;
}}
dropdown.print-dropdown > button arrow,
dropdown.print-dropdown > button > box > image:last-child {{
  min-width: 16px; min-height: 16px; -gtk-icon-size: 16px;
}}
.print-item-label {{ margin-bottom: {m.TEXT_RAISE}px; }}
.print-icon-combo .print-item-label {{ margin-bottom: {m.ICON_TEXT_RAISE}px; }}
.print-item-icon {{ -gtk-icon-size: 16px; margin-right: {m.ICON_GAP}px; margin-bottom: 2px; }}
popover.print-menu .print-item-icon {{ margin-bottom: 0; }}
.print-footer checkbutton.print-check check {{ margin-bottom: 4px; }}
popover.print-menu > contents {{
  border-width: 1px; border-radius: {m.MENU_RADIUS}px; padding: {m.MENU_PAD[0]}px {m.MENU_PAD[1]}px;
}}
popover.print-menu listview > row {{
  min-height: {m.MENU_ROW_HEIGHT}px; margin: {m.MENU_ROW_MARGIN}px 0; padding: 0 0 0 {m.MENU_ROW_PAD_X}px;
  border-radius: {m.CONTROL_RADIUS}px;
}}
popover.print-menu.print-icon-menu listview > row {{ min-height: {m.MENU_ICON_ROW_HEIGHT}px; }}
popover.print-menu listview > row:selected {{ background-size: {mp_w}px {mp_h}px; background-position: {m.MENU_PILL_X}px center; }}
popover.print-menu .print-item-label {{ margin-bottom: 0; }}
entry.print-entry, spinbutton.print-spin {{
  min-height: {ch}px; border-width: 1px; border-radius: {m.CONTROL_RADIUS}px; padding: 0 0 0 {m.CONTROL_PAD_X}px;
}}
entry.print-entry {{ padding-right: {m.CONTROL_PAD_X}px; }}
spinbutton.print-spin > button {{ min-width: {ch - 2}px; min-height: {ch - 6}px; margin: 3px 3px 3px 0; border-radius: {m.CONTROL_RADIUS}px; }}
checkbutton.print-check check {{
  min-width: {m.CHECK_SIZE - 2}px; min-height: {m.CHECK_SIZE - 2}px; margin: 0 {m.CHECK_TEXT_GAP}px 0 0;
  border-width: 1px; border-radius: {m.CONTROL_RADIUS}px; -gtk-icon-size: 12px;
}}
checkbutton.print-check {{ border-spacing: 0; }}
.print-footer checkbutton.print-check label {{ line-height: {m.CHECK_LINE_HEIGHT}px; margin-top: {m.TEXT_NUDGE}px; }}
switch.print-switch {{ min-width: {tw}px; min-height: {th}px; border-radius: {th // 2}px; }}
switch.print-switch > slider {{
  min-width: {m.TOGGLE_KNOB}px; min-height: {m.TOGGLE_KNOB}px; margin: {knob_m}px; border-radius: {m.TOGGLE_KNOB}px;
}}
switch.print-switch:hover > slider {{
  min-width: {m.TOGGLE_KNOB_HOVER}px; min-height: {m.TOGGLE_KNOB_HOVER}px; margin: {hover_m}px;
}}
button.print-link {{ padding: 0 1px; border-radius: {m.CONTROL_RADIUS - 1}px; min-height: {m.TEXT_LINK_HEIGHT}px; }}
button.print-link.print-icon-link {{ min-height: {m.LINK_HEIGHT}px; }}
button.print-link image {{ -gtk-icon-size: {m.LINK_ICON}px; margin: 0 {m.LINK_ICON_GAP}px 0 1px; }}
.print-preview-box {{ border-width: 1px; border-radius: {m.CONTROL_RADIUS}px; }}
.print-footer {{ min-height: {m.FOOTER_HEIGHT - 1}px; border-top-width: 1px; }}
button.fluent-button {{
  min-height: {ch}px; padding: 0 12px; border-width: 1px; border-radius: {m.CONTROL_RADIUS}px;
}}
dropdown.print-dropdown > button:focus-visible, button.fluent-button:focus-visible,
button.print-link:focus-visible, button.print-nav:focus-visible, button.print-close:focus-visible,
checkbutton.print-check:focus-visible check, switch.print-switch:focus-visible {{ box-shadow: {ring}; }}
switch.print-switch:focus-visible:not(:checked) {{
  box-shadow: inset 0 0 0 1px var(--toggle-outline), {ring};
}}
"""


_manager: ThemeManager | None = None


def init(override=None, fixed_accent=False) -> ThemeManager:
    global _manager
    _manager = ThemeManager(override, fixed_accent)
    return _manager


def get() -> ThemeManager:
    return _manager

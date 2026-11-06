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

    def accent_hex(self) -> str:
        if self.fixed_accent:
            name = "blue"
        else:
            c = gget(FENESTRA, "accent-color-custom", "") or ""
            name = c if len(c) == 7 and c.startswith("#") else gget(IFACE, "accent-color", "blue")
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
        pal["accent-text"] = acc
        pv = metrics.PREVIEW_DARK if dark else metrics.PREVIEW_LIGHT
        pal["preview-bg"] = "#%02x%02x%02x" % tuple(round(v * 255) for v in pv["background"])
        self.pal = pal
        css = ":root {\n" + "".join(f"  --{k}: {v};\n" for k, v in pal.items()) + "}\n"
        css += (f"window.fenestra-print {{ font-family: {metrics.FONT_TEXT}; }}\n"
                f".print-heading {{ font-family: {metrics.FONT_DISPLAY}; font-size: {metrics.HEADING_SIZE}px; }}\n"
                f".print-summary {{ font-size: {metrics.SUMMARY_SIZE}px; }}\n"
                f".print-footer {{ min-height: {metrics.FOOTER_HEIGHT}px; }}\n"
                f"dropdown.print-dropdown > button, spinbutton.print-spin, entry.print-entry"
                f" {{ min-height: {metrics.CONTROL_HEIGHT - 2}px; }}\n"
                f"button.print-button {{ min-width: {metrics.BUTTON_MIN_WIDTH}px; min-height: {metrics.CONTROL_HEIGHT}px; }}\n")
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


_manager: ThemeManager | None = None


def init(override=None, fixed_accent=False) -> ThemeManager:
    global _manager
    _manager = ThemeManager(override, fixed_accent)
    return _manager


def get() -> ThemeManager:
    return _manager

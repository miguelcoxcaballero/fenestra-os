"""Light/dark + accent handling, the same palette and accent rules as Fenestra Settings.

The accent follows GNOME's accent-color, or Fenestra's custom accent
(org.fenestra.desktop accent-color-custom, shipped with fenestra-tray) when set. Colours
reach style.css as CSS custom properties.
"""
from __future__ import annotations

import colorsys
import os

from gi.repository import Gdk, Gtk

from . import util

IFACE = "org.gnome.desktop.interface"
FENESTRA = "org.fenestra.desktop"

# GNOME accent-color -> (light-mode accent, dark-mode accent); same values as Fenestra Settings
ACCENTS = {
    "blue": ("#0067c0", "#4cc2ff"), "teal": ("#00777a", "#3fd5d9"), "green": ("#107c10", "#6ccb5f"),
    "yellow": ("#8a6100", "#ffd04a"), "orange": ("#c24e00", "#ff9e5e"), "red": ("#c42b1c", "#ff99a4"),
    "pink": ("#bf0077", "#ff8ad8"), "purple": ("#744da9", "#c8a8ff"), "slate": ("#4a5a70", "#a9b8cc"),
}

DARK = {
    "bg": "#202020", "bg-grad-a": "#1c2027", "bg-grad-b": "#202020", "bg-grad-c": "#221f22",
    "card": "rgba(255,255,255,0.051)", "card-hover": "rgba(255,255,255,0.083)", "card-press": "rgba(255,255,255,0.03)",
    "card-border": "rgba(0,0,0,0.20)", "card-edge": "rgba(255,255,255,0.06)",
    "fg": "#ffffff", "fg2": "#c5c5c5", "fg3": "#7e7e7e",
    "ctl": "rgba(255,255,255,0.061)", "ctl-hover": "rgba(255,255,255,0.084)", "ctl-press": "rgba(255,255,255,0.033)",
    "ctl-border": "rgba(255,255,255,0.07)", "ctl-border-bottom": "rgba(255,255,255,0.05)",
    "input": "rgba(255,255,255,0.061)", "input-focus": "#1f1f1f", "input-bottom": "rgba(255,255,255,0.54)",
    "subtle-hover": "rgba(255,255,255,0.061)", "subtle-press": "rgba(255,255,255,0.042)",
    "subtle-select": "rgba(255,255,255,0.061)", "toggle-off": "rgba(255,255,255,0.78)",
    "toggle-off-bg": "rgba(0,0,0,0.10)", "divider": "rgba(255,255,255,0.084)", "popover": "#2c2c2c",
    "popover-border": "rgba(0,0,0,0.35)", "trough": "rgba(255,255,255,0.20)", "shadow": "rgba(0,0,0,0.30)",
    "danger": "#ff99a4", "success": "#6ccb5f", "warning": "#fce100", "caution-bg": "rgba(252,225,0,0.08)",
    "close-hover": "#c42b1c", "shot-bg": "#161616", "badge-flathub": "rgba(76,194,255,0.16)",
    "badge-fedora": "rgba(108,203,95,0.16)", "badge-flathub-fg": "#9fdcff", "badge-fedora-fg": "#a6e39b",
}

LIGHT = {
    "bg": "#f3f3f3", "bg-grad-a": "#eef1f7", "bg-grad-b": "#f3f3f3", "bg-grad-c": "#f6f2f3",
    "card": "rgba(255,255,255,0.70)", "card-hover": "rgba(249,249,249,0.50)", "card-press": "rgba(249,249,249,0.30)",
    "card-border": "rgba(0,0,0,0.07)", "card-edge": "rgba(255,255,255,0.0)",
    "fg": "#1b1b1b", "fg2": "#5d5d5d", "fg3": "#a0a0a0",
    "ctl": "rgba(255,255,255,0.70)", "ctl-hover": "rgba(249,249,249,0.50)", "ctl-press": "rgba(249,249,249,0.30)",
    "ctl-border": "rgba(0,0,0,0.073)", "ctl-border-bottom": "rgba(0,0,0,0.16)",
    "input": "rgba(255,255,255,0.70)", "input-focus": "#ffffff", "input-bottom": "rgba(0,0,0,0.45)",
    "subtle-hover": "rgba(0,0,0,0.037)", "subtle-press": "rgba(0,0,0,0.024)", "subtle-select": "rgba(0,0,0,0.055)",
    "toggle-off": "rgba(0,0,0,0.62)", "toggle-off-bg": "rgba(0,0,0,0.024)", "divider": "rgba(0,0,0,0.08)",
    "popover": "#f9f9f9", "popover-border": "rgba(0,0,0,0.12)", "trough": "rgba(0,0,0,0.12)",
    "shadow": "rgba(0,0,0,0.14)", "danger": "#c42b1c", "success": "#0f7b0f", "warning": "#9d5d00",
    "caution-bg": "rgba(255,244,206,0.7)", "close-hover": "#c42b1c", "shot-bg": "#e6e6e6",
    "badge-flathub": "rgba(0,103,192,0.10)", "badge-fedora": "rgba(16,124,16,0.10)",
    "badge-flathub-fg": "#004f94", "badge-fedora-fg": "#0b5e0b",
}


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
    def __init__(self, override: str | None = None):
        self.override = override
        self.listeners = []
        self.provider = Gtk.CssProvider()
        self.base = Gtk.CssProvider()
        display = Gdk.Display.get_default()
        self.base.connect("parsing-error", self._on_css_error)
        self.base.load_from_path(os.path.join(util.data_dir(), "style.css"))
        Gtk.StyleContext.add_provider_for_display(display, self.base, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        Gtk.StyleContext.add_provider_for_display(display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
        it = Gtk.IconTheme.get_for_display(display)
        it.add_search_path(os.path.join(util.data_dir(), "icons", "ui"))
        it.add_search_path(os.path.join(util.data_dir(), "icons", "hicolor", "scalable", "apps"))
        util.gconnect(IFACE, "color-scheme", self.apply)
        util.gconnect(IFACE, "accent-color", self.apply)
        util.gconnect(FENESTRA, "accent-color-custom", self.apply)
        self.apply()

    @staticmethod
    def _on_css_error(_prov, section, error):
        loc = section.get_start_location()
        print(f"style.css:{loc.lines + 1}:{loc.line_chars}: {error.message}")

    @property
    def dark(self) -> bool:
        if self.override:
            return self.override == "dark"
        return util.gget(IFACE, "color-scheme", "default") == "prefer-dark"

    def accent_hex(self) -> str:
        if util.DEMO:
            name = "blue"
        else:
            c = util.gget(FENESTRA, "accent-color-custom", "") or ""
            name = c if len(c) == 7 and c.startswith("#") else util.gget(IFACE, "accent-color", "blue")
        if name.startswith("#"):
            light_hex, dark_hex = custom_variants(name)
        else:
            light_hex, dark_hex = ACCENTS.get(name, ACCENTS["blue"])
        return dark_hex if self.dark else light_hex

    def apply(self, *_):
        dark = self.dark
        pal = dict(DARK if dark else LIGHT)
        acc = self.accent_hex()
        r, g, b = _hex_to_rgb(acc)
        pal["accent"] = acc
        pal["accent-hover"] = f"rgba({r},{g},{b},0.9)"
        pal["accent-press"] = f"rgba({r},{g},{b},0.8)"
        pal["accent-soft"] = f"rgba({r},{g},{b},0.16)"
        pal["accent-fg"] = on_accent(acc)
        pal["accent-text"] = acc
        self.pal = pal
        css = ":root {\n" + "".join(f"  --{k}: {v};\n" for k, v in pal.items()) + "}\n"
        css += ("window.fenestra-store { background-image: linear-gradient(120deg, "
                f"{pal['bg-grad-a']} 0%, {pal['bg-grad-b']} 45%, {pal['bg-grad-c']} 100%); }}\n")
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


def init(override=None) -> ThemeManager:
    global _manager
    _manager = ThemeManager(override)
    return _manager


def get() -> ThemeManager:
    return _manager

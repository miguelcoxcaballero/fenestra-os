"""Light/dark palettes and accent colour, exported as CSS custom properties for style.css.

Follows org.gnome.desktop.interface color-scheme / accent-color and Fenestra's own
org.fenestra.desktop accent-color-custom live, unless Settings > App theme forces one."""
from __future__ import annotations

import colorsys
import os

from gi.repository import Gdk, Gtk

from . import util

IFACE = "org.gnome.desktop.interface"
FENESTRA = "org.fenestra.desktop"

ACCENTS = {  # GNOME accent-color -> (light-mode accent, dark-mode accent)
    "blue": ("#0067c0", "#4cc2ff"), "teal": ("#00777a", "#3fd5d9"), "green": ("#107c10", "#6ccb5f"),
    "yellow": ("#8a6100", "#ffd04a"), "orange": ("#c24e00", "#ff9e5e"), "red": ("#c42b1c", "#ff99a4"),
    "pink": ("#bf0077", "#ff8ad8"), "purple": ("#744da9", "#c8a8ff"), "slate": ("#4a5a70", "#a9b8cc"),
}

LIGHT = {
    "bg": "#f3f3f3", "bar": "#f9f9f9", "bar-line": "#ebebeb", "sep": "#eaeaea",
    "fg": "#1a1a1a", "fg2": "#5f5f5f", "fg3": "#9d9d9d", "label": "#616161",
    "hover": "rgba(0,0,0,0.037)", "press": "rgba(0,0,0,0.024)", "active": "rgba(0,0,0,0.055)",
    "card": "#f9f9f9", "card-line": "rgba(0,0,0,0.06)", "card-shadow": "rgba(0,0,0,0.10)",
    "popover": "#f9f9f9", "popover-line": "rgba(0,0,0,0.10)", "menu-sep": "#eaeaea", "shadow": "rgba(0,0,0,0.18)",
    "ctl": "rgba(255,255,255,0.7)", "ctl-hover": "rgba(249,249,249,0.5)", "ctl-press": "rgba(249,249,249,0.3)",
    "ctl-line": "rgba(0,0,0,0.0578)", "ctl-top": "rgba(0,0,0,0.0578)", "ctl-bottom": "rgba(0,0,0,0.1622)", "input": "rgba(255,255,255,0.7)", "input-bottom": "rgba(0,0,0,0.45)",
    "track": "rgba(0,0,0,0.4458)", "thumb": "#ffffff", "thumb-line": "rgba(0,0,0,0.10)",
    "swatch-line": "rgba(0,0,0,0.30)", "empty-swatch": "#9a9a9a", "smoke": "rgba(0,0,0,0.30)",
    "dialog": "#ffffff", "dialog-foot": "#f3f3f3", "close-hover": "#c42b1c",
    "handle": "#ffffff", "handle-line": "#3c3c3c", "canvas-shadow": "rgba(0,0,0,0.07)",
    "ruler": "#f9f9f9", "ruler-fg": "#6a6a6a", "link": "#003e92",
    "tool-hover": "#f9f9f9", "tool-hover-line": "#eaeaea", "tool-press": "#f9f9f9",
    "radio-fill": "rgba(0,0,0,0.0241)", "radio-line": "rgba(0,0,0,0.4458)", "input-focus": "#ffffff",
    "dialog-line": "rgba(0,0,0,0.27)", "dialog-sep": "rgba(0,0,0,0.0578)",
}
DARK = {
    "bg": "#202020", "bar": "#272727", "bar-line": "#1c1c1c", "sep": "#3a3a3a",
    "fg": "#ffffff", "fg2": "#cfcfcf", "fg3": "#737373", "label": "#cfcfcf",
    "hover": "rgba(255,255,255,0.061)", "press": "rgba(255,255,255,0.042)", "active": "rgba(255,255,255,0.083)",
    "card": "#2c2c2c", "card-line": "rgba(0,0,0,0.25)", "card-shadow": "rgba(0,0,0,0.30)",
    "popover": "#2c2c2c", "popover-line": "rgba(0,0,0,0.45)", "menu-sep": "#3d3d3d", "shadow": "rgba(0,0,0,0.40)",
    "ctl": "rgba(255,255,255,0.0605)", "ctl-hover": "rgba(255,255,255,0.0837)", "ctl-press": "rgba(255,255,255,0.0326)",
    "ctl-line": "rgba(255,255,255,0.07)", "ctl-top": "rgba(255,255,255,0.093)", "ctl-bottom": "rgba(255,255,255,0.0698)", "input": "rgba(255,255,255,0.0605)", "input-bottom": "rgba(255,255,255,0.54)",
    "track": "rgba(255,255,255,0.5442)", "thumb": "#454545", "thumb-line": "rgba(255,255,255,0.09)",
    "swatch-line": "rgba(255,255,255,0.35)", "empty-swatch": "#8a8a8a", "smoke": "rgba(0,0,0,0.40)",
    "dialog": "#2b2b2b", "dialog-foot": "#202020", "close-hover": "#c42b1c",
    "handle": "#2c2c2c", "handle-line": "#d0d0d0", "canvas-shadow": "rgba(0,0,0,0.35)",
    "ruler": "#2c2c2c", "ruler-fg": "#b0b0b0", "link": "#99ebff",
    "tool-hover": "#3a3a3a", "tool-hover-line": "#373737", "tool-press": "#2e2e2e",
    "radio-fill": "rgba(0,0,0,0.1)", "radio-line": "rgba(255,255,255,0.5442)", "input-focus": "#1f1f1f",
    "dialog-line": "rgba(0,0,0,0.33)", "dialog-sep": "rgba(0,0,0,0.1)",
}


def rgba(s) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(s)
    return c


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(h):
    c = [v / 255 for v in _hex(h)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b):
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def custom_variants(base):
    """(light-mode accent, dark-mode accent) for a custom '#rrggbb' (as fenestra-settings)."""
    r, g, b = (v / 255 for v in _hex(base))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    to_hex = lambda l_: "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, max(0, l_), s))
    lt = l - 0.08
    while lt > 0.05 and _contrast(to_hex(lt), "#ffffff") < 4.5:
        lt -= 0.01
    dark = base.lower()
    for _i in range(40):
        if _contrast(dark, "#202020") >= 3:
            break
        dr, dg, db = _hex(dark)
        dark = "#%02x%02x%02x" % tuple(round(v + (255 - v) * 0.1) for v in (dr, dg, db))
    return to_hex(lt), dark


class Theme:
    def __init__(self, override=None):
        self.override = override            # "dark" | "light" | None (command line)
        self.listeners = []
        display = Gdk.Display.get_default()
        self.base = Gtk.CssProvider()
        self.base.connect("parsing-error", self._css_error)
        self.base.load_from_path(os.path.join(util.data_dir(), "style.css"))
        self.vars = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, self.base, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        Gtk.StyleContext.add_provider_for_display(display, self.vars, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
        it = Gtk.IconTheme.get_for_display(display)
        it.add_search_path(os.path.join(util.data_dir(), "icons", "ui"))
        it.add_search_path(os.path.join(util.data_dir(), "icons", "hicolor", "scalable", "apps"))
        it.add_search_path(os.path.join(util.data_dir(), "icons"))
        for key in ("color-scheme", "accent-color"):
            util.gconnect(IFACE, key, self.apply)
        util.gconnect(FENESTRA, "accent-color-custom", self.apply)
        self.apply()

    @staticmethod
    def _css_error(_p, section, error):
        loc = section.get_start_location()
        print(f"style.css:{loc.lines + 1}: {error.message}")

    @property
    def dark(self) -> bool:
        o = self.override or util.opts()["theme"]
        if o in ("dark", "light"):
            return o == "dark"
        return util.gget(IFACE, "color-scheme", "default") == "prefer-dark"

    def accent_hex(self) -> str:
        if not os.environ.get("FENESTRA_PAINT_DEFAULT_ACCENT"):
            c = util.gget(FENESTRA, "accent-color-custom", "") or ""
            if len(c) == 7 and c.startswith("#"):
                lt, dk = custom_variants(c)
                return dk if self.dark else lt
            name = util.gget(IFACE, "accent-color", "blue")
        else:
            name = "blue"
        lt, dk = ACCENTS.get(name, ACCENTS["blue"])
        return dk if self.dark else lt

    def apply(self, *_a):
        dark = self.dark
        pal = dict(DARK if dark else LIGHT)
        acc = self.accent_hex()
        r, g, b = _hex(acc)
        pal["accent"] = acc
        pal["accent-fg"] = "#000000" if _lum(acc) > 0.25 else "#ffffff"
        pal["accent-soft"] = f"rgba({r},{g},{b},0.12)"
        pal["accent-hover"] = f"rgba({r},{g},{b},0.9)"
        self.pal = pal
        self.c = {k: rgba(v) for k, v in pal.items()}
        css = ":root {\n" + "".join(f"  --{k}: {v};\n" for k, v in pal.items()) + "}\n"
        self.vars.load_from_string(css)
        gs = Gtk.Settings.get_default()
        if gs is not None:
            # GTK >= 4.20: gtk-interface-color-scheme (the old property is deprecated, 4.24 warns).
            if hasattr(Gtk, "InterfaceColorScheme") and gs.find_property("gtk-interface-color-scheme"):
                gs.set_property("gtk-interface-color-scheme",
                                Gtk.InterfaceColorScheme.DARK if dark else Gtk.InterfaceColorScheme.LIGHT)
            else:
                gs.set_property("gtk-application-prefer-dark-theme", dark)
            if gs.props.gtk_theme_name != "Default":
                gs.props.gtk_theme_name = "Default"
        for cb in list(self.listeners):
            cb()

    def connect(self, cb):
        self.listeners.append(cb)

    def rgb(self, key):
        c = self.c[key]
        return c.red, c.green, c.blue, c.alpha


_theme: Theme | None = None


def init(override=None):
    global _theme
    _theme = Theme(override)
    return _theme


def get() -> Theme:
    return _theme

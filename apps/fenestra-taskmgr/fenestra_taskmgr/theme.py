"""Light/dark palettes, accent colour and heat-map colours (Windows 11 Task Manager tones)."""
from __future__ import annotations

import colorsys
import os

from gi.repository import Gdk, Gio, Gtk

from . import util

IFACE = "org.gnome.desktop.interface"

ACCENTS = {  # GNOME accent-color -> (light accent, dark accent)
    "blue": ("#0067c0", "#4cc2ff"), "teal": ("#00777a", "#3fd5d9"), "green": ("#107c10", "#6ccb5f"),
    "yellow": ("#8a6100", "#ffd04a"), "orange": ("#c24e00", "#ff9e5e"), "red": ("#c42b1c", "#ff99a4"),
    "pink": ("#bf0077", "#ff8ad8"), "purple": ("#744da9", "#c8a8ff"), "slate": ("#4a5a70", "#a9b8cc"),
}

DARK = {
    "bg": "#202020", "panel": "#191919", "panel-edge": "#1d1d1d", "fg": "#ffffff", "fg2": "#cdcdcd",
    "fg3": "#6d6d6d", "line": "#2d2d2d", "toolbar-line": "#2c2c2c", "hover": "rgba(255,255,255,0.061)",
    "press": "rgba(255,255,255,0.042)", "select": "#2d2d2d", "header-sel": "#272727",
    "search": "#2d2d2d", "search-border": "#353535", "search-focus": "#1f1f1f", "item-sel": "#272727",
    "card": "#2b2b2b", "card-line": "#1d1d1d", "ctl": "#373737", "ctl-hover": "#3c3c3c",
    "popover": "#2c2c2c", "popover-border": "rgba(0,0,0,0.35)", "shadow": "rgba(0,0,0,0.30)",
    "close-hover": "#c42b1c", "dialog": "#202020", "dialog-foot": "#2b2b2b", "smoke": "rgba(0,0,0,0.3)",
    "check-border": "rgba(255,255,255,0.55)", "graph-border": "#757575", "mini-bg": "#292929", "grid": "#2c2c2c",
    "link": "#99ebff", "warn": "#fce100", "leaf": "#6ccb5f",
}
LIGHT = {
    "bg": "#f3f3f3", "panel": "#f9f9f9", "panel-edge": "#e5e5e5", "fg": "#1b1b1b", "fg2": "#5d5d5d",
    "fg3": "#a0a0a0", "line": "#e5e5e5", "toolbar-line": "#e5e5e5", "hover": "rgba(0,0,0,0.037)",
    "press": "rgba(0,0,0,0.024)", "select": "#e9e9e9", "header-sel": "#ededed",
    "search": "#ffffff", "search-border": "#e5e5e5", "search-focus": "#ffffff", "item-sel": "#ededed",
    "card": "#ffffff", "card-line": "#e5e5e5", "ctl": "#fbfbfb", "ctl-hover": "#f6f6f6",
    "popover": "#f9f9f9", "popover-border": "rgba(0,0,0,0.12)", "shadow": "rgba(0,0,0,0.14)",
    "close-hover": "#c42b1c", "dialog": "#f3f3f3", "dialog-foot": "#ffffff", "smoke": "rgba(0,0,0,0.3)",
    "check-border": "rgba(0,0,0,0.55)", "graph-border": "#8e8e8e", "mini-bg": "#ffffff", "grid": "#e6e6e6",
    "link": "#003e92", "warn": "#9d5d00", "leaf": "#0f7b0f",
}

# heat-map levels (lowest .. hot); dark tones sampled from Windows 11 Task Manager
HEAT_DARK = ["#11243e", "#08336e", "#0b4a96", "#1460b8", "#1c78d6", "#9a3a12"]
HEAT_LIGHT = ["#fff4c4", "#f9eca8", "#ffe08a", "#ffd27a", "#ffb64a", "#f7a4a4"]

# graph colours: (line, fill) per resource
GRAPH_DARK = {"cpu": ("#39b8e3", "#0f313b"), "mem": ("#5c9efa", "#0f1d34"), "disk": ("#84c718", "#2d3e0f"),
              "net": ("#f5628e", "#430f22"), "gpu": ("#39b8e3", "#0f313b")}
GRAPH_LIGHT = {"cpu": ("#117dbb", "#f1f6fa"), "mem": ("#8b12ae", "#f4f2f4"), "disk": ("#4da60c", "#eff7ea"),
               "net": ("#a74f01", "#fcf3eb"), "gpu": ("#117dbb", "#f1f6fa")}


def rgba(s) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(s)
    return c


def _rehue(hexcol, hue):
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    _, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(hue, l, s)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


class Theme:
    def __init__(self, override=None):
        self.override = override
        self.listeners = []
        self.iface = None
        src = Gio.SettingsSchemaSource.get_default()
        if src and src.lookup(IFACE, True):
            self.iface = Gio.Settings.new(IFACE)
            self.iface.connect("changed::color-scheme", lambda *_: self.apply())
            self.iface.connect("changed::accent-color", lambda *_: self.apply())
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
        self.apply()

    @staticmethod
    def _css_error(_p, section, error):
        loc = section.get_start_location()
        print(f"style.css:{loc.lines + 1}: {error.message}")

    @property
    def dark(self):
        o = self.override or util.opts()["theme"]
        if o in ("dark", "light"):
            return o == "dark"
        if self.iface is None:
            return True
        return self.iface.get_string("color-scheme") == "prefer-dark"

    @property
    def accent_name(self):
        if util.DEMO or self.iface is None:
            return "blue"
        a = self.iface.get_string("accent-color")
        return a if a in ACCENTS else "blue"

    def apply(self):
        dark = self.dark
        pal = dict(DARK if dark else LIGHT)
        acc = ACCENTS[self.accent_name][1 if dark else 0]
        pal["accent"] = acc
        pal["accent-fg"] = "#000000" if dark else "#ffffff"
        self.pal = pal
        self.c = {k: rgba(v) for k, v in pal.items()}
        heat = HEAT_DARK if dark else HEAT_LIGHT
        if self.accent_name != "blue" and dark:
            h = acc.lstrip("#")
            hue = colorsys.rgb_to_hls(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)))[0]
            heat = [_rehue(x, hue) for x in heat[:-1]] + [heat[-1]]
        self.heat = [rgba(x) for x in heat]
        self.heat_line = rgba("rgba(255,255,255,0.09)" if dark else "rgba(0,0,0,0.06)")
        g = GRAPH_DARK if dark else GRAPH_LIGHT
        self.graph = {k: (rgba(a), rgba(b)) for k, (a, b) in g.items()}
        css = ":root {\n" + "".join(f"  --{k}: {v};\n" for k, v in pal.items()) + "}\n"
        self.vars.load_from_string(css)
        gs = Gtk.Settings.get_default()
        if gs is not None:
            try:
                gs.set_property("gtk-interface-color-scheme",
                                Gtk.InterfaceColorScheme.DARK if dark else Gtk.InterfaceColorScheme.LIGHT)
            except (TypeError, AttributeError):
                gs.set_property("gtk-application-prefer-dark-theme", dark)
            if gs.props.gtk_theme_name != "Default":
                gs.props.gtk_theme_name = "Default"
        for cb in list(self.listeners):
            cb()

    def heat_for(self, frac):
        """Heat-map colour index for a 0..1 share of the resource."""
        if frac < 0.01:
            return 0
        if frac < 0.10:
            return 1
        if frac < 0.30:
            return 2
        if frac < 0.55:
            return 3
        if frac < 0.85:
            return 4
        return 5


_theme: Theme | None = None


def init(override=None):
    global _theme
    _theme = Theme(override)
    return _theme


def get() -> Theme:
    return _theme

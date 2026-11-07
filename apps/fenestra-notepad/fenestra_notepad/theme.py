"""Light/dark palettes and accent colour (system colour scheme + Fenestra accent), live.

Produces CSS custom properties consumed by data/style.css plus a small provider for the
editor font and zoom."""
from __future__ import annotations

import colorsys
import os

from gi.repository import Gdk, Gio, Gtk

from . import util

IFACE = "org.gnome.desktop.interface"
FENESTRA = "org.fenestra.desktop"   # accent-color-custom ('#rrggbb' or '')

ACCENTS = {  # GNOME accent-color -> (light-mode accent, dark-mode accent)
    "blue": ("#0067c0", "#4cc2ff"), "teal": ("#00777a", "#3fd5d9"), "green": ("#107c10", "#6ccb5f"),
    "yellow": ("#8a6100", "#ffd04a"), "orange": ("#c24e00", "#ff9e5e"), "red": ("#c42b1c", "#ff99a4"),
    "pink": ("#bf0077", "#ff8ad8"), "purple": ("#744da9", "#c8a8ff"), "slate": ("#4a5a70", "#a9b8cc"),
}

LIGHT = {
    "strip": "#e8e8e8", "layer": "#f8f8f8", "editor": "#f9f9f9", "line": "#eaeaea", "st-sep": "#eaeaea", "dlg-line": "#eaeaea",
    "tab-border": "#dadada", "tab-hover": "rgba(0,0,0,0.037)", "tab-sep": "rgba(0,0,0,0.16)",
    "fg": "#1a1a1a", "text": "#000000", "fg2": "#5e5e5e", "fg3": "#9f9f9f", "glyph2": "#747474",
    "hover": "rgba(0,0,0,0.037)", "press": "rgba(0,0,0,0.024)",
    "popover": "#f9f9f9", "popover-border": "rgba(0,0,0,0.125)", "popover-bottom": "rgba(0,0,0,0.18)",
    "menu-sep": "#eaeaea", "shadow": "rgba(0,0,0,0.14)",
    "card": "#f9f9f9", "card-border": "rgba(0,0,0,0.25)",
    "input": "rgba(255,255,255,0.7)", "input-border": "rgba(0,0,0,0.0578)", "input-bottom": "rgba(0,0,0,0.4458)",
    "input-focus": "#ffffff",
    "btn": "rgba(255,255,255,0.7)", "btn-hover": "rgba(249,249,249,0.5)", "btn-border": "rgba(0,0,0,0.0578)",
    "btn-top": "rgba(0,0,0,0.0578)", "btn-bottom": "rgba(0,0,0,0.1622)", "scard-hover": "#f6f6f6",
    "sbody": "#f4f4f4", "radio-fill": "rgba(0,0,0,0.024)", "radio-border": "rgba(0,0,0,0.4458)",
    "page": "#f3f3f3", "scard": "#fbfbfb", "scard-border": "#e5e5e5", "sub": "#606060",
    "dot": "#8a8a8a", "smoke": "rgba(0,0,0,0.30)", "dialog": "#ffffff", "dialog-foot": "#f3f3f3",
    "close-hover": "#c42b1c", "scroll": "#8a8a8a", "toggle-off": "rgba(0,0,0,0.62)",
    "link": "#003e92", "current-line": "rgba(0,0,0,0.0)", "match": "rgba(255,200,0,0.45)",
}
DARK = {
    "strip": "#202020", "layer": "#2c2c2c", "editor": "#272727", "line": "#272727", "st-sep": "#3d3d3d", "dlg-line": "#1d1d1d",
    "tab-border": "#1c1c1c", "tab-hover": "rgba(255,255,255,0.061)", "tab-sep": "rgba(255,255,255,0.16)",
    "fg": "#ffffff", "text": "#ffffff", "fg2": "#cfcfcf", "fg3": "#787878", "glyph2": "#9a9a9a",
    "hover": "rgba(255,255,255,0.061)", "press": "rgba(255,255,255,0.042)",
    "popover": "#2c2c2c", "popover-border": "rgba(0,0,0,0.36)", "popover-bottom": "rgba(0,0,0,0.45)",
    "menu-sep": "rgba(255,255,255,0.0837)", "shadow": "rgba(0,0,0,0.32)",
    "card": "#282828", "card-border": "#444444",
    "input": "rgba(255,255,255,0.0605)", "input-border": "rgba(255,255,255,0.0698)",
    "input-bottom": "rgba(255,255,255,0.5442)",
    "input-focus": "rgba(30,30,30,0.7)",
    "btn": "rgba(255,255,255,0.0605)", "btn-hover": "rgba(255,255,255,0.0837)", "btn-border": "rgba(255,255,255,0.0698)",
    "btn-top": "rgba(255,255,255,0.0942)", "btn-bottom": "rgba(255,255,255,0.0698)", "scard-hover": "#3c3c3c",
    "sbody": "#272727", "radio-fill": "rgba(0,0,0,0.1)", "radio-border": "rgba(255,255,255,0.51)",
    "page": "#202020", "scard": "#2b2b2b", "scard-border": "#1d1d1d", "sub": "#cfcfcf",
    "dot": "#9a9a9a", "smoke": "rgba(0,0,0,0.30)", "dialog": "#2b2b2b", "dialog-foot": "#202020",
    "close-hover": "#c42b1c", "scroll": "#9f9f9f", "toggle-off": "rgba(255,255,255,0.78)",
    "link": "#99ebff", "current-line": "rgba(255,255,255,0.0)", "match": "rgba(255,200,0,0.35)",
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
    """(light-mode accent, dark-mode accent) for a custom hex; mirrors fenestra-settings."""
    r, g, b = (v / 255 for v in _hex_to_rgb(base))
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    def to_hex(l_):
        return "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, max(0, min(1, l_)), s))
    lt = l - 0.08
    while lt > 0.05 and _contrast(to_hex(lt), "#ffffff") < 4.5:
        lt -= 0.01
    dark = base.lower()
    for _i in range(40):
        if _contrast(dark, "#202020") >= 3:
            break
        dr, dg, db = _hex_to_rgb(dark)
        dark = "#%02x%02x%02x" % tuple(round(v + (255 - v) * 0.1) for v in (dr, dg, db))
    return to_hex(lt), dark


def on_accent(h):
    return "#000000" if _lum(h) > 0.25 else "#ffffff"


def rgba(s) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(s)
    return c


class Theme:
    def __init__(self, override=None):
        self.override = override            # "dark" | "light" | None (command line)
        self.listeners = []
        self._gs = {}
        src = Gio.SettingsSchemaSource.get_default()
        for sid, keys in ((IFACE, ("color-scheme", "accent-color")), (FENESTRA, ("accent-color-custom",))):
            if src is not None and src.lookup(sid, True) is not None:
                s = Gio.Settings.new(sid)
                self._gs[sid] = s
                for k in keys:
                    if s.props.settings_schema.has_key(k):
                        s.connect(f"changed::{k}", lambda *_: self.apply())
        display = Gdk.Display.get_default()
        self.base = Gtk.CssProvider()
        self.base.connect("parsing-error", self._css_error)
        self.base.load_from_path(os.path.join(util.data_dir(), "style.css"))
        self.vars = Gtk.CssProvider()
        self.font = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, self.base, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        Gtk.StyleContext.add_provider_for_display(display, self.vars, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
        Gtk.StyleContext.add_provider_for_display(display, self.font, Gtk.STYLE_PROVIDER_PRIORITY_USER + 3)
        it = Gtk.IconTheme.get_for_display(display)
        it.add_search_path(os.path.join(util.data_dir(), "icons", "ui"))
        it.add_search_path(os.path.join(util.data_dir(), "icons", "hicolor", "scalable", "apps"))
        util.settings().listeners.append(self._on_setting)
        self.apply()

    @staticmethod
    def _css_error(_p, section, error):
        loc = section.get_start_location()
        print(f"style.css:{loc.lines + 1}: {error.message}")

    def _get(self, sid, key, default=""):
        s = self._gs.get(sid)
        if s is None or not s.props.settings_schema.has_key(key):
            return default
        return s.get_value(key).unpack()

    def _on_setting(self, key):
        if key == "theme":
            self.apply()

    @property
    def dark(self) -> bool:
        o = self.override or util.settings()["theme"]
        if o in ("dark", "light"):
            return o == "dark"
        return self._get(IFACE, "color-scheme", "default") == "prefer-dark"

    def accent_pair(self):
        c = "" if util.DEMO else (self._get(FENESTRA, "accent-color-custom", "") or "")
        if len(c) == 7 and c.startswith("#"):
            return custom_variants(c)
        name = "blue" if util.DEMO else self._get(IFACE, "accent-color", "blue")
        return ACCENTS.get(name, ACCENTS["blue"])

    def apply(self):
        dark = self.dark
        pal = dict(DARK if dark else LIGHT)
        light_acc, dark_acc = self.accent_pair()
        acc = dark_acc if dark else light_acc
        r, g, b = _hex_to_rgb(acc)
        pal["accent"] = acc
        pal["accent-fg"] = on_accent(acc)
        pal["accent-hover"] = f"rgba({r},{g},{b},0.9)"
        pal["accent-press"] = f"rgba({r},{g},{b},0.8)"
        pal["selection"] = light_acc
        pal["selection-fg"] = "#ffffff"
        self.pal = pal
        self.c = {k: rgba(v) for k, v in pal.items()}
        css = ":root {\n" + "".join(f"  --{k}: {v};\n" for k, v in pal.items()) + "}\n"
        # literal colours where var() is not resolved reliably
        css += ("switch.fluent:checked { background-color: %s; border-color: %s; }\n" % (acc, acc))
        css += ("checkbutton.fluent radio:checked { background-color: %s; border-color: %s; "
                "background-image: radial-gradient(circle, %s 0%%, %s 5.5px, %s 6px); }\n"
                % (acc, acc, pal["accent-fg"], pal["accent-fg"], acc))
        self.vars.load_from_string(css)
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

    def set_editor_font(self, family, style, size_pt):
        """Editor font for every view; zoom levels are CSS classes z10 .. z500 on the view."""
        fam = family.replace('"', "") if family else util.DEFAULT_FONT
        weight = "bold" if "bold" in style else "normal"
        fstyle = "italic" if "italic" in style else "normal"
        # Line pitch in px, not a factor: Pango scales a factor by the font's own height, so
        # 1.04 gave 18 px with DejaVu Sans Mono but 15 px with Consolas. Notepad: 18 px at 11 pt.
        line = LINE_PITCH * 96.0 / 72.0
        css = ("textview.editor { font-family: \"%s\", %s; font-size: %.2fpt; line-height: %.2fpx; "
               "font-weight: %s; font-style: %s; }\n" % (fam, util.FONT_FALLBACKS, size_pt, size_pt * line,
                                                         weight, fstyle))
        for z in ZOOM_LEVELS:
            zpt = max(1.0, size_pt * z / 100.0)
            css += "textview.editor.z%d { font-size: %.2fpt; line-height: %.2fpx; }\n" % (z, zpt, zpt * line)
        self.font.load_from_string(css)


ZOOM_LEVELS = list(range(10, 501, 10))
LINE_PITCH = 18.0 / (11 * 96.0 / 72.0)  # reference: 18 px lines for 11 pt text


_theme: Theme | None = None


def init(override=None) -> Theme:
    global _theme
    _theme = Theme(override)
    return _theme


def get() -> Theme:
    return _theme

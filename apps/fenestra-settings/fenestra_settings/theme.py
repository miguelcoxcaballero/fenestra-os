"""Light/dark + accent handling. Produces CSS custom properties consumed by style.css."""
from __future__ import annotations

import os

from gi.repository import Gdk, Gtk

from . import util

IFACE = "org.gnome.desktop.interface"

# GNOME accent-color -> (light-mode accent, dark-mode accent)
ACCENTS = {
    "blue": ("#0067c0", "#4cc2ff"),
    "teal": ("#00777a", "#3fd5d9"),
    "green": ("#107c10", "#6ccb5f"),
    "yellow": ("#8a6100", "#ffd04a"),
    "orange": ("#c24e00", "#ff9e5e"),
    "red": ("#c42b1c", "#ff99a4"),
    "pink": ("#bf0077", "#ff8ad8"),
    "purple": ("#744da9", "#c8a8ff"),
    "slate": ("#4a5a70", "#a9b8cc"),
}
ACCENT_ORDER = list(ACCENTS)

DARK = {
    "bg": "#202020",
    "bg-grad-a": "#1c2027",
    "bg-grad-b": "#202020",
    "bg-grad-c": "#221f22",
    "card": "rgba(255,255,255,0.051)",
    "card-hover": "rgba(255,255,255,0.083)",
    "card-press": "rgba(255,255,255,0.03)",
    "card-border": "rgba(0,0,0,0.20)",
    "card-edge": "rgba(255,255,255,0.06)",
    "fg": "#ffffff",
    "fg2": "#c5c5c5",
    "fg3": "#7e7e7e",
    "ctl": "rgba(255,255,255,0.061)",
    "ctl-hover": "rgba(255,255,255,0.084)",
    "ctl-press": "rgba(255,255,255,0.033)",
    "ctl-border": "rgba(255,255,255,0.07)",
    "ctl-border-bottom": "rgba(255,255,255,0.05)",
    "input": "rgba(255,255,255,0.061)",
    "input-focus": "#1f1f1f",
    "input-bottom": "rgba(255,255,255,0.54)",
    "subtle-hover": "rgba(255,255,255,0.061)",
    "subtle-press": "rgba(255,255,255,0.042)",
    "subtle-select": "rgba(255,255,255,0.061)",
    "toggle-off": "rgba(255,255,255,0.78)",
    "toggle-off-bg": "rgba(0,0,0,0.10)",
    "divider": "rgba(255,255,255,0.084)",
    "popover": "#2c2c2c",
    "popover-border": "rgba(0,0,0,0.35)",
    "trough": "rgba(255,255,255,0.54)",
    "thumb": "#454545",
    "thumb-border": "rgba(255,255,255,0.09)",
    "shadow": "rgba(0,0,0,0.30)",
    "hero": "rgba(255,255,255,0.03)",
    "danger": "#ff99a4",
    "success": "#6ccb5f",
    "warning": "#fce100",
    "caution-bg": "rgba(252,225,0,0.08)",
    "close-hover": "#c42b1c",
}

LIGHT = {
    "bg": "#f3f3f3",
    "bg-grad-a": "#eef1f7",
    "bg-grad-b": "#f3f3f3",
    "bg-grad-c": "#f6f2f3",
    "card": "rgba(255,255,255,0.70)",
    "card-hover": "rgba(249,249,249,0.50)",
    "card-press": "rgba(249,249,249,0.30)",
    "card-border": "rgba(0,0,0,0.07)",
    "card-edge": "rgba(255,255,255,0.0)",
    "fg": "#1b1b1b",
    "fg2": "#5d5d5d",
    "fg3": "#a0a0a0",
    "ctl": "rgba(255,255,255,0.70)",
    "ctl-hover": "rgba(249,249,249,0.50)",
    "ctl-press": "rgba(249,249,249,0.30)",
    "ctl-border": "rgba(0,0,0,0.073)",
    "ctl-border-bottom": "rgba(0,0,0,0.16)",
    "input": "rgba(255,255,255,0.70)",
    "input-focus": "#ffffff",
    "input-bottom": "rgba(0,0,0,0.45)",
    "subtle-hover": "rgba(0,0,0,0.037)",
    "subtle-press": "rgba(0,0,0,0.024)",
    "subtle-select": "rgba(0,0,0,0.055)",
    "toggle-off": "rgba(0,0,0,0.62)",
    "toggle-off-bg": "rgba(0,0,0,0.024)",
    "divider": "rgba(0,0,0,0.08)",
    "popover": "#f9f9f9",
    "popover-border": "rgba(0,0,0,0.12)",
    "trough": "rgba(0,0,0,0.45)",
    "thumb": "#ffffff",
    "thumb-border": "rgba(0,0,0,0.10)",
    "shadow": "rgba(0,0,0,0.14)",
    "hero": "rgba(255,255,255,0.5)",
    "danger": "#c42b1c",
    "success": "#0f7b0f",
    "warning": "#9d5d00",
    "caution-bg": "rgba(255,244,206,0.7)",
    "close-hover": "#c42b1c",
}


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class ThemeManager:
    def __init__(self, override: str | None = None):
        self.override = override  # "dark" | "light" | None
        self.listeners = []
        self.provider = Gtk.CssProvider()
        self.base = Gtk.CssProvider()
        display = Gdk.Display.get_default()
        css_path = os.path.join(util.data_dir(), "style.css")
        self.base.connect("parsing-error", self._on_css_error)
        self.base.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            display, self.base, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        Gtk.StyleContext.add_provider_for_display(
            display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
        theme = Gtk.IconTheme.get_for_display(display)
        theme.add_search_path(os.path.join(util.data_dir(), "icons", "fluent"))
        theme.add_search_path(os.path.join(util.data_dir(), "icons"))
        util.gconnect(IFACE, "color-scheme", self.apply)
        util.gconnect(IFACE, "accent-color", self.apply)
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

    @property
    def accent_name(self) -> str:
        if util.DEMO:
            return "blue"
        a = util.gget(IFACE, "accent-color", "blue")
        return a if a in ACCENTS else "blue"

    def accent_hex(self, name=None, dark=None) -> str:
        light_hex, dark_hex = ACCENTS.get(name or self.accent_name, ACCENTS["blue"])
        d = self.dark if dark is None else dark
        return dark_hex if d else light_hex

    def apply(self, *_):
        dark = self.dark
        pal = dict(DARK if dark else LIGHT)
        acc = self.accent_hex()
        r, g, b = _hex_to_rgb(acc)
        pal["accent"] = acc
        pal["accent-hover"] = f"rgba({r},{g},{b},0.9)"
        pal["accent-press"] = f"rgba({r},{g},{b},0.8)"
        pal["accent-soft"] = f"rgba({r},{g},{b},0.18)"
        pal["accent-fg"] = "#000000" if dark else "#ffffff"
        pal["accent-text"] = acc
        css = ":root {\n" + "".join(f"  --{k}: {v};\n" for k, v in pal.items()) + "}\n"
        # Gradients do not resolve var() reliably, so emit literal colors.
        css += (
            "window.fenestra-settings { background-image: linear-gradient(120deg, "
            f"{pal['bg-grad-a']} 0%, {pal['bg-grad-b']} 45%, {pal['bg-grad-c']} 100%); }}\n"
            "scale.fluent-slider > trough > slider { background-image: radial-gradient("
            f"circle, {acc} 0%, {acc} 5px, transparent 5.5px); }}\n"
            "checkbutton radio:checked { background-color: " + acc + "; background-image: radial-gradient("
            f"circle, {pal['accent-fg']} 0%, {pal['accent-fg']} 4px, {acc} 4.5px); }}\n"
            "scale.fluent-slider > trough > slider:hover { background-image: radial-gradient("
            f"circle, {acc} 0%, {acc} 6px, transparent 6.5px); }}\n"
        )
        self.provider.load_from_string(css)
        gs = Gtk.Settings.get_default()
        if gs is not None:
            try:
                if gs.find_property("gtk-interface-color-scheme") is not None:
                    gs.set_property("gtk-interface-color-scheme",
                                    Gtk.InterfaceColorScheme.DARK if dark
                                    else Gtk.InterfaceColorScheme.LIGHT)
                else:
                    gs.set_property("gtk-application-prefer-dark-theme", dark)
            except (TypeError, AttributeError):
                pass
            # Avoid Adwaita/libadwaita restyling: plain GTK "Default" theme as base.
            if gs.props.gtk_theme_name not in ("Default",):
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

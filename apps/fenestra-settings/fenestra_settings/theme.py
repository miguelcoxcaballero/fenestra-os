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

# Fenestra custom accent (org.fenestra.desktop, shipped with fenestra-tray), the
# same key the shell, taskbar and GTK themes follow. '' = GNOME accent-color.
FENESTRA = "org.fenestra.desktop"
# Windows 11 "Accent color" grid (Settings > Personalization > Colors).
WINDOWS_ACCENTS = [
    "#FFB900", "#FF8C00", "#F7630C", "#CA5010", "#DA3B01", "#EF6950", "#D13438", "#FF4343",
    "#E74856", "#E81123", "#EA005E", "#C30052", "#E3008C", "#BF0077", "#C239B3", "#9A0089",
    "#0078D4", "#0063B1", "#8E8CD8", "#6B69D6", "#8764B8", "#744DA9", "#B146C2", "#881798",
    "#0099BC", "#2D7D9A", "#00B7C3", "#038387", "#00B294", "#018574", "#00CC6A", "#10893E",
    "#7A7574", "#5D5A58", "#68768A", "#515C6B", "#567C73", "#486860", "#498205", "#107C10",
    "#767676", "#4C4A48", "#69797E", "#4A5459", "#647C64", "#525E54", "#847545", "#7E735F",
]


def _lum(h):
    c = [v / 255 for v in _hex_to_rgb(h)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b):
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def custom_variants(base):
    """(light-mode accent, dark-mode accent) for a custom hex; mirrors fenestra-tray appearance.js."""
    import colorsys
    r, g, b = (v / 255 for v in _hex_to_rgb(base))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    to_hex = lambda l_: "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l_, s))
    lt = l - 0.08
    while lt > 0.05 and _contrast(to_hex(lt), "#ffffff") < 4.5:
        lt -= 0.01
    dark = base.lower()
    while _contrast(dark, "#202020") < 3:
        dr, dg, db = _hex_to_rgb(dark)
        dark = "#%02x%02x%02x" % tuple(round(v + (255 - v) * 0.1) for v in (dr, dg, db))
    return to_hex(lt), dark


# AccentTextFillColorPrimary (links, accent text): the default blue's exact values,
# other accents shifted in lightness from their light/dark-mode accent.
ACCENT_TEXT = {"#4cc2ff": "#99ebff", "#0067c0": "#003e92"}


def accent_text(acc, dark):
    if acc.lower() in ACCENT_TEXT:
        return ACCENT_TEXT[acc.lower()]
    import colorsys
    r, g, b = (v / 255 for v in _hex_to_rgb(acc))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = min(0.9, l + 0.15) if dark else max(0.1, l - 0.12)
    return "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l, s))


def on_accent(h):
    """Windows: black glyphs on light accents, white on dark ones."""
    return "#000000" if _lum(h) > 0.25 else "#ffffff"

DARK = {
    "bg": "#202020",
    "bg-grad-a": "#202020",
    "bg-grad-b": "#202020",
    "bg-grad-c": "#202020",
    "card": "rgba(255,255,255,0.051)",
    "card-hover": "rgba(255,255,255,0.083)",
    "card-press": "rgba(255,255,255,0.03)",
    "card-border": "rgba(0,0,0,0.10)",
    "card-edge": "rgba(0,0,0,0.10)",
    "fg": "#ffffff",
    "fg2": "rgba(255,255,255,0.7725)",
    "fg3": "rgba(255,255,255,0.5451)",
    "ctl": "rgba(255,255,255,0.061)",
    "ctl-hover": "rgba(255,255,255,0.084)",
    "ctl-press": "rgba(255,255,255,0.033)",
    "ctl-border": "rgba(255,255,255,0.07)",
    "ctl-border-bottom": "rgba(255,255,255,0.05)",
    "input": "rgba(255,255,255,0.061)",
    "search": "rgba(255,255,255,0.061)",
    "search-hover": "rgba(255,255,255,0.084)",
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
    "bg-grad-a": "#f3f3f3",
    "bg-grad-b": "#f3f3f3",
    "bg-grad-c": "#f3f3f3",
    "card": "rgba(255,255,255,0.70)",
    "card-hover": "rgba(249,249,249,0.50)",
    "card-press": "rgba(249,249,249,0.30)",
    "card-border": "rgba(0,0,0,0.0578)",
    "card-edge": "rgba(0,0,0,0.0578)",
    "fg": "rgba(0,0,0,0.8941)",
    "fg2": "rgba(0,0,0,0.6196)",
    "fg3": "rgba(0,0,0,0.4471)",
    "ctl": "rgba(255,255,255,0.70)",
    "ctl-hover": "rgba(249,249,249,0.50)",
    "ctl-press": "rgba(249,249,249,0.30)",
    "ctl-border": "rgba(0,0,0,0.073)",
    "ctl-border-bottom": "rgba(0,0,0,0.16)",
    "input": "rgba(255,255,255,0.70)",
    "search": "#ffffff",
    "search-hover": "#fafafa",
    "input-focus": "#ffffff",
    "input-bottom": "rgba(0,0,0,0.45)",
    "subtle-hover": "rgba(0,0,0,0.037)",
    "subtle-press": "rgba(0,0,0,0.024)",
    "subtle-select": "rgba(0,0,0,0.037)",
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

    @property
    def accent_name(self) -> str:
        if util.DEMO:
            return "blue"
        a = util.gget(IFACE, "accent-color", "blue")
        return a if a in ACCENTS else "blue"

    @property
    def accent_custom(self) -> str:
        c = "" if util.DEMO else (util.gget(FENESTRA, "accent-color-custom", "") or "")
        return c.upper() if len(c) == 7 and c.startswith("#") else ""

    def accent_hex(self, name=None, dark=None) -> str:
        name = name or self.accent_custom or self.accent_name
        if name.startswith("#"):
            light_hex, dark_hex = custom_variants(name)
        else:
            light_hex, dark_hex = ACCENTS.get(name, ACCENTS["blue"])
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
        pal["accent-fg"] = on_accent(acc)
        pal["accent-text"] = accent_text(acc, dark)
        # base system accent (glyphs such as the Themes summary icons use it in both modes)
        pal["accent-base"] = "#0078d4" if acc.lower() in ACCENT_TEXT else self.accent_hex(dark=False)
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

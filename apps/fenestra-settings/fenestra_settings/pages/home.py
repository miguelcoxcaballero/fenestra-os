"""Home page (device hero + recommendation cards), laid out like the reference Home:
left column  - Recommended settings, Accessibility preferences (text size tiles);
right column - Personalize your device (theme tiles, color mode), Your device info."""
from __future__ import annotations

from gi.repository import Gtk, Pango

from .. import theme, util
from ..backends import appearance, system_info
from ..i18n import C_, _
from ..widgets import Dropdown, SettingRow, icon, label
from .base import Page, register
from .common import MiniWindow, Thumb, device_hero

# text-scaling-factor for the four text size tiles
TEXT_SIZES = [(1.0, "Default"), (1.15, "Medium"), (1.3, "Large"), (1.5, "Extra large")]


@register
class HomePage(Page):
    id = "home"
    title = "Home"
    keywords = "start overview recommended"

    def build(self, box):
        box.append(device_hero(self))
        cols = Gtk.Box(spacing=8, homogeneous=True)
        cols.add_css_class("home-grid")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cols.append(left)
        cols.append(right)
        box.append(cols)
        left.append(self._recommended())
        left.append(self._accessibility())
        right.append(self._personalize())
        right.append(self._device_info())

    # ------------------------------------------------------------- helpers
    def _card(self, title, text=None):
        c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        c.add_css_class("home-card")
        c.set_valign(Gtk.Align.START)
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        head.add_css_class("home-card-head")
        head.append(label(title, "home-card-title", wrap=True))
        if text:
            head.append(label(text, "home-card-text", wrap=True))
        c.append(head)
        return c

    @staticmethod
    def _section(child, css="home-card-section"):
        child.add_css_class(css)
        return child

    # ------------------------------------------------------------- cards
    def _recommended(self):
        c = self._card(_("Recommended settings"), _("Recent and commonly used settings"))
        items = [
            ("taskbar", _("Taskbar"), "fs-panel-bottom-symbolic"),
            ("installed", _("Installed apps"), "fs-apps-list-symbolic"),
            ("contrast" if theme.get().dark else "lockscreen",
             _("Contrast themes") if theme.get().dark else _("Lock screen"),
             "fs-dark-theme-symbolic" if theme.get().dark else "fs-lock-closed-symbolic"),
        ]
        for pid, t, ic in items:
            r = SettingRow(t, None, ic, chevron=True, on_click=lambda p=pid: self.go(p))
            c.append(self._section(r, "home-card-row"))
        return c

    def _accessibility(self):
        c = self._card(_("Accessibility preferences"), _("Optimize your settings for a better experience"))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        body.append(label(C_("home", "Text size"), "home-card-label"))
        flow = Gtk.Grid()
        flow.add_css_class("text-size-tiles")
        flow.set_column_homogeneous(True)
        flow.set_row_spacing(4)
        flow.set_halign(Gtk.Align.START)
        try:
            cur = float(appearance.text_scale())
        except Exception:  # noqa: BLE001 - no backend in this session
            cur = 1.0
        self.size_tiles = []
        for i, (factor, name) in enumerate(TEXT_SIZES):
            b = Gtk.Button()
            b.add_css_class("text-size-tile")
            b.set_halign(Gtk.Align.CENTER)
            if abs(cur - factor) < 0.01:
                b.add_css_class("selected")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, valign=Gtk.Align.CENTER)
            glyph = Gtk.Label()
            big = (14, 17, 20, 26)[i]
            glyph.set_markup(f'<span size="{int(big * 0.62 * Pango.SCALE)}">A</span>'
                             f'<span size="{big * Pango.SCALE}">A</span>')
            glyph.add_css_class("text-size-glyph")
            inner.append(glyph)
            inner.append(label(C_("home", name), "text-size-name", xalign=0.5))
            b.set_child(inner)
            b.connect("clicked", lambda _b, f=factor: self._set_text_size(f))
            cell = Gtk.Box()
            cell.set_size_request(122, -1)
            cell.append(b)
            b.set_hexpand(True)
            b.set_halign(Gtk.Align.CENTER)
            flow.attach(cell, i % 3, i // 3, 1, 1)
            self.size_tiles.append((b, factor))
        body.append(flow)
        c.append(self._section(body, "home-card-body"))
        return c

    def _set_text_size(self, factor):
        if util.READ_ONLY:
            return
        if appearance.set_text_scale(factor):
            for b, f in self.size_tiles:
                (b.add_css_class if abs(f - factor) < 0.01 else b.remove_css_class)("selected")

    def _personalize(self):
        c = self._card(_("Personalize your device"))
        from .personalization import find_backgrounds
        grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        grid.add_css_class("home-theme-grid")
        rows = [Gtk.Box(spacing=8, halign=Gtk.Align.START) for _r in range(2)]
        for r in rows:
            grid.append(r)
        paths = find_backgrounds(6) or [system_info.wallpaper_path(theme.get().dark)]
        acc = theme.get().accent_hex
        for i in range(6):
            path = paths[i % len(paths)]
            dark = i % 3 == 1 or i >= 3
            b = Gtk.Button()
            b.add_css_class("home-theme-tile")
            b.set_halign(Gtk.Align.START)
            b.set_valign(Gtk.Align.START)
            ov = Gtk.Overlay()
            ov.set_child(Thumb(path, 112, 90, "thumb-picture"))
            mw = MiniWindow(dark, acc(dark=dark), 41, 40)
            mw.set_halign(Gtk.Align.END)
            mw.set_valign(Gtk.Align.END)
            mw.set_margin_end(5)
            mw.set_margin_bottom(5)
            ov.add_overlay(mw)
            b.set_child(ov)
            b.set_tooltip_text(_("Dark") if dark else _("Light"))
            b.connect("clicked", lambda _b, p=path, d=dark: self._apply_theme(p, d))
            rows[i // 3].append(b)
        c.append(grid)
        dark_now = theme.get().dark
        mode = Dropdown([("light", _("Light")), ("dark", _("Dark"))], "dark" if dark_now else "light",
                        appearance.set_color_scheme)
        mode.set_size_request(130, -1)
        r = SettingRow(_("Color mode"), None, "fs-color-symbolic", control=mode)
        c.append(self._section(r, "home-card-row"))
        r.add_css_class("tall")
        more = SettingRow(_("Browse more backgrounds, colors, and themes"), None, None, chevron=True,
                          on_click=lambda: self.go("personalization"))
        c.append(self._section(more, "home-card-row"))
        more.add_css_class("tall")
        return c

    def _apply_theme(self, path, dark):
        if util.READ_ONLY:
            return
        appearance.set_wallpaper(path)
        appearance.set_color_scheme("dark" if dark else "light")

    def _device_info(self):
        c = self._card(_("Your device info"), _("View your device and operating system specifications"))
        info = system_info.os_info()
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(12)
        grid.set_row_spacing(16)
        cells = [(_("Processor"), system_info.cpu()), (_("Installed RAM"), system_info.ram_usable_str()),
                 (_("Edition"), info.get("edition", "")), (_("OS version"), info.get("version", ""))]
        for i, (k, v) in enumerate(cells):
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            cell.append(label(k, "home-info-key", wrap=True))
            cell.append(label(v, "home-info-value", wrap=True))
            grid.attach(cell, i % 2, i // 2, 1, 1)
        c.append(self._section(grid, "home-card-info"))
        return c

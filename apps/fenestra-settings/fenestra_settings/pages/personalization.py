"""Personalization: background, colors, themes, lock screen, start, taskbar, fonts."""
from __future__ import annotations

import os

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from .. import theme, util
from ..backends import appearance, session, shell_options
from ..backends.shell_options import gnome as dtp
from ..i18n import C_, N_, _
from ..widgets import (Dropdown, ExpanderRow, SettingRow, Slider, ToggleSwitch, button, icon, label,
                       not_available_row, toast)
from .base import Page, register
from .common import Thumb, gsetting_dropdown, gsetting_toggle, theme_preview, theme_tiles, wallpaper_thumb

BG = "org.gnome.desktop.background"
SS = "org.gnome.desktop.screensaver"
IFACE = "org.gnome.desktop.interface"
PRIVACY = "org.gnome.desktop.privacy"
NOTIF = "org.gnome.desktop.notifications"

ACCENT_LABELS = {"blue": N_("Blue"), "teal": N_("Teal"), "green": N_("Green"), "yellow": N_("Yellow"),
                 "orange": N_("Orange"), "red": N_("Red"), "pink": N_("Pink"), "purple": N_("Purple"),
                 "slate": N_("Slate")}

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".svg", ".jxl", ".avif", ".heic", ".bmp")


def _loadable_exts():
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    exts = set()
    for f in GdkPixbuf.Pixbuf.get_formats():
        for e in f.get_extensions():
            exts.add("." + e.lower())
    return exts


def find_backgrounds(limit=40):
    roots = ([] if util.DEMO else [os.path.expanduser("~/.local/share/backgrounds")]) + ["/usr/share/backgrounds",
             "/usr/local/share/backgrounds"]
    ok_ext = _loadable_exts()
    out = []
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for f in sorted(files):
                ext = os.path.splitext(f)[1].lower()
                if ext in IMG_EXT and ext in ok_ext:
                    out.append(os.path.join(dirpath, f))
                    if len(out) >= limit:
                        return out
    return out


def set_wallpaper(path):
    return appearance.set_wallpaper(path)


def preview_card(width=319, height=172):
    """Desktop preview like the reference: 8 px black bezel around the wallpaper and a
    96x96 mini window (four text lines and an accent button) near the bottom right."""
    frame = Gtk.Box()
    frame.add_css_class("preview-frame")
    frame.set_halign(Gtk.Align.START)
    frame.set_valign(Gtk.Align.START)
    ov = Gtk.Overlay()
    ov.add_css_class("preview-card")
    ov.set_child(wallpaper_thumb(width, height, "preview-thumb"))
    win = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    win.add_css_class("preview-window")
    win.add_css_class("dark" if theme.get().dark else "light")
    win.set_size_request(96, 96)
    win.set_halign(Gtk.Align.END)
    win.set_valign(Gtk.Align.END)
    win.set_margin_end(9)
    win.set_margin_bottom(22)
    for i, w in enumerate((72, 72, 72, 42)):
        ln = Gtk.Box()
        ln.add_css_class("preview-line")
        ln.set_size_request(w, 1)
        ln.set_halign(Gtk.Align.START)
        ln.set_margin_start(12)
        ln.set_margin_top(12 if i == 0 else 8)
        win.append(ln)
    btn = Gtk.Box()
    btn.add_css_class("preview-button")
    btn.set_size_request(24, 8)
    btn.set_halign(Gtk.Align.START)
    btn.set_margin_start(60)
    btn.set_margin_top(34)
    win.append(btn)
    ov.add_overlay(win)
    frame.append(ov)
    return frame


@register
class PersonalizationPage(Page):
    id = "personalization"
    title = "Personalization"
    keywords = "customize look appearance wallpaper theme color"
    ROWS = [
        ("background", N_("Background"), N_("Background image, color, slideshow"), "fs-image-symbolic"),
        ("colors", N_("Colors"), N_("Accent color, transparency effects, color theme"), "fs-color-symbolic"),
        ("themes", N_("Themes"), N_("Install, create, manage"), "fs-paint-brush-symbolic"),
        ("lockscreen", N_("Lock screen"), N_("Lock screen images, apps, animations"), "fs-lock-closed-symbolic"),
        ("start", N_("Start"), N_("Recent apps and items, folders"), "fs-grid-symbolic"),
        ("taskbar", N_("Taskbar"), N_("Taskbar behaviors, system pins"), "fs-panel-bottom-symbolic"),
        ("fonts", N_("Fonts"), N_("Install, manage"), "fs-text-font-symbolic"),
    ]

    def build(self, box):
        top = Gtk.Box(spacing=46)
        top.add_css_class("personalization-hero")
        pv = preview_card()
        pv.set_valign(Gtk.Align.CENTER)
        top.append(pv)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True)
        right.append(label(_("Select a theme to apply"), ["body-strong", "theme-tiles-label"]))
        right.append(theme_tiles())
        top.append(right)
        box.append(top)
        g = self.group()
        for pid, t, s, ic in self.ROWS:
            self.nav_row(g, pid, _(t), _(s), ic)


@register
class BackgroundPage(Page):
    id = "background"
    parent = "personalization"
    title = "Background"
    keywords = "wallpaper desktop picture image photo"
    index = [
        ("bg-type", "Personalize your background", "picture solid color"),
        ("recent", "Recent images", "wallpaper gallery"),
        ("browse", "Choose a photo", "browse photos file"),
        ("fit", "Choose a fit for your desktop image", "fill fit stretch tile center span"),
    ]

    FITS = [("zoom", N_("Fill")), ("scaled", N_("Fit")), ("stretched", N_("Stretch")),
            ("wallpaper", N_("Tile")), ("centered", N_("Center")), ("spanned", N_("Span"))]

    def build(self, box):
        self.preview_holder = Gtk.Box()
        self.preview_holder.add_css_class("preview-hero")
        self.preview_holder.append(preview_card())
        box.append(self.preview_holder)
        g = self.group()
        mode = appearance.background_mode()
        modes = [("picture", _("Picture")), ("solid", _("Solid color"))]
        if session.supports("wallpaper-spotlight"):
            modes.append(("spotlight", _("Spotlight")))
        dd = Dropdown(modes, mode, lambda v: self._mode(v))
        r = SettingRow(_("Personalize your background"),
                       _("A picture background applies to your current desktop"), "fs-image-symbolic",
                       control=dd, key="bg-type")
        self.remember("bg-type", r)
        exp = ExpanderRow(_("Recent images"), None, "fs-image-symbolic", key="recent", expanded=True)
        self.remember("recent", exp)
        g.add(r)
        g.add(exp)
        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        grid.add_css_class("plain")
        current = _current_path()
        self.thumbs = []
        for i, path in enumerate(find_backgrounds(15)):
            b = Gtk.Button()
            b.add_css_class("wallpaper-thumb")
            if path == current:
                b.add_css_class("selected")
            b.set_child(Thumb(path, 104, 66, "thumb-picture"))
            b.set_tooltip_text(os.path.basename(path))
            b.connect("clicked", lambda _b, p=path: self._apply(p))
            grid.attach(b, i % 5, i // 5, 1, 1)
            self.thumbs.append((b, path))
        exp.add(grid)
        browse = SettingRow(_("Choose a photo"), None, "fs-folder-symbolic",
                            control=button(_("Browse photos"), self._browse), key="browse")
        self.remember("browse", browse)
        g.add(browse)
        fit = gsetting_dropdown(BG, "picture-options", [(k, _(v)) for k, v in self.FITS] + [("none", _("None"))])
        if fit:
            fr = SettingRow(_("Choose a fit for your desktop image"), None, "fs-zoom-fit-symbolic", control=fit,
                            key="fit")
            self.remember("fit", fr)
            g.add(fr)

    def _mode(self, v):
        if not appearance.set_background_mode(v) and util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
        GLib.timeout_add(150, self._refresh_preview)

    def _apply(self, path):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        appearance.set_wallpaper(path)
        for b, p in self.thumbs:
            (b.add_css_class if p == path else b.remove_css_class)("selected")
        GLib.timeout_add(150, self._refresh_preview)

    def _refresh_preview(self):
        from ..widgets import clear
        from . import common
        common._thumb_cache.clear()
        clear(self.preview_holder)
        self.preview_holder.append(preview_card())
        return False

    def _browse(self):
        dlg = Gtk.FileDialog()
        dlg.set_title(_("Choose a photo"))
        flt = Gtk.FileFilter()
        flt.set_name(_("Images"))
        flt.add_pixbuf_formats()
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        dlg.set_filters(store)
        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        if pictures:
            dlg.set_initial_folder(Gio.File.new_for_path(pictures))

        def done(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                self._apply(f.get_path())
        dlg.open(self.box.get_root(), None, done)


def _current_path():
    if util.DEMO:
        from ..backends import demo
        return demo.wallpaper(theme.get().dark)
    return appearance.wallpaper(theme.get().dark)


@register
class ColorsPage(Page):
    id = "colors"
    parent = "personalization"
    title = "Colors"
    keywords = "dark mode light mode accent color theme"
    index = [
        ("mode", "Choose your mode", "dark light"),
        ("accent", "Accent color", "highlight color"),
        ("transparency", "Transparency effects", "blur translucent"),
    ]

    def build(self, box):
        top = Gtk.Box()
        top.add_css_class("preview-hero")
        top.append(preview_card())
        box.append(top)
        g = self.group()
        dd = Dropdown([("light", _("Light")), ("dark", _("Dark"))], appearance.color_scheme(),
                      appearance.set_color_scheme)
        r = SettingRow(_("Choose your mode"), _("Change the colors that appear in Fenestra and your apps"),
                       "fs-dark-theme-symbolic", control=dd, key="mode")
        self.remember("mode", r)
        g.add(r)
        if not appearance.has("accent-color"):
            g.add(not_available_row(_("Accent color")))
            return
        exp = ExpanderRow(_("Accent color"), None, "fs-color-symbolic", key="accent", expanded=True)
        self.remember("accent", exp)
        g.add(exp)
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wrap.add_css_class("plain")
        wrap.append(label(_("Fenestra colors"), "body-strong"))
        grid = Gtk.FlowBox()
        grid.add_css_class("accent-grid")
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        # Reference: 50 x 50 swatches, 3 px apart, nine per row.
        grid.set_max_children_per_line(9)
        grid.set_min_children_per_line(9)
        grid.set_column_spacing(3)
        grid.set_row_spacing(3)
        grid.set_halign(Gtk.Align.START)
        self.swatches = []
        tm = theme.get()
        current = tm.accent_custom or tm.accent_hex(tm.accent_name, dark=False).upper()
        if not tm.accent_custom and tm.accent_name == "blue":
            current = "#0078D4"  # Windows' default accent, whose light-mode shade is #0067C0
        for hexc in theme.WINDOWS_ACCENTS:
            b = Gtk.Button()
            b.add_css_class("color-swatch-btn")
            sw = Gtk.Box()
            sw.add_css_class("color-swatch")
            prov = Gtk.CssProvider()
            prov.load_from_string(f"box {{ background-color: {hexc}; }}")
            sw.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
            # Selected swatch: 2 px ring and a check badge in the top-right corner.
            badge = Gtk.Box()
            badge.add_css_class("color-swatch-badge")
            badge.set_halign(Gtk.Align.END)
            badge.set_valign(Gtk.Align.START)
            badge.set_hexpand(True)
            mark = Gtk.Image.new_from_icon_name("fs-checkmark-symbolic")
            mark.set_pixel_size(12)
            mark.set_hexpand(True)
            mark.set_vexpand(True)
            badge.append(mark)
            sw.append(badge)
            b.set_child(sw)
            b.set_tooltip_text(hexc)
            if hexc == current:
                b.add_css_class("selected")
            b.connect("clicked", lambda _b, h=hexc: self._pick(h))
            grid.append(b)
            self.swatches.append((b, hexc))
        wrap.append(grid)
        # Custom colors: Windows' "View colors" picker.
        custom = Gtk.ColorDialogButton.new(Gtk.ColorDialog(title=_("Pick a custom accent color"), with_alpha=False))
        rgba = Gdk.RGBA()
        rgba.parse(tm.accent_custom or "#0078D4")
        custom.set_rgba(rgba)
        custom.connect("notify::rgba", lambda w, _p: self._pick("#%02X%02X%02X" % tuple(
            round(v * 255) for v in (w.get_rgba().red, w.get_rgba().green, w.get_rgba().blue))))
        wrap.append(SettingRow(_("Custom colors"), None, None, control=custom, key="accent-custom"))
        exp.add(wrap)
        g2 = self.group(_("Related settings"))
        g2.add(SettingRow(_("Contrast themes"), _("Color themes for low vision, light sensitivity"),
                          "fs-dark-theme-symbolic", chevron=True, on_click=lambda: self.go("contrast")))
        g2.add(SettingRow(_("Themes"), None, "fs-paint-brush-symbolic", chevron=True,
                          on_click=lambda: self.go("themes")))

    def _pick(self, hexc):
        """Exact hex for the shell, the taskbar and GTK, nearest GNOME accent-color for
        libadwaita apps (backends/appearance)."""
        appearance.set_accent(hexc)
        for b, h in self.swatches:
            (b.add_css_class if h == hexc else b.remove_css_class)("selected")


_nearest_gnome_accent = appearance.gnome.nearest_gnome_accent


def _list_themes(sub):
    dirs = [os.path.expanduser("~/.themes"), os.path.expanduser("~/.local/share/themes"),
            "/usr/share/themes"]
    found = set()
    for d in dirs:
        if os.path.isdir(d):
            for t in os.listdir(d):
                if any(os.path.isdir(os.path.join(d, t, s)) for s in sub):
                    found.add(t)
    return sorted(found, key=str.lower)


def _list_icon_themes(cursor=False):
    dirs = [os.path.expanduser("~/.icons"), os.path.expanduser("~/.local/share/icons"), "/usr/share/icons"]
    found = set()
    for d in dirs:
        if os.path.isdir(d):
            for t in os.listdir(d):
                p = os.path.join(d, t)
                if cursor and os.path.isdir(os.path.join(p, "cursors")):
                    found.add(t)
                elif not cursor and os.path.isfile(os.path.join(p, "index.theme")) and t not in (
                        "default", "hicolor", "locolor") and len(os.listdir(p)) > 2:
                    found.add(t)
    return sorted(found, key=str.lower)


THEME_KEYS = {"gtk-theme": (appearance.gtk_theme, appearance.set_gtk_theme),
              "icon-theme": (appearance.icon_theme, appearance.set_icon_theme),
              "cursor-theme": (appearance.cursor_theme, appearance.set_cursor_theme)}


@register
class ThemesPage(Page):
    def _summary(self):
        """What the current theme is made of (reference: the panel beside the preview)."""
        grid = Gtk.Grid()
        grid.add_css_class("theme-summary")
        grid.set_valign(Gtk.Align.START)
        mode = appearance.background_mode()
        acc = theme.get().accent_custom or theme.get().accent_name
        color = _(ACCENT_LABELS[acc]) if acc in ACCENT_LABELS else _("Custom")
        icons = demo_cursor = None
        if util.DEMO:
            from ..backends import demo
            icons, demo_cursor = demo.THEMES["icon-theme"][0], demo.THEMES["cursor-theme"][0]
        items = [("fs-image-symbolic", C_("themes", "Background"),
                  _("Solid color") if mode == "solid" else _("Picture"),
                  "background"),
                 ("fs-color-symbolic", _("Color"), color, "colors"),
                 ("fs-apps-symbolic", _("Icons"), icons or appearance.icon_theme() or "", None),
                 ("fs-cursor-symbolic", _("Mouse cursor"), demo_cursor or appearance.cursor_theme() or "", None)]
        for i, (ic, title, value, target) in enumerate(items):
            b = Gtk.Button()
            b.add_css_class("theme-summary-item")
            bx = Gtk.Box(spacing=12)
            im = icon(ic, 24, "theme-summary-icon")
            im.set_valign(Gtk.Align.START)
            bx.append(im)
            tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            tb.append(label(title, "theme-summary-title", ellipsize=True))
            v = label(value, "theme-summary-value", ellipsize=True)
            v.set_max_width_chars(18)
            tb.append(v)
            bx.append(tb)
            b.set_child(bx)
            b.set_size_request(207, -1)
            if target:
                b.connect("clicked", lambda _b, t=target: self.go(t))
            else:
                b.set_can_target(False)
            grid.attach(b, i % 2, i // 2, 1, 1)
        return grid

    id = "themes"
    parent = "personalization"
    title = "Themes"
    keywords = "gtk theme icons cursor"
    index = [("icons", "Icons", "icon theme"), ("iconpack", "Icon pack", "import icons zip windows"),
             ("cursor", "Mouse cursor", "pointer theme"),
             ("gtk", "App style", "gtk theme legacy apps")]

    def build(self, box):
        top = Gtk.Box(spacing=32)
        top.add_css_class("preview-hero")
        top.append(preview_card())
        top.append(self._summary())
        box.append(top)
        g = self.group(_("Current theme"))
        for key, sk, title, sub, ic, items in (
                ("gtk", "gtk-theme", _("App style"), _("Theme used by GTK 3 apps"), "fs-window-brush-symbolic",
                 _list_themes(["gtk-3.0", "gtk-4.0"])),
                ("icons", "icon-theme", _("Icons"), None, "fs-apps-symbolic", _list_icon_themes()),
                ("cursor", "cursor-theme", _("Mouse cursor"), None, "fs-cursor-symbolic",
                 _list_icon_themes(cursor=True))):
            getter, setter = THEME_KEYS[sk]
            cur = getter()
            if cur is None:
                continue
            if util.DEMO:
                from ..backends import demo
                items = demo.THEMES[sk]
                cur = items[0]
            opts = [(t, t) for t in items]
            if cur not in items:
                opts.insert(0, (cur, cur))
            dd = Dropdown(opts, cur, setter, width=220)
            r = SettingRow(title, sub, ic, control=dd, key=key)
            self.remember(key, r)
            g.add(r)
        # Icon packs (own Windows icons, Fenestra Icon Extractor zips, icon theme
        # zips): handled by the same step as the first-login setup.
        self.ext_row(g, _("Icon pack"), _("Import your own icons or an icon pack (.zip)"),
                     "fs-apps-symbolic", ["/usr/libexec/fenestra-oobe", "--icons"], key="iconpack")
        g2 = self.group(_("Related settings"))
        if util.have("gnome-tweaks"):
            self.ext_row(g2, _("More appearance options"), _("Tweaks"), "fs-options-symbolic", ["gnome-tweaks"])
        g2.add(SettingRow(_("Colors"), None, "fs-color-symbolic", chevron=True, on_click=lambda: self.go("colors")))


@register
class LockScreenPage(Page):
    id = "lockscreen"
    parent = "personalization"
    title = "Lock screen"
    keywords = "lock screen picture notifications timeout"
    index = [("ls-picture", "Personalize your lock screen", "picture image"),
             ("ls-notif", "Lock screen notifications", "status")]

    def build(self, box):
        top = Gtk.Box()
        top.add_css_class("hero")
        uri = util.gget(SS, "picture-uri") or util.gget(BG, "picture-uri")
        path = Gio.File.new_for_uri(uri).get_path() if uri else None
        if util.DEMO:
            from ..backends import demo
            path = demo.wallpaper(theme.get().dark)
        ov = Gtk.Overlay()
        ov.set_child(Thumb(path, 300, 188, "preview-thumb"))
        clock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER)
        clock.set_margin_top(28)
        clock.set_valign(Gtk.Align.START)
        clock.append(label(GLib.DateTime.new_now_local().format("%H:%M"), "lock-clock", xalign=0.5))
        clock.append(label(GLib.DateTime.new_now_local().format("%A, %e %B"), "lock-date", xalign=0.5))
        ov.add_overlay(clock)
        top.append(ov)
        box.append(top)
        g = self.group()
        r = SettingRow(_("Personalize your lock screen"), None, "fs-image-symbolic",
                       control=button(_("Browse photos"), self._browse) if util.has_key(SS, "picture-uri")
                       else label(_("Uses your desktop background"), "row-value"), key="ls-picture")
        self.remember("ls-picture", r)
        g.add(r)
        t = gsetting_toggle(NOTIF, "show-in-lock-screen")
        if t:
            r = SettingRow(_("Lock screen notifications"), _("Show notifications on the lock screen"),
                           "fs-alert-symbolic", control=t, key="ls-notif")
            self.remember("ls-notif", r)
            g.add(r)
        g2 = self.group(_("Related settings"))
        self.nav_row(g2, "power", _("Screen timeout"), None, "fs-timer-symbolic", key="screen-timeout",
                     focus="screen-sleep")
        self.nav_row(g2, "screenlock", _("Screen lock"), _("Lock automatically and require a password"),
                     "fs-lock-shield-symbolic")

    def _browse(self):
        dlg = Gtk.FileDialog()
        flt = Gtk.FileFilter()
        flt.add_pixbuf_formats()
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        dlg.set_filters(store)

        def done(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            if f:
                util.gset(SS, "picture-uri", f.get_uri())
        dlg.open(self.box.get_root(), None, done)


def _extension_installed(uuid):
    for base in (os.path.expanduser("~/.local/share/gnome-shell/extensions"),
                 "/usr/share/gnome-shell/extensions"):
        if os.path.isdir(os.path.join(base, uuid)):
            return True
    return False


ARCMENU = "org.gnome.shell.extensions.arcmenu"
DTP = "org.gnome.shell.extensions.dash-to-panel"

START_LAYOUTS = [("11", N_("Fenestra (centered, recommended)")), ("windows", N_("Classic")),
                 ("redmond", N_("Classic with places")), ("insider", N_("Insider")), ("plasma", N_("Plasma")),
                 ("arcmenu", N_("ArcMenu")), ("gnome-menu", N_("GNOME menu")), ("runner", N_("Runner (search only)"))]


# Start layout picker (reference: three desktop previews with a radio under each).
PICKER_LAYOUTS = [("windows", N_("Classic")), ("11", N_("Default")), ("redmond", N_("Classic with places"))]
_PREVIEW_COLORS = {  # wallpaper, panel/taskbar, emphasised glyphs, dim glyphs, bezel
    True: ((0, 10, 42), (0, 37, 88), (96, 204, 254), (98, 113, 140), (9, 9, 9)),
    False: ((145, 209, 239), (223, 245, 255), (0, 94, 183), (140, 160, 175), (31, 31, 31)),
}


def _start_preview(layout, dark):
    """257x167 drawing of a monitor with the Start menu of `layout`, own artwork."""
    area = Gtk.DrawingArea()
    area.set_content_width(257)
    area.set_content_height(167)
    wall, panel, acc, dim, bezel = (tuple(c / 255 for c in col) for col in _PREVIEW_COLORS[dark])

    def rrect(cr, x, y, w, h, r):
        import math
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def draw(_a, cr, w, h):
        cr.set_source_rgb(*bezel)
        rrect(cr, 0, 0, 257, 167, 8)
        cr.fill()
        cr.set_source_rgb(*wall)
        cr.rectangle(8, 9, 241, 141)
        cr.fill()
        cr.set_source_rgb(*panel)
        cr.rectangle(8, 150, 241, 8)  # taskbar
        cr.fill()

        def glyph(x, y, c, line=0):
            cr.set_source_rgb(*c)
            rrect(cr, x, y, 8, 8, 1.5)
            cr.fill()
            if line:
                cr.rectangle(x + 12, y + 2, line, 1)
                cr.rectangle(x + 12, y + 5, line * 0.6, 1)
                cr.fill()

        if layout == "11":  # centred: pinned grid, then recommended list
            cr.set_source_rgb(*panel)
            rrect(cr, 68, 18, 122, 126, 4)
            cr.fill()
            for r in range(3):
                for c in range(6):
                    glyph(78 + 18 * c, 30 + 21 * r, dim)
            for r in range(3):
                for c in range(2):
                    glyph(78 + 46 * c, 94 + 15 * r, dim, 22)
        else:  # classic: left-aligned menu with an app list (+ places column)
            cr.set_source_rgb(*panel)
            rrect(cr, 8, 18, 132 if layout == "redmond" else 110, 132, 4)
            cr.fill()
            for r in range(7):
                glyph(18, 28 + 16 * r, acc if layout == "windows" else dim, 40)
            if layout == "redmond":
                for r in range(6):
                    glyph(84, 28 + 16 * r, acc, 30)

    area.set_draw_func(draw)
    return area


class StartLayoutPicker(Gtk.Box):
    """Three previews with radio buttons; writes ArcMenu's menu-layout."""

    def __init__(self, schema, key):
        super().__init__(spacing=37)
        self.add_css_class("start-picker")
        self.schema, self.key = schema, key
        self.radios = {}
        dark = theme.get().dark
        first = None
        for lid, name in PICKER_LAYOUTS:
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            prev = _start_preview(lid, dark)
            prev.add_css_class("start-preview")
            click = Gtk.GestureClick()
            click.connect("released", lambda *_a, l=lid: self._pick(l))
            prev.add_controller(click)
            col.append(prev)
            rb = Gtk.CheckButton(label=_(name))
            rb.add_css_class("start-radio")
            if first is None:
                first = rb
            else:
                rb.set_group(first)
            rb.connect("toggled", lambda b, l=lid: b.get_active() and not self._silent and self._pick(l))
            col.append(rb)
            self.radios[lid] = rb
            self.append(col)
        self._silent = False
        self.sync()
        util.gconnect(schema, key, self.sync)

    def sync(self, *_a):
        cur = util.gget(self.schema, self.key)
        self._silent = True
        for lid, rb in self.radios.items():
            rb.set_active(lid == cur)
        self._silent = False

    def _pick(self, lid):
        util.gset(self.schema, self.key, lid)
        self.sync()


@register
class StartPage(Page):
    id = "start"
    parent = "personalization"
    title = "Start"
    keywords = "start menu arcmenu pinned recent apps layout recommended"
    index = [("recent-items", "Show recommended files in Start", "recent documents"),
             ("start-layout", "Layout", "start menu style"),
             ("pinned-reset", "Pinned apps", "reset pins")]

    def build(self, box):
        layout_row = None
        if util.settings(ARCMENU) is not None:
            gp = self.group(_("Layout"))
            gp.add(StartLayoutPicker(ARCMENU, "menu-layout"))
            cur = util.gget(ARCMENU, "menu-layout")
            opts = [(k, _(v)) for k, v in START_LAYOUTS]
            if cur not in [o[0] for o in opts]:
                opts.append((cur, str(cur)))
            # every layout stays reachable: the picker shows three, this row all of them
            layout_row = SettingRow(_("Layout"), _("Choose how the Start menu looks"), "fs-grid-symbolic",
                                    control=gsetting_dropdown(ARCMENU, "menu-layout", opts), key="start-layout")
            self.remember("start-layout", layout_row)
        g = self.group()
        if util.settings(ARCMENU) is not None:
            for key, rkey, title, ic in (
                    ("show-recently-installed-apps", "start-recent-installed", _("Show recently added apps"),
                     "fs-arrow-download-symbolic"),
                    ("eleven-show-frequent-apps", "start-frequent", _("Show most used apps"), "fs-star-symbolic"),
                    ("show-user-avatar", "start-avatar", _("Show my account picture"), "fs-person-symbolic")):
                t = gsetting_toggle(ARCMENU, key)
                if t:
                    g.add(SettingRow(title, None, ic, control=t, key=rkey))
        elif not shell_options.supports("start-pins"):
            g.add(not_available_row(_("Start menu"), _("The Start menu extension is not installed"),
                                    "fs-grid-symbolic"))
        t = gsetting_toggle(PRIVACY, "remember-recent-files")
        if t:
            r = SettingRow(_("Show recommended files in Start and recent files in the file manager"),
                           None, "fs-document-symbolic", control=t, key="recent-items")
            self.remember("recent-items", r)
            g.add(r)
        if shell_options.supports("start-pins"):
            n = shell_options.pinned_count()
            self.pin_row = SettingRow(_("Pinned apps"), _("{0} apps pinned to Start").format(n), "fs-star-symbolic",
                                      control=button(_("Reset"), self._reset_pins), key="pinned-reset")
            self.remember("pinned-reset", self.pin_row)
            g.add(self.pin_row)
        if layout_row is not None:
            g.add(layout_row)
        g2 = self.group(_("Related settings"))
        g2.add(SettingRow(_("Installed apps"), None, "fs-apps-list-symbolic", chevron=True,
                          on_click=lambda: self.go("installed")))

    def _reset_pins(self):
        def go():
            if not shell_options.reset_start_pins():
                toast(self.box, _("This action is disabled in read-only mode"))
                return
            self.pin_row.set_subtitle(_("{0} apps pinned to Start").format(shell_options.pinned_count()))
        from ..widgets import confirm
        confirm(self.box, _("Reset pinned apps?"), _("Start will go back to the default set of pinned apps."),
                _("Reset"), go)


# Dash to Panel helpers moved to backends/shell_options/gnome.py.
_dtp_json, _dtp_set_all, _dtp_first = dtp.dtp_json, dtp.dtp_set_all, dtp.dtp_first
_dtp_elements, _dtp_element, _dtp_update_element = dtp.dtp_elements, dtp.dtp_element, dtp.dtp_update_element


@register
class TaskbarPage(Page):
    id = "taskbar"
    parent = "personalization"
    title = "Taskbar"
    keywords = "panel dock dash to panel clock tray alignment position size transparency autohide"
    index = [("tb-search", "Search", "search box icon label taskbar"),
             ("tb-widgets", "Widgets", "weather widgets news"),
             ("tb-align", "Taskbar alignment", "center left"),
             ("tb-position", "Taskbar position on screen", "bottom top"),
             ("tb-autohide", "Automatically hide the taskbar", "intellihide"),
             ("weekday", "Show the day of the week in the clock", "clock"),
             ("seconds", "Show seconds in system tray clock", "clock seconds")]

    SEARCH = [("hide", N_("Hide")), ("icon", N_("Search icon only")), ("icon-label", N_("Search icon and label")),
              ("box", N_("Search box"))]

    def _ro(self, ok):
        if not ok:
            toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                  else _("The change was not applied"))

    def build(self, box):
        # Expander sections like the reference page: Taskbar items (open), Taskbar
        # behaviors, Clock; then Related settings.
        top = self.group()
        gi_ = ExpanderRow(_("Taskbar items"), _("Show or hide buttons that appear on the taskbar"),
                          None, key="tb-items", expanded=True)
        top.add(gi_)
        shown = False
        if shell_options.supports("search-mode"):
            search = Dropdown([(k, _(v)) for k, v in self.SEARCH], shell_options.search_mode(),
                              lambda v: self._ro(shell_options.set_search_mode(v)))
            r = SettingRow(C_("taskbar", "Search"), None, "fs-search-symbolic", control=search, key="tb-search")
            self.remember("tb-search", r)
            gi_.add(r)
            shown = True
        if shell_options.supports("weather"):
            widgets = ToggleSwitch(shell_options.weather(), lambda v: self._ro(shell_options.set_weather(v)))
            r = SettingRow(_("Widgets"), _("Weather at the left end of the taskbar"), "fs-weather-sunny-symbolic",
                           control=widgets, key="tb-widgets")
            self.remember("tb-widgets", r)
            gi_.add(r)
            shown = True
        if not shown:
            gi_.add(not_available_row(_("Taskbar items")))
        g = ExpanderRow(_("Taskbar behaviors"),
                        _("Taskbar alignment, automatically hide, multiple displays"), None, key="tb-behaviors")
        top.add(g)
        if shell_options.supports("alignment"):
            r = SettingRow(_("Taskbar alignment"), None, "fs-panel-bottom-symbolic",
                           control=Dropdown([("center", _("Center")), ("left", _("Left"))],
                                            shell_options.alignment(),
                                            lambda v: self._ro(shell_options.set_alignment(v))),
                           key="tb-align")
            self.remember("tb-align", r)
            g.add(r)
        else:
            g.add(not_available_row(_("Taskbar behaviors"), _("The taskbar extension is not installed"),
                                    "fs-panel-bottom-symbolic"))
        if util.settings(DTP) is not None:
            pos = _dtp_first("panel-positions", "BOTTOM")
            r = SettingRow(_("Taskbar position on screen"), None, "fs-panel-bottom-symbolic",
                           control=Dropdown([("BOTTOM", _("Bottom")), ("TOP", _("Top")), ("LEFT", _("Left")),
                                             ("RIGHT", _("Right"))], pos,
                                            lambda v: _dtp_set_all("panel-positions", v)), key="tb-position")
            self.remember("tb-position", r)
            g.add(r)
            size = _dtp_first("panel-sizes", 48)
            opts = [(40, _("Small")), (48, _("Medium")), (56, _("Large")), (64, _("Extra large"))]
            if size not in [o[0] for o in opts]:
                opts.append((size, f"{size} px"))
            g.add(SettingRow(_("Taskbar size"), None, "fs-zoom-fit-symbolic",
                             control=Dropdown(opts, size, lambda v: _dtp_set_all("panel-sizes", int(v))),
                             key="tb-size"))
            ah = gsetting_toggle(DTP, "intellihide")
            if ah:
                r = SettingRow(_("Automatically hide the taskbar"), None, "fs-panel-bottom-symbolic", control=ah,
                               key="tb-autohide")
                self.remember("tb-autohide", r)
                g.add(r)
            grp = gsetting_toggle(DTP, "group-apps")
            if grp:
                g.add(SettingRow(_("Combine taskbar buttons"), None, "fs-apps-symbolic", control=grp,
                                 key="tb-combine"))
            desk = _dtp_element("desktopButton")
            if desk is not None:
                g.add(SettingRow(_("Select the far corner of the taskbar to show the desktop"), None,
                                 "fs-desktop-symbolic",
                                 control=ToggleSwitch(bool(desk.get("visible", True)),
                                                      lambda v: _dtp_update_element("desktopButton", visible=v)),
                                 key="tb-show-desktop"))
            tr = gsetting_toggle(DTP, "trans-use-custom-opacity")
            if tr:
                g.add(SettingRow(_("Taskbar transparency"), None, "fs-circle-half-fill-symbolic", control=tr,
                                 key="tb-transparency"))
                op = util.gget(DTP, "trans-panel-opacity", 0.8)
                g.add(SettingRow(_("Taskbar opacity"), None, "fs-circle-half-fill-symbolic",
                                 control=Slider(0, 100, round(op * 100),
                                                lambda v: util.gset(DTP, "trans-panel-opacity", round(v) / 100.0),
                                                fmt="{:.0f}%", width=200), key="tb-opacity"))
        g2 = ExpanderRow(_("Clock"), _("Day of the week, date, seconds, time format"), None, key="tb-clock")
        top.add(g2)
        for key, sk, t in (("weekday", "clock-show-weekday", _("Show the day of the week in the clock")),
                           ("date", "clock-show-date", _("Show the date in the clock")),
                           ("seconds", "clock-show-seconds", _("Show seconds in system tray clock"))):
            tg = gsetting_toggle(IFACE, sk)
            if tg:
                r = SettingRow(t, None, "fs-clock-symbolic", control=tg, key=key)
                self.remember(key, r)
                g2.add(r)
        fmt = gsetting_dropdown(IFACE, "clock-format", [("24h", _("24-hour")), ("12h", _("12-hour"))])
        if fmt:
            g2.add(SettingRow(_("Time format"), None, "fs-clock-symbolic", control=fmt, key="tb-clock-format"))
        rel = self.group(_("Related settings"))
        rel.add(SettingRow(_("Date & time"), _("Time zones, automatic clock settings, calendar display"),
                           "fs-calendar-symbolic", chevron=True, on_click=lambda: self.go("datetime")))
        rel.add(SettingRow(_("Notifications"), _("Alerts from apps and system, do not disturb"),
                           "fs-alert-symbolic", chevron=True, on_click=lambda: self.go("notifications")))


@register
class FontsPage(Page):
    id = "fonts"
    parent = "personalization"
    title = "Fonts"
    keywords = "typeface text font install antialiasing hinting"
    index = [("font-ui", "Interface text", "system font"),
             ("antialias", "Font smoothing", "antialiasing cleartype")]

    def build(self, box):
        g = self.group(_("Font settings"))
        fonts = appearance.fonts()
        for key, kind, sk, t in (("font-ui", "ui", "font-name", _("Interface text")),
                                 ("font-doc", "document", "document-font-name", _("Document text")),
                                 ("font-mono", "monospace", "monospace-font-name", _("Monospace text"))):
            cur = fonts.get(kind)
            if cur is None:
                continue
            if util.DEMO:
                cur = {"font-name": "Inter 11", "document-font-name": "Inter 11",
                       "monospace-font-name": "Adwaita Mono 11"}[sk]
            fb = Gtk.FontDialogButton.new(Gtk.FontDialog())
            fb.set_font_desc(Pango.FontDescription.from_string(cur))
            fb.add_css_class("fluent-fontbutton")
            fb.set_valign(Gtk.Align.CENTER)
            fb.connect("notify::font-desc",
                       lambda b, _p, kind=kind: appearance.set_font(kind, b.get_font_desc().to_string()))
            r = SettingRow(t, None, "fs-text-font-symbolic", control=fb, key=key)
            self.remember(key, r)
            g.add(r)
        aa = gsetting_dropdown(IFACE, "font-antialiasing", [("grayscale", _("Standard (grayscale)")),
                                                            ("rgba", _("Subpixel (LCD)")),
                                                            ("none", _("None"))])
        if aa:
            r = SettingRow(_("Font smoothing"), None, "fs-text-font-size-symbolic", control=aa, key="antialias")
            self.remember("antialias", r)
            g.add(r)
        hint = gsetting_dropdown(IFACE, "font-hinting", [("none", _("None")), ("slight", _("Slight")),
                                                         ("medium", _("Medium")), ("full", _("Full"))])
        if hint:
            g.add(SettingRow(_("Hinting"), None, "fs-text-font-size-symbolic", control=hint))

        g2 = self.group(_("Available fonts"))
        self.filter = Gtk.Entry()
        self.filter.add_css_class("fluent-entry")
        self.filter.set_placeholder_text(_("Type here to search"))
        self.filter.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "fs-search-symbolic")
        self.filter.set_size_request(300, -1)
        self.filter.set_halign(Gtk.Align.START)
        self.filter.set_margin_bottom(10)
        g2.rows.append(self.filter)
        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_homogeneous(True)
        self.flow.set_min_children_per_line(2)
        self.flow.set_max_children_per_line(5)
        self.flow.set_column_spacing(8)
        self.flow.set_row_spacing(8)
        g2.rows.append(self.flow)
        families = sorted(self.box.get_pango_context().list_families(), key=lambda f: f.get_name().lower())
        if util.DEMO:
            from ..backends import demo
            families = [f for f in families if f.get_name() in demo.FONT_FAMILIES]
        self.families = families
        self.count_lbl = label("", "caption")
        g2.rows.append(self.count_lbl)
        self._fill("")
        self.filter.connect("changed", lambda e: self._fill(e.get_text()))

    def _fill(self, q):
        from ..widgets import clear
        clear(self.flow)
        q = q.lower().strip()
        shown = [f for f in self.families if q in f.get_name().lower()]
        for fam in shown[:40]:
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            tile.add_css_class("font-tile")
            sample = Gtk.Label(label="Aa", xalign=0)
            attrs = Pango.AttrList()
            attrs.insert(Pango.attr_family_new(fam.get_name()))
            attrs.insert(Pango.attr_size_new(36 * Pango.SCALE))
            sample.set_attributes(attrs)
            tile.append(sample)
            tile.append(label(fam.get_name(), "body-strong", ellipsize=True))
            faces = fam.list_faces()
            tile.append(label(_("{0} font faces").format(len(faces)) if len(faces) != 1 else _("1 font face"),
                              "caption"))
            self.flow.append(tile)
        self.count_lbl.set_label(_("{0} fonts available").format(len(shown)) +
                                 (_(" (showing 40)") if len(shown) > 40 else ""))

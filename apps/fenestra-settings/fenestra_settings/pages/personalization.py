"""Personalization: background, colors, themes, lock screen, start, taskbar, fonts."""
from __future__ import annotations

import os

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from .. import theme, util
from ..i18n import N_, _
from ..widgets import (Dropdown, ExpanderRow, SettingRow, Slider, ToggleSwitch, button, label,
                       not_available_row, toast)
from .base import Page, register
from .common import Thumb, gsetting_dropdown, gsetting_toggle, theme_preview, wallpaper_thumb

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
    uri = Gio.File.new_for_path(path).get_uri()
    a = util.gset(BG, "picture-uri", uri)
    b = util.gset(BG, "picture-uri-dark", uri)
    return a and b


def preview_card(width=300, height=188):
    """Large desktop preview with a mini taskbar."""
    ov = Gtk.Overlay()
    ov.add_css_class("preview-card")
    ov.set_halign(Gtk.Align.START)
    ov.set_child(wallpaper_thumb(width, height, "preview-thumb"))
    bar = Gtk.Box()
    bar.add_css_class("mini-taskbar")
    bar.set_valign(Gtk.Align.END)
    bar.set_size_request(width, 14)
    dots = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
    for i in range(4):
        d = Gtk.Box()
        d.add_css_class("mini-taskbar-icon")
        if i == 0:
            d.add_css_class("accent")
        d.set_size_request(8, 8)
        dots.append(d)
    bar.append(dots)
    ov.add_overlay(bar)
    win = Gtk.Box()
    win.add_css_class("mini-window")
    win.add_css_class("dark" if theme.get().dark else "light")
    win.set_size_request(width // 3, height // 3)
    win.set_halign(Gtk.Align.CENTER)
    win.set_valign(Gtk.Align.CENTER)
    ov.add_overlay(win)
    return ov


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
        top = Gtk.Box(spacing=24)
        top.add_css_class("hero")
        top.append(preview_card(300, 188))
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        right.append(label(_("Select a theme to apply"), "body-strong"))
        flow = Gtk.Box(spacing=8)
        dark_now = theme.get().dark
        for dark in (False, True):
            b = Gtk.Button()
            b.add_css_class("theme-thumb")
            if dark == dark_now:
                b.add_css_class("selected")
            b.set_child(theme_preview(dark, 128, 80))
            b.connect("clicked", lambda _b, d=dark: util.gset(IFACE, "color-scheme",
                                                              "prefer-dark" if d else "default"))
            b.set_tooltip_text(_("Dark") if dark else _("Light"))
            flow.append(b)
        right.append(flow)
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
        self.preview_holder.add_css_class("hero")
        self.preview_holder.append(preview_card(300, 188))
        box.append(self.preview_holder)
        g = self.group()
        mode = "none" if util.gget(BG, "picture-options") == "none" else "picture"
        dd = Dropdown([("picture", _("Picture")), ("none", _("Solid color"))], mode,
                      lambda v: util.gset(BG, "picture-options", "none" if v == "none" else "zoom"))
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

    def _apply(self, path):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        set_wallpaper(path)
        for b, p in self.thumbs:
            (b.add_css_class if p == path else b.remove_css_class)("selected")
        GLib.timeout_add(150, self._refresh_preview)

    def _refresh_preview(self):
        from ..widgets import clear
        from . import common
        common._thumb_cache.clear()
        clear(self.preview_holder)
        self.preview_holder.append(preview_card(300, 188))
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
    uri = util.gget(BG, "picture-uri-dark" if theme.get().dark else "picture-uri") or ""
    return Gio.File.new_for_uri(uri).get_path() if uri else None


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
        g = self.group()
        cur = util.gget(IFACE, "color-scheme", "default")
        dd = Dropdown([("default", _("Light")), ("prefer-dark", _("Dark"))],
                      "prefer-dark" if cur == "prefer-dark" else "default",
                      lambda v: util.gset(IFACE, "color-scheme", v))
        r = SettingRow(_("Choose your mode"), _("Change the colors that appear in Fenestra and your apps"),
                       "fs-dark-theme-symbolic", control=dd, key="mode")
        self.remember("mode", r)
        g.add(r)
        if not util.has_key(IFACE, "accent-color"):
            g.add(not_available_row(_("Accent color")))
            return
        exp = ExpanderRow(_("Accent color"), None, "fs-color-symbolic", key="accent", expanded=True)
        self.remember("accent", exp)
        g.add(exp)
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wrap.add_css_class("plain")
        wrap.append(label(_("Fenestra colors"), "body-strong"))
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_max_children_per_line(8)
        grid.set_min_children_per_line(8)
        grid.set_column_spacing(4)
        grid.set_row_spacing(4)
        grid.set_halign(Gtk.Align.START)
        self.swatches = []
        tm = theme.get()
        current = tm.accent_custom or tm.accent_hex(tm.accent_name, dark=False).upper()
        for hexc in theme.WINDOWS_ACCENTS:
            b = Gtk.Button()
            b.add_css_class("color-swatch-btn")
            sw = Gtk.Box()
            sw.add_css_class("color-swatch")
            prov = Gtk.CssProvider()
            prov.load_from_string(f"box {{ background-color: {hexc}; }}")
            sw.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
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
        """Windows accent: exact hex in org.fenestra.desktop (shell, taskbar, GTK) and the
        nearest GNOME accent-color for libadwaita apps."""
        util.gset(theme.FENESTRA, "accent-color-custom", hexc)
        util.gset(IFACE, "accent-color", _nearest_gnome_accent(hexc))
        for b, h in self.swatches:
            (b.add_css_class if h == hexc else b.remove_css_class)("selected")


def _nearest_gnome_accent(hexc):
    import colorsys
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.18:
        return "slate"
    hues = {"red": 0, "orange": 25, "yellow": 48, "green": 120, "teal": 178, "blue": 210, "purple": 270, "pink": 320}
    deg = h * 360
    return min(hues, key=lambda k: min(abs(deg - hues[k]), 360 - abs(deg - hues[k])))


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


@register
class ThemesPage(Page):
    id = "themes"
    parent = "personalization"
    title = "Themes"
    keywords = "gtk theme icons cursor"
    index = [("icons", "Icons", "icon theme"), ("iconpack", "Icon pack", "import icons zip windows"),
             ("cursor", "Mouse cursor", "pointer theme"),
             ("gtk", "App style", "gtk theme legacy apps")]

    def build(self, box):
        top = Gtk.Box(spacing=24)
        top.add_css_class("hero")
        top.append(preview_card(300, 188))
        box.append(top)
        g = self.group(_("Current theme"))
        for key, sk, title, sub, ic, items in (
                ("gtk", "gtk-theme", _("App style"), _("Theme used by GTK 3 apps"), "fs-window-brush-symbolic",
                 _list_themes(["gtk-3.0", "gtk-4.0"])),
                ("icons", "icon-theme", _("Icons"), None, "fs-apps-symbolic", _list_icon_themes()),
                ("cursor", "cursor-theme", _("Mouse cursor"), None, "fs-cursor-symbolic",
                 _list_icon_themes(cursor=True))):
            cur = util.gget(IFACE, sk)
            if cur is None:
                continue
            if util.DEMO:
                from ..backends import demo
                items = demo.THEMES[sk]
                cur = items[0]
            opts = [(t, t) for t in items]
            if cur not in items:
                opts.insert(0, (cur, cur))
            dd = Dropdown(opts, cur, lambda v, sk=sk: util.gset(IFACE, sk, v), width=220)
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
        g2.add(SettingRow(_("Screen timeout"), None, "fs-timer-symbolic", chevron=True,
                          on_click=lambda: self.go("power", "screen-sleep")))
        g2.add(SettingRow(_("Screen lock"), _("Lock automatically and require a password"), "fs-lock-shield-symbolic",
                          chevron=True, on_click=lambda: self.go("screenlock")))

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
        g = self.group()
        if util.settings(ARCMENU) is None:
            g.add(not_available_row(_("Start menu"), _("The Start menu extension is not installed"),
                                    "fs-grid-symbolic"))
        else:
            cur = util.gget(ARCMENU, "menu-layout")
            opts = [(k, _(v)) for k, v in START_LAYOUTS]
            if cur not in [o[0] for o in opts]:
                opts.append((cur, str(cur)))
            r = SettingRow(_("Layout"), _("Choose how the Start menu looks"), "fs-grid-symbolic",
                           control=gsetting_dropdown(ARCMENU, "menu-layout", opts), key="start-layout")
            self.remember("start-layout", r)
            g.add(r)
            for key, title, sub in (("eleven-show-frequent-apps", _("Show most used apps"), None),
                                    ("show-recently-installed-apps", _("Show recently added apps"), None),
                                    ("show-user-avatar", _("Show my account picture"), None)):
                t = gsetting_toggle(ARCMENU, key)
                if t:
                    g.add(SettingRow(title, sub, "fs-apps-symbolic", control=t))
        t = gsetting_toggle(PRIVACY, "remember-recent-files")
        if t:
            r = SettingRow(_("Show recommended files in Start and recent files in the file manager"),
                           None, "fs-document-symbolic", control=t, key="recent-items")
            self.remember("recent-items", r)
            g.add(r)
        if util.settings(ARCMENU) is not None:
            n = len(util.gget(ARCMENU, "pinned-apps", []) or [])
            self.pin_row = SettingRow(_("Pinned apps"), _("{0} apps pinned to Start").format(n), "fs-star-symbolic",
                                      control=button(_("Reset"), self._reset_pins), key="pinned-reset")
            self.remember("pinned-reset", self.pin_row)
            g.add(self.pin_row)
        g2 = self.group(_("Related settings"))
        g2.add(SettingRow(_("Installed apps"), None, "fs-apps-list-symbolic", chevron=True,
                          on_click=lambda: self.go("installed")))

    def _reset_pins(self):
        def go():
            if not util.greset(ARCMENU, "pinned-apps"):
                toast(self.box, _("This action is disabled in read-only mode"))
                return
            n = len(util.gget(ARCMENU, "pinned-apps", []) or [])
            self.pin_row.set_subtitle(_("{0} apps pinned to Start").format(n))
        from ..widgets import confirm
        confirm(self.box, _("Reset pinned apps?"), _("Start will go back to the default set of pinned apps."),
                _("Reset"), go)


def _dtp_json(key):
    import json
    try:
        return json.loads(util.gget(DTP, key, "{}") or "{}")
    except ValueError:
        return {}


def _dtp_set_all(key, value):
    """Per-monitor JSON keys: apply the value to every known monitor."""
    import json
    d = _dtp_json(key) or {"0": value}
    for mon in d:
        d[mon] = value
    return util.gset(DTP, key, json.dumps(d))


def _dtp_first(key, default):
    d = _dtp_json(key)
    return next(iter(d.values()), default) if d else default


DTP_DEFAULT_ELEMENTS = [
    {"element": "showAppsButton", "visible": False, "position": "stackedTL"},
    {"element": "activitiesButton", "visible": False, "position": "stackedTL"},
    {"element": "leftBox", "visible": True, "position": "stackedTL"},
    {"element": "taskbar", "visible": True, "position": "stackedTL"},
    {"element": "centerBox", "visible": True, "position": "stackedBR"},
    {"element": "rightBox", "visible": True, "position": "stackedBR"},
    {"element": "dateMenu", "visible": True, "position": "stackedBR"},
    {"element": "systemMenu", "visible": True, "position": "stackedBR"},
    {"element": "desktopButton", "visible": True, "position": "stackedBR"},
]


def _dtp_elements():
    """Per-monitor element layout; synthesised from Dash to Panel's defaults when unset."""
    import copy
    d = _dtp_json("panel-element-positions")
    if not d:
        mons = list(_dtp_json("panel-positions")) or ["0"]
        d = {m: copy.deepcopy(DTP_DEFAULT_ELEMENTS) for m in mons}
    return d


def _dtp_element(name):
    for mon in _dtp_elements().values():
        for e in mon:
            if e.get("element") == name:
                return e
    return None


def _dtp_update_element(names, **changes):
    import json
    names = [names] if isinstance(names, str) else names
    d = _dtp_elements()
    if not d:
        return False
    for mon in d.values():
        for e in mon:
            if e.get("element") in names:
                e.update(changes)
    return util.gset(DTP, "panel-element-positions", json.dumps(d))


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

    def build(self, box):
        # Taskbar items: Search and Widgets (weather), like the reference page.
        gi_ = self.group(_("Taskbar items"))
        search = gsetting_dropdown("org.fenestra.desktop", "taskbar-search",
                                   [("hide", _("Hide")), ("icon", _("Search icon only")),
                                    ("icon-label", _("Search icon and label")), ("box", _("Search box"))])
        if search:
            r = SettingRow(_("Search"), None, "fs-search-symbolic", control=search, key="tb-search")
            self.remember("tb-search", r)
            gi_.add(r)
        widgets = gsetting_toggle("org.fenestra.desktop", "taskbar-widgets")
        if widgets:
            r = SettingRow(_("Widgets"), _("Weather at the left end of the taskbar"), "fs-weather-sunny-symbolic",
                           control=widgets, key="tb-widgets")
            self.remember("tb-widgets", r)
            gi_.add(r)
        if not search and not widgets:
            gi_.add(not_available_row(_("Taskbar items")))
        g = self.group(_("Taskbar behaviors"))
        if util.settings(DTP) is None:
            r = not_available_row(_("Taskbar behaviors"), _("The taskbar extension is not installed"),
                                  "fs-panel-bottom-symbolic")
            g.add(r)
        else:
            tb = _dtp_element("taskbar") or {}
            align = "center" if tb.get("position", "centerMonitor").startswith("center") else "left"

            def set_align(v):
                pos = "centerMonitor" if v == "center" else "stackedTL"
                ok = _dtp_update_element(["taskbar", "leftBox"], position=pos)
                if not ok:
                    toast(self.box, _("This action is disabled in read-only mode"))
            r = SettingRow(_("Taskbar alignment"), None, "fs-panel-bottom-symbolic",
                           control=Dropdown([("center", _("Center")), ("left", _("Left"))], align, set_align),
                           key="tb-align")
            self.remember("tb-align", r)
            g.add(r)
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
                             control=Dropdown(opts, size, lambda v: _dtp_set_all("panel-sizes", int(v)))))
            ah = gsetting_toggle(DTP, "intellihide")
            if ah:
                r = SettingRow(_("Automatically hide the taskbar"), None, "fs-panel-bottom-symbolic", control=ah,
                               key="tb-autohide")
                self.remember("tb-autohide", r)
                g.add(r)
            grp = gsetting_toggle(DTP, "group-apps")
            if grp:
                g.add(SettingRow(_("Combine taskbar buttons"), None, "fs-apps-symbolic", control=grp))
            desk = _dtp_element("desktopButton")
            if desk is not None:
                g.add(SettingRow(_("Select the far corner of the taskbar to show the desktop"), None,
                                 "fs-desktop-symbolic",
                                 control=ToggleSwitch(bool(desk.get("visible", True)),
                                                      lambda v: _dtp_update_element("desktopButton", visible=v))))
            tr = gsetting_toggle(DTP, "trans-use-custom-opacity")
            if tr:
                g.add(SettingRow(_("Taskbar transparency"), None, "fs-circle-half-fill-symbolic", control=tr))
                op = util.gget(DTP, "trans-panel-opacity", 0.8)
                g.add(SettingRow(_("Taskbar opacity"), None, "fs-circle-half-fill-symbolic",
                                 control=Slider(0, 100, round(op * 100),
                                                lambda v: util.gset(DTP, "trans-panel-opacity", round(v) / 100.0),
                                                fmt="{:.0f}%", width=200)))
        g2 = self.group(_("Clock"))
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
            g2.add(SettingRow(_("Time format"), None, "fs-clock-symbolic", control=fmt))


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
        for key, sk, t in (("font-ui", "font-name", _("Interface text")),
                           ("font-doc", "document-font-name", _("Document text")),
                           ("font-mono", "monospace-font-name", _("Monospace text"))):
            cur = util.gget(IFACE, sk)
            if cur is None:
                continue
            if util.DEMO:
                cur = {"font-name": "Inter 11", "document-font-name": "Inter 11",
                       "monospace-font-name": "Adwaita Mono 11"}[sk]
            fb = Gtk.FontDialogButton.new(Gtk.FontDialog())
            fb.set_font_desc(Pango.FontDescription.from_string(cur))
            fb.add_css_class("fluent-fontbutton")
            fb.set_valign(Gtk.Align.CENTER)
            fb.connect("notify::font-desc", lambda b, _p, sk=sk: util.gset(IFACE, sk, b.get_font_desc().to_string()))
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

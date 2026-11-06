"""Widgets shared by several pages: thumbnails, device hero, info bars."""
from __future__ import annotations

import threading

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from .. import theme, util  # noqa: E402
from ..backends import system_info  # noqa: E402
from ..i18n import _  # noqa: E402
from ..widgets import icon, label, link  # noqa: E402

_thumb_cache: dict[tuple, Gdk.Texture] = {}


class Thumb(Gtk.Box):
    """Fixed-size, rounded, cover-cropped image loaded in a worker thread."""

    def __init__(self, path, width, height, css="thumb"):
        super().__init__()
        # Without a layout manager GTK calls do_measure/do_size_allocate below, so the
        # thumb keeps its fixed size instead of growing to the picture's natural size.
        self.set_layout_manager(None)
        self.w, self.h = width, height
        self.set_size_request(width, height)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.add_css_class(css)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.pic = Gtk.Picture()
        self.pic.set_content_fit(Gtk.ContentFit.COVER)
        self.pic.set_can_shrink(True)
        self.pic.set_size_request(width, height)
        self.pic.set_hexpand(False)
        self.append(self.pic)
        self.set_hexpand(False)
        self.set_path(path)

    def do_measure(self, orientation, for_size):
        v = self.w if orientation == Gtk.Orientation.HORIZONTAL else self.h
        return v, v, -1, -1

    def do_size_allocate(self, width, height, baseline):
        alloc = Gdk.Rectangle()
        alloc.x, alloc.y, alloc.width, alloc.height = 0, 0, width, height
        self.pic.size_allocate(alloc, -1)

    def set_path(self, path):
        if not path:
            return
        key = (path, self.w, self.h)
        if key in _thumb_cache:
            self.pic.set_paintable(_thumb_cache[key])
            return

        def work():
            try:
                _fmt, sw, sh = GdkPixbuf.Pixbuf.get_file_info(path)
                tw, th = self.w * 2, self.h * 2
                if not sw or not sh:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, tw, th, False)
                else:
                    scale = min(1.0, max(tw / sw, th / sh))
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        path, max(1, int(sw * scale)), max(1, int(sh * scale)), False)
                tex = Gdk.Texture.new_for_pixbuf(pb)
            except GLib.Error:
                return
            _thumb_cache[key] = tex
            GLib.idle_add(lambda: (self.pic.set_paintable(tex), False)[1])
        threading.Thread(target=work, daemon=True).start()


def wallpaper_thumb(width, height, css="hero-thumb", dark=None):
    d = theme.get().dark if dark is None else dark
    return Thumb(system_info.wallpaper_path(d), width, height, css)


class MiniWindow(Gtk.Box):
    """Tiny window mock drawn over theme previews."""

    def __init__(self, dark, accent, w=60, h=40):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("mini-window")
        self.add_css_class("dark" if dark else "light")
        self.set_size_request(w, h)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        bar = Gtk.Box()
        bar.add_css_class("mini-accent")
        bar.set_size_request(w // 3, 6)
        bar.set_halign(Gtk.Align.START)
        bar.set_margin_start(8)
        bar.set_margin_top(h - 16)
        self.append(bar)
        prov = Gtk.CssProvider()
        prov.load_from_string(f"box {{ background-color: {accent}; }}")
        bar.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)


def theme_preview(dark: bool, width=120, height=80, wallpaper_dark=None):
    ov = Gtk.Overlay()
    ov.set_size_request(width, height)
    wd = dark if wallpaper_dark is None else wallpaper_dark
    ov.set_child(wallpaper_thumb(width, height, "thumb-picture", wd))
    acc = theme.get().accent_hex(dark=dark)
    ov.add_overlay(MiniWindow(dark, acc, width // 2, height // 2))
    return ov


def theme_tiles():
    """Six 112x90 theme tiles (wallpaper + light/dark mini window), 3 per row, 8 px apart,
    as on the reference Home and Personalization pages. A click applies wallpaper + mode."""
    from ..backends import appearance
    from .personalization import find_backgrounds
    grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    grid.add_css_class("theme-tiles")
    rows = [Gtk.Box(spacing=8, halign=Gtk.Align.START) for _r in range(2)]
    for r in rows:
        grid.append(r)
    paths = find_backgrounds(6) or [system_info.wallpaper_path(theme.get().dark)]

    def apply(path, dark):
        if util.READ_ONLY:
            return
        appearance.set_wallpaper(path)
        appearance.set_color_scheme("dark" if dark else "light")

    for i in range(6):
        path = paths[i % len(paths)]
        dark = i % 3 == 1 or i >= 3
        b = Gtk.Button()
        b.add_css_class("home-theme-tile")
        b.set_halign(Gtk.Align.START)
        b.set_valign(Gtk.Align.START)
        ov = Gtk.Overlay()
        ov.set_child(Thumb(path, 112, 90, "thumb-picture"))
        mw = MiniWindow(dark, theme.get().accent_hex(dark=dark), 41, 40)
        mw.set_halign(Gtk.Align.END)
        mw.set_valign(Gtk.Align.END)
        mw.set_margin_end(5)
        mw.set_margin_bottom(5)
        ov.add_overlay(mw)
        b.set_child(ov)
        b.set_tooltip_text(_("Dark") if dark else _("Light"))
        b.connect("clicked", lambda _b, p=path, d=dark: apply(p, d))
        rows[i // 3].append(b)
    return grid


def device_hero(page, show_status=True):
    """Device banner: wallpaper thumb, device name, model, Rename link."""
    box = Gtk.Box(spacing=0)
    box.add_css_class("hero")
    box.add_css_class("device-hero")
    thumb_frame = Gtk.Box()
    thumb_frame.add_css_class("hero-device")
    thumb = wallpaper_thumb(112, 60, "hero-thumb")
    thumb_frame.append(thumb)
    box.append(thumb_frame)
    texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START, spacing=0)
    texts.add_css_class("hero-texts")
    texts.set_margin_start(16)
    name = label(system_info.hostname(), "hero-name", ellipsize=True)
    texts.append(name)
    mdl = system_info.model()
    if mdl:
        texts.append(label(mdl, "hero-model", ellipsize=True))
    texts.append(link(_("Rename"), lambda: rename_dialog(page, name)))
    texts.set_hexpand(True)
    box.append(texts)
    if show_status:
        st = Gtk.Box(spacing=24, valign=Gtk.Align.START)
        st.add_css_class("hero-status")
        net_item = _status_item("fs-wifi-1-symbolic", _("Network"), _("Checking…"),
                                lambda: page.go("network"))
        st.append(net_item)
        upd_item = _status_item("fs-arrow-sync-symbolic", _("Fenestra Update"), _update_status_text(),
                                lambda: page.go("update"))
        st.append(upd_item)
        box.append(st)

        from ..backends import network

        def got(res):
            wifi = [d for d in res["devices"] if d.connected and d.type in ("wifi", "ethernet")]
            if wifi:
                d = wifi[0]
                net_item.sub.set_label(d.connection or _("Connected"))
                net_item.title.set_label(_("Wi-Fi") if d.type == "wifi" else _("Ethernet"))
                if d.type == "ethernet":
                    net_item.ic.set_from_icon_name("fs-plug-connected-symbolic")
            else:
                net_item.sub.set_label(_("Not connected"))
        network.status(got)
        page.hero_status = st
    page.hero_name = name
    return box


def _update_status_text():
    from ..backends import packages
    t = packages.last_checked()
    if packages.offline_pending():
        return _("Restart required")
    if not t:
        return _("Check for updates")
    return _("Last checked: {0}").format(GLib.DateTime.new_from_unix_local(int(t)).format("%x %H:%M"))


def _status_item(icon_name, title, sub, cb):
    b = Gtk.Button()
    b.add_css_class("hero-status-item")
    bx = Gtk.Box(spacing=16)
    ic = icon(icon_name, 20, "accent-icon")
    ic.set_valign(Gtk.Align.START)
    ic.add_css_class("hero-status-icon")
    bx.append(ic)
    tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    t = label(title, "hero-status-title", ellipsize=True)
    s = label(sub, "hero-status-sub", wrap=True)
    s.set_max_width_chars(24)
    s.set_lines(2)
    s.set_ellipsize(Pango.EllipsizeMode.END)
    tb.append(t)
    tb.append(s)
    bx.append(tb)
    b.set_child(bx)
    b.connect("clicked", lambda *_: cb())
    b.ic, b.title, b.sub = ic, t, s
    return b


def rename_dialog(page, name_label=None):
    from ..widgets import ContentDialog, show_dialog, toast
    entry = Gtk.Entry()
    entry.add_css_class("fluent-entry")
    entry.set_text(system_info.hostname())
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.append(label(_("Current PC name: {0}").format(system_info.hostname()), "caption"))
    box.append(entry)
    box.append(label(_("You can use a combination of letters, hyphens, and numbers."), "caption",
                     wrap=True))

    def resp(r):
        if r != "primary":
            return
        new = entry.get_text().strip()
        if not new:
            return
        if util.READ_ONLY:
            toast(page.box, _("This action is disabled in read-only mode"))
            return

        def done(ok, _res):
            if ok:
                if name_label is not None:
                    name_label.set_label(new)
                toast(page.box, _("Your PC has been renamed"))
            else:
                toast(page.box, _("Could not rename this PC"))
        system_info.rename(new, done)
    dlg = ContentDialog(_("Rename your PC"), None, primary=_("Next"), close=_("Cancel"),
                        on_response=resp, extra=box)
    entry.connect("activate", lambda *_: dlg.respond("primary"))
    show_dialog(page.box, dlg)


def infobar(text, title=None, caution=False, action: Gtk.Widget | None = None):
    b = Gtk.Box(spacing=12)
    b.add_css_class("infobar")
    if caution:
        b.add_css_class("caution")
    b.append(icon("fs-info-symbolic", 16, "infobar-icon"))
    tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
    if title:
        tb.append(label(title, "body-strong"))
    tb.append(label(text, wrap=True))
    b.append(tb)
    if action is not None:
        b.append(action)
    return b


def gsetting_toggle(schema, key, invert=False, on_after=None):
    """ToggleSwitch bound to a boolean GSettings key; None if unavailable."""
    from ..widgets import ToggleSwitch
    if not util.has_key(schema, key):
        return None
    val = bool(util.gget(schema, key))

    def changed(v):
        util.gset(schema, key, (not v) if invert else v)
        if on_after:
            on_after(v)
    t = ToggleSwitch(val != invert, changed)
    util.gconnect(schema, key, lambda: t.set_active(bool(util.gget(schema, key)) != invert))
    return t


def gsetting_dropdown(schema, key, options, cast=None):
    from ..widgets import Dropdown
    if not util.has_key(schema, key):
        return None
    cur = util.gget(schema, key)
    ids = [o[0] for o in options]
    if cur not in ids:
        options = options + [(cur, str(cur))]
    dd = Dropdown(options, cur, lambda v: util.gset(schema, key, cast(v) if cast else v))
    # follow external changes (other apps, gsettings, dconf-editor)
    util.gconnect(schema, key, lambda: dd.select(util.gget(schema, key)))
    return dd

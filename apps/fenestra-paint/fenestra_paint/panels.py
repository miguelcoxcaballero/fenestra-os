"""Side panels: layers, size/opacity sliders, status bar, settings page and thumbnail."""
from __future__ import annotations

import math

import cairo
from gi.repository import Gdk, GLib, GObject, Graphene, Gtk

from . import __version__, raster, theme, util
from .canvas import ZOOM_MAX, ZOOM_MIN, ZOOM_PRESETS
from .i18n import _
from .widgets import Menu, Slider, button, icon, label, popup_menu, radio_group


def _checker(cr, x, y, w, h, cell=6):
    cr.save()
    cr.rectangle(x, y, w, h)
    cr.clip()
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.set_source_rgb(0.85, 0.85, 0.85)
    for j in range(int(h // cell) + 1):
        for i in range(int(w // cell) + 1):
            if (i + j) % 2:
                cr.rectangle(x + i * cell, y + j * cell, cell, cell)
    cr.fill()
    cr.restore()


def draw_fitted(cr, surf, w, h, checker=True, bg=None):
    """Paint surf scaled to fit (w, h), centred."""
    sw, sh = surf.get_width(), surf.get_height()
    s = min(w / sw, h / sh)
    dw, dh = sw * s, sh * s
    x, y = (w - dw) / 2, (h - dh) / 2
    if bg is not None:
        cr.rectangle(x, y, dw, dh)
        cr.set_source_rgb(*bg)
        cr.fill()
    elif checker:
        _checker(cr, x, y, dw, dh)
    cr.save()
    cr.translate(x, y)
    cr.scale(s, s)
    cr.set_source_surface(surf, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    cr.restore()
    return x, y, dw, dh


class Thumb(Gtk.Widget):
    __gtype_name__ = "FenestraPaintThumb"

    def __init__(self, get_surface, size=72, bg=None):
        super().__init__()
        self.get_surface = get_surface
        self.size = size
        self.bg = bg

    def do_measure(self, orientation, for_size):
        return self.size, self.size, -1, -1

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        surf = self.get_surface()
        if surf is None:
            return
        cr = snap.append_cairo(Graphene.Rect().init(0, 0, w, h))
        draw_fitted(cr, surf, w, h, bg=self.bg() if callable(self.bg) else self.bg)


# =========================================================================== layers

class LayersPanel(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.add_css_class("layers-panel")
        add = button(icon("add-circle", 16), "panel-icon-button", tooltip=_("Add layer"),
                     cb=lambda: win.doc.add_layer())
        add.set_halign(Gtk.Align.CENTER)
        self.append(add)
        self.append(Gtk.Separator())
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_vexpand(True)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.list.add_css_class("layer-list")
        sc.set_child(self.list)
        self.append(sc)
        self.bg_tile = None
        bgwrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bgwrap.add_css_class("bg-wrap")
        self.bg_btn = Gtk.Button()
        self.bg_btn.add_css_class("bg-tile")
        self.bg_btn.set_tooltip_text(_("Background"))
        ov = Gtk.Overlay()
        self.bg_thumb = Thumb(self._bg_surface, 56)
        self.bg_thumb.add_css_class("bg-paper")
        self.bg_thumb.set_halign(Gtk.Align.CENTER)
        self.bg_thumb.set_valign(Gtk.Align.CENTER)
        ov.set_child(self.bg_thumb)
        self.bg_eye = icon("eye-off", 16, "tile-badge")
        self.bg_eye.set_halign(Gtk.Align.END)
        self.bg_eye.set_valign(Gtk.Align.START)
        ov.add_overlay(self.bg_eye)
        self.bg_btn.set_child(ov)
        self.bg_btn.connect("clicked", lambda *_a: self._bg_menu())
        bgwrap.append(self.bg_btn)
        self.append(bgwrap)
        self.append(Gtk.Separator())
        self.tiles = []
        self._pending = 0

    def _bg_surface(self):
        s = raster.new_surface(56, 56)
        if self.win.doc is not None and self.win.doc.bg_visible:
            cr = cairo.Context(s)
            cr.set_source_rgb(*self.win.doc.bg_color)
            cr.paint()
        return s

    def _bg_menu(self):
        doc = self.win.doc
        m = Menu(self.win, width=200)
        m.add(_("Hide background") if doc.bg_visible else _("Show background"),
              lambda: doc.set_bg_visible(not doc.bg_visible), icon_name="eye-off" if doc.bg_visible else "eye")
        popup_menu(self.win, m, self.bg_btn, align="end")

    def rebuild(self):
        doc = self.win.doc
        child = self.list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.list.remove(child)
            child = nxt
        self.tiles = []
        for idx in reversed(range(len(doc.layers))):
            self.list.append(self._tile(idx))
        self.bg_eye.set_visible(not doc.bg_visible)
        self.bg_thumb.queue_draw()

    def _tile(self, idx):
        doc = self.win.doc
        layer = doc.layers[idx]
        b = Gtk.Button()
        b.add_css_class("layer-tile")
        if idx == doc.active:
            b.add_css_class("selected")
        b.set_tooltip_text(layer.name + ("" if layer.opacity >= 1 else f" ({round(layer.opacity * 100)}%)"))
        ov = Gtk.Overlay()
        th = Thumb(lambda layer=layer: layer.surface, 76)
        if not layer.visible:
            th.set_opacity(0.4)
        ov.set_child(th)
        if not layer.visible:
            eye = icon("eye-off", 16, "tile-badge")
            eye.set_halign(Gtk.Align.END)
            eye.set_valign(Gtk.Align.START)
            ov.add_overlay(eye)
        more = button(icon("more", 16), "tile-more", tooltip=_("Layer options"))
        more.set_halign(Gtk.Align.END)
        more.set_valign(Gtk.Align.END)
        more.connect("clicked", lambda *_a: self.layer_menu(idx, more))
        ov.add_overlay(more)
        b.set_child(ov)
        b.connect("clicked", lambda *_a: self.win.select_layer(idx))
        g = Gtk.GestureClick(button=3)
        g.connect("pressed", lambda *_a: self.layer_menu(idx, b))
        b.add_controller(g)
        # drag to reorder
        src = Gtk.DragSource()
        src.set_actions(Gdk.DragAction.MOVE)
        src.connect("prepare", lambda *_a: Gdk.ContentProvider.new_for_value(str(idx)))
        b.add_controller(src)
        dt = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        dt.connect("drop", lambda _t, v, _x, _y, j=idx: self._drop(v, j))
        b.add_controller(dt)
        self.tiles.append((b, th))
        return b

    def _drop(self, v, j):
        try:
            i = int(v)
        except (TypeError, ValueError):
            return False
        if i == j:
            return False
        self.win.commit_tool()
        doc = self.win.doc

        def fn():
            act = doc.layers[doc.active]
            layer = doc.layers.pop(i)
            doc.layers.insert(j, layer)
            doc.active = doc.layers.index(act)
        doc.structural(fn, _("Move layer"))
        return True

    def layer_menu(self, idx, anchor):
        win, doc = self.win, self.win.doc
        layer = doc.layers[idx]
        n = len(doc.layers)
        m = Menu(win, width=230)

        def act(fn):
            def run():
                win.commit_tool()
                fn()
            return run
        m.add(_("Hide layer") if layer.visible else _("Show layer"),
              act(lambda: doc.set_layer_visible(idx, not layer.visible)),
              icon_name="eye-off" if layer.visible else "eye")
        m.add(_("Duplicate layer"), act(lambda: doc.duplicate_layer(idx)), icon_name="duplicate")
        m.add(_("Merge down"), act(lambda: doc.merge_down(idx)), icon_name="merge", sensitive=idx > 0)
        m.add(_("Move layer up"), act(lambda: doc.move_layer(idx, 1)), icon_name="arrow-up", sensitive=idx < n - 1)
        m.add(_("Move layer down"), act(lambda: doc.move_layer(idx, -1)), icon_name="arrow-down", sensitive=idx > 0)
        m.add(_("Layer opacity"), icon_name="opacity", submenu=lambda lvl: self._opacity_menu(idx, lvl))
        m.add_separator()
        m.add(_("Delete layer"), act(lambda: doc.delete_layer(idx)), icon_name="delete")
        popup_menu(win, m, anchor, align="end")

    def _opacity_menu(self, idx, level):
        win, doc = self.win, self.win.doc
        m = Menu(win, level, width=220)
        box = Gtk.Box(spacing=8)
        box.add_css_class("menu-slider")
        start = doc.layers[idx].opacity
        val = label(f"{round(start * 100)}%", "menu-value")
        sl = Slider(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, start, length=140)

        def changed(*_a):
            val.set_text(f"{round(sl.value * 100)}%")
            doc.set_layer_opacity(idx, sl.value, record=False)

        def released(*_a):
            v = sl.value
            doc.layers[idx].opacity = start
            if abs(v - start) > 1e-4:
                win.commit_tool()
                doc.set_layer_opacity(idx, v)
        sl.connect("value-changed", changed)
        sl.connect("released", released)
        box.append(sl)
        box.append(val)
        m.add_widget(box)
        return m

    def refresh_thumbs(self):
        if self._pending:
            return
        self._pending = GLib.timeout_add(150, self._refresh)

    def _refresh(self):
        self._pending = 0
        for _b, th in self.tiles:
            th.queue_draw()
        self.bg_thumb.queue_draw()
        return False


# =========================================================================== sliders

def _size_map():
    to = lambda v: max(0.0, (v - 1) / 99)
    fr = lambda f: max(1, round(1 + f * 99))
    return to, fr


class SideSliders(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.win = win
        self.add_css_class("side-sliders")
        self.set_halign(Gtk.Align.START)
        self.set_homogeneous(True)
        self.size_card, self.size = self._card("size", _("Size"), Slider(Gtk.Orientation.VERTICAL, 1, 100, 5,
                                                                        length=120, mapping=_size_map()))
        self.op_card, self.opacity = self._card("opacity", _("Opacity"),
                                                Slider(Gtk.Orientation.VERTICAL, 0.01, 1.0, 1.0, length=120))
        self.size.connect("value-changed", lambda s: win.set_size(s.value, from_slider=True))
        self.opacity.connect("value-changed", lambda s: win.set_opacity(s.value, from_slider=True))
        for s in (self.size, self.opacity):
            s.connect("released", lambda *_a: win.hide_bubble())
        self.append(self.size_card)
        self.append(self.op_card)

    def _card(self, ic, tip, slider):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("slider-card")
        card.set_tooltip_text(tip)
        card.append(icon(ic, 16, "slider-icon"))
        slider.set_vexpand(True)
        slider.set_halign(Gtk.Align.CENTER)
        card.append(slider)
        return card, slider

    def sync(self):
        w = self.win
        t = w.tool
        self.size.set_value(w.size_for(w.size_key))
        self.opacity.set_value(w.opacity)
        self.size_card.set_sensitive(t.uses_size)
        self.op_card.set_sensitive(t.uses_opacity)


# =========================================================================== status bar

class StatusBar(Gtk.Box):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.add_css_class("statusbar")
        self.pos = self._item("cursor", 133)
        self.sel = self._item("select-size", 132)
        self.size = self._item("canvas-size", 200, 5)
        self.append(Gtk.Box(hexpand=True))
        fit = button(icon("fit", 24), "status-button", tooltip=_("Fit to window"), cb=win.zoom_fit)
        self.append(fit)
        zb = Gtk.Box()
        self.zoom_label = label("100%", "zoom-label")
        self.zoom_label.set_xalign(0)
        self.zoom_label.set_hexpand(True)
        zb.append(self.zoom_label)
        zb.append(icon("chevron-down", 12, "zoom-chev"))
        self.zoom_btn = button(zb, "zoom-combo", tooltip=_("Zoom"), cb=self._zoom_menu)
        self.zoom_btn.set_hexpand(False)
        self.zoom_btn.set_valign(Gtk.Align.CENTER)
        self.append(self.zoom_btn)
        self.append(button(icon("zoom-out", 18), "status-button", "zoom-out", tooltip=_("Zoom out"),
                           cb=lambda: win.canvas.zoom_step(-1)))
        # Linear track as in the reference (100 % sits near the left end).
        lo = -0.14
        self.slider = Slider(Gtk.Orientation.HORIZONTAL, ZOOM_MIN, ZOOM_MAX, 1.0, length=146,
                             mapping=(lambda v: (v - lo) / (ZOOM_MAX - lo),
                                      lambda f: max(ZOOM_MIN, lo + f * (ZOOM_MAX - lo))))
        self.slider.add_css_class("zoom-slider")
        self.slider.connect("value-changed", lambda s: win.canvas.set_zoom(s.value))
        self.append(self.slider)
        self.append(button(icon("zoom-in", 18), "status-button", "zoom-in", tooltip=_("Zoom in"),
                           cb=lambda: win.canvas.zoom_step(1)))

    def _item(self, ic, width, spacing=8):
        b = Gtk.Box(spacing=spacing)
        b.add_css_class("status-item")
        b.set_size_request(width, -1)
        b.append(icon(ic, 16))
        lb = label("", "status-text")
        b.append(lb)
        self.append(b)
        return lb

    def _zoom_menu(self):
        win = self.win
        m = Menu(win, width=150)
        for z in reversed(ZOOM_PRESETS):
            m.add(f"{int(z * 100) if z >= 1 else z * 100:g}%", lambda z=z: win.canvas.set_zoom(z),
                  selected=abs(win.canvas.zoom - z) < 1e-6)
        m.add_separator()
        m.add(_("Fit to window"), win.zoom_fit)
        popup_menu(win, m, self.zoom_btn, above=True)

    def set_zoom(self, z):
        self.zoom_label.set_text(f"{z * 100:.0f}%" if z * 100 >= 10 else f"{z * 100:.1f}%")
        self.slider.set_value(z)


# =========================================================================== settings

class SettingsPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.add_css_class("settings-page")
        head = Gtk.Box(spacing=16)
        head.add_css_class("settings-head")
        head.append(button(icon("back", 16), "back-button", tooltip=_("Back"), cb=win.close_settings))
        head.append(label(_("Settings"), "settings-title"))
        self.append(head)
        cols = Gtk.Box(spacing=56)
        cols.add_css_class("settings-cols")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left.set_size_request(1000, -1)
        left.append(label(_("Appearance"), "settings-section"))
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("settings-card")
        hdr = Gtk.Box(spacing=16)
        hdr.add_css_class("card-head")
        hdr.append(icon("theme", 16))
        hdr.append(label(_("App theme"), "card-title"))
        hdr.append(Gtk.Box(hexpand=True))
        self.chev = icon("chevron-up", 12)
        hdr.append(self.chev)
        hb = Gtk.Button()
        hb.set_child(hdr)
        hb.add_css_class("card-head-button")
        card.append(hb)
        self.rev = Gtk.Revealer()
        self.rev.set_reveal_child(True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.add_css_class("card-body")
        cur = util.opts()["theme"]
        self.radios = radio_group([("light", _("Light")), ("dark", _("Dark")), ("system", _("Use system setting"))],
                                  cur, win.set_app_theme)
        body.append(self.radios)
        self.rev.set_child(body)
        card.append(self.rev)

        def toggle(*_a):
            on = not self.rev.get_reveal_child()
            self.rev.set_reveal_child(on)
            self.chev.set_from_icon_name("pt-chevron-up-symbolic" if on else "pt-chevron-down-symbolic")
        hb.connect("clicked", toggle)
        left.append(card)
        cols.append(left)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        right.set_size_request(560, -1)
        right.append(label(_("About Paint"), "settings-section", "about-title"))
        right.append(label("Fenestra Paint " + __version__, "about-line"))
        right.append(label(_("An image editor for Fenestra OS."), "about-line"))
        right.append(label(_("Free software, GPL-3.0-or-later. Icons: Fluent UI System Icons (MIT)."),
                           "about-line", wrap=True))
        link = Gtk.LinkButton.new_with_label(util.PROJECT_URL, _("Project website"))
        link.add_css_class("about-link")
        link.set_halign(Gtk.Align.START)
        right.append(link)
        cols.append(right)
        self.append(cols)

    def sync(self):
        cur = util.opts()["theme"]
        b = self.radios.btns.get(cur)
        if b is not None and not b.get_active():
            b.set_active(True)


# =========================================================================== thumbnail

class ThumbnailView(Gtk.Box):
    """View > Thumbnail: small floating view of the whole image."""

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.add_css_class("thumbnail-card")
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.START)
        head = Gtk.Box()
        head.append(label(_("Thumbnail"), "thumb-title"))
        head.append(Gtk.Box(hexpand=True))
        head.append(button(icon("dismiss", 12), "panel-icon-button", tooltip=_("Close"),
                           cb=lambda: win.set_thumbnail(False)))
        self.append(head)
        self.view = Thumb(lambda: win.doc.composite if win.doc else None, 180)
        self.view.set_size_request(220, 140)
        self.append(self.view)
        self._pending = 0

    def refresh(self):
        if self._pending or not self.get_visible():
            return
        self._pending = GLib.timeout_add(120, self._do)

    def _do(self):
        self._pending = 0
        self.view.queue_draw()
        return False


class Toast(Gtk.Revealer):
    def __init__(self):
        super().__init__()
        self.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self.lbl = label("", "toast")
        self.set_child(self.lbl)
        self.set_can_target(False)
        self._id = 0

    def show(self, text, secs=3):
        self.lbl.set_text(text)
        self.set_reveal_child(True)
        if self._id:
            GLib.source_remove(self._id)
        self._id = GLib.timeout_add(int(secs * 1000), self._hide)

    def _hide(self):
        self._id = 0
        self.set_reveal_child(False)
        return False


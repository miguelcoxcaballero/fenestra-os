"""Building blocks in Fenestra's visual language: cards, badges, action buttons with progress,
section headers, toggles, the featured banner and the screenshot carousel."""
from __future__ import annotations

from gi.repository import Gdk, GLib, Gtk, Pango

from . import art, theme, util
from .i18n import _
from .model import AVAILABLE, INSTALLED, QUEUED, SOURCES


def icon(name: str | None, size: int = 16, css: str | None = None) -> Gtk.Image:
    img = Gtk.Image()
    if name:
        img.set_from_icon_name(name)
    img.set_pixel_size(size)
    for c in (css or "").split():
        img.add_css_class(c)
    return img


def label(text: str = "", css=None, wrap=False, xalign=0.0, ellipsize=False, lines=0) -> Gtk.Label:
    lb = Gtk.Label(label=text, xalign=xalign)
    if wrap:
        lb.set_wrap(True)
        lb.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if lines:
        lb.set_lines(lines)
    for c in (css.split() if isinstance(css, str) else css or []):
        lb.add_css_class(c)
    return lb


def clear(box: Gtk.Widget):
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def button(text, css="fluent-button", cb=None, icon_name=None, tooltip=None):
    b = Gtk.Button()
    if icon_name and text:
        box = Gtk.Box(spacing=8)
        box.append(icon(icon_name, 16))
        box.append(label(text))
        b.set_child(box)
    elif icon_name:
        b.set_child(icon(icon_name, 16))
    else:
        b.set_label(text)
    for c in css.split():
        b.add_css_class(c)
    if cb:
        b.connect("clicked", lambda *_: cb())
    if tooltip:
        b.set_tooltip_text(tooltip)
    return b


class Clamp(Gtk.Widget):
    """Limits its child to a maximum width, centred."""
    __gtype_name__ = "FstClamp"

    def __init__(self, child: Gtk.Widget, maximum: int = 1240):
        super().__init__()
        self.maximum = maximum
        self.child = child
        child.set_parent(self)

    def do_dispose(self):
        if self.child is not None:
            self.child.unparent()
            self.child = None
        Gtk.Widget.do_dispose(self)

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        if self.child is None:
            return 0, 0, -1, -1
        if orientation == Gtk.Orientation.VERTICAL and for_size >= 0:
            for_size = min(for_size, self.maximum)
        mn, nat, _a, _b = self.child.measure(orientation, for_size)
        if orientation == Gtk.Orientation.HORIZONTAL:
            nat = max(mn, min(nat, self.maximum))
        return mn, nat, -1, -1

    def do_size_allocate(self, width, height, baseline):
        if self.child is None:
            return
        w = min(width, self.maximum)
        mn, _n, _a, _b = self.child.measure(Gtk.Orientation.HORIZONTAL, -1)
        w = max(w, mn)
        alloc = Gdk.Rectangle()
        alloc.x, alloc.y, alloc.width, alloc.height = (width - w) // 2, 0, w, height
        self.child.size_allocate(alloc, -1)


# --------------------------------------------------------------------------- images

def app_icon(app, size: int) -> Gtk.Image:
    """App icon: AppStream file/stock icon, remote icon (fetched off the UI thread) or generated."""
    img = Gtk.Image()
    img.set_pixel_size(size)
    img.add_css_class("app-icon")
    if app.icon_path:
        img.set_from_file(app.icon_path)
        return img
    if app.icon_name:
        disp = Gdk.Display.get_default()
        if disp and Gtk.IconTheme.get_for_display(disp).has_icon(app.icon_name):
            img.set_from_icon_name(app.icon_name)
            return img
    img.set_from_paintable(art.icon_texture(app, size))
    if app.icon_url and not util.DEMO:
        def got(path):
            if path:
                try:
                    img.set_from_file(path)
                    app.icon_path = path
                except GLib.Error:
                    pass
        util.in_thread(util.fetch_cached, app.icon_url, on_done=got)
    return img


def _file_texture(path):
    return Gdk.Texture.new_from_filename(path) if path else None


def screenshot_picture(app, shot, w=960, h=600) -> Gtk.Picture:
    pic = Gtk.Picture()
    pic.set_content_fit(Gtk.ContentFit.CONTAIN)
    pic.add_css_class("shot-picture")
    if shot.url and not util.DEMO:
        pic.set_paintable(None)

        def load(url):
            return _file_texture(util.fetch_cached(url))

        def done(tex):
            if tex is not None:
                pic.set_paintable(tex)
            else:
                pic.set_paintable(art.screenshot_texture(app, shot.art, w, h, theme.get().dark))
        util.in_thread(load, shot.url, on_done=done, on_error=lambda _e: done(None))
    else:
        pic.set_paintable(art.screenshot_texture(app, shot.art, w, h, theme.get().dark))
    return pic


# --------------------------------------------------------------------------- small pieces

def source_badge(app, small=False) -> Gtk.Label:
    lb = label(_(SOURCES.get(app.source, app.source)), ["source-badge", f"badge-{app.source}"])
    if small:
        lb.add_css_class("small")
    lb.set_valign(Gtk.Align.CENTER)
    lb.set_halign(Gtk.Align.START)
    return lb


def chip(text, css="chip") -> Gtk.Label:
    lb = label(text, css)
    lb.set_valign(Gtk.Align.CENTER)
    return lb


def section_header(title, see_all=None, subtitle=None) -> Gtk.Box:
    box = Gtk.Box(spacing=12)
    box.add_css_class("section-head")
    tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
    tb.append(label(title, "section-title"))
    if subtitle:
        tb.append(label(subtitle, "caption"))
    box.append(tb)
    if see_all:
        b = Gtk.Button()
        inner = Gtk.Box(spacing=6)
        inner.append(label(_("See all")))
        inner.append(icon("st-chevron-right-symbolic", 12))
        b.set_child(inner)
        b.add_css_class("hyperlink")
        b.set_valign(Gtk.Align.END)
        b.connect("clicked", lambda *_: see_all())
        box.append(b)
    return box


def status_text(app) -> str:
    return _(app.status_text) if app.status_text else ""


def card_grid(min_w=232) -> Gtk.FlowBox:
    fb = Gtk.FlowBox()
    fb.set_selection_mode(Gtk.SelectionMode.NONE)
    fb.set_homogeneous(True)
    fb.set_column_spacing(12)
    fb.set_row_spacing(12)
    fb.set_min_children_per_line(1)
    fb.set_max_children_per_line(6)
    fb.add_css_class("card-grid")
    fb.set_valign(Gtk.Align.START)
    fb.min_w = min_w
    return fb


class ToggleSwitch(Gtk.Box):
    """'On'/'Off' label + Fenestra toggle. on_toggled(bool) fires only on user action."""

    def __init__(self, active=False, on_toggled=None):
        super().__init__(spacing=12)
        self.add_css_class("toggle-box")
        self._cb = on_toggled
        self._silent = False
        self.lbl = label("", "toggle-label", xalign=1.0)
        self.lbl.set_width_chars(3)
        self.sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.sw.add_css_class("fluent-toggle")
        c = self.sw.get_first_child()
        while c is not None:
            if isinstance(c, Gtk.Image):
                c.set_visible(False)
            c = c.get_next_sibling()
        self.append(self.lbl)
        self.append(self.sw)
        self.set_valign(Gtk.Align.CENTER)
        self.set_active(active)
        self.sw.connect("notify::active", self._on_notify)

    def _on_notify(self, *_):
        self.lbl.set_label(_("On") if self.sw.get_active() else _("Off"))
        if not self._silent and self._cb:
            self._cb(self.sw.get_active())

    def set_active(self, v):
        self._silent = True
        self.sw.set_active(bool(v))
        self._silent = False
        self.lbl.set_label(_("On") if v else _("Off"))

    def get_active(self):
        return self.sw.get_active()


# --------------------------------------------------------------------------- app card

class AppCard(Gtk.Button):
    """Card: icon + source badge, name, two-line summary, state line. Opens the app page."""

    def __init__(self, win, app):
        super().__init__()
        self.win = win
        self.uid = app.uid
        self.add_css_class("app-card")
        self.set_tooltip_text(app.name)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        top = Gtk.Box(spacing=8)
        top.append(app_icon(app, 48))
        sp = Gtk.Box(hexpand=True)
        top.append(sp)
        b = source_badge(app, small=True)
        b.set_valign(Gtk.Align.START)
        top.append(b)
        box.append(top)
        name = label(app.name, "card-name", ellipsize=True)
        name.set_max_width_chars(18)
        box.append(name)
        summ = label(app.summary, "card-summary", wrap=True, ellipsize=True, lines=2)
        summ.set_width_chars(18)
        summ.set_max_width_chars(24)
        summ.set_valign(Gtk.Align.START)
        summ.set_vexpand(True)
        box.append(summ)
        self.state = Gtk.Box(spacing=6)
        self.state.add_css_class("card-state")
        box.append(self.state)
        self.set_child(box)
        self.connect("clicked", lambda *_: win.show_app(self.uid))
        self.sync(app)
        win.watch(app.uid, self)

    def sync(self, app):
        clear(self.state)
        if app.busy:
            bar = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
            bar.add_css_class("fluent-progress")
            bar.set_fraction(app.progress)
            self.state.append(bar)
            self._bar = bar
        elif app.has_update:
            self.state.append(icon("st-update-symbolic", 12, "accent-icon"))
            self.state.append(label(_("Update available"), "card-state-text"))
        elif app.installed:
            self.state.append(icon("st-check-symbolic", 12, "success-icon"))
            self.state.append(label(_("Installed"), "card-state-text"))
        else:
            cat = app.categories[0] if app.categories else ""
            from .model import CATEGORY_TITLES
            self.state.append(label(_(CATEGORY_TITLES.get(cat, "")), "card-state-text"))

    def progress(self, frac, _text):
        bar = getattr(self, "_bar", None)
        if bar is not None and frac >= 0:
            bar.set_fraction(frac)


# --------------------------------------------------------------------------- action area

class ActionArea(Gtk.Box):
    """Install / Open / Update buttons, replaced by a progress bar while an operation runs."""

    def __init__(self, win, app, show_open=True, small=False):
        super().__init__(spacing=8)
        self.win = win
        self.uid = app.uid
        self.show_open = show_open
        self.small = small
        self.add_css_class("action-area")
        self.set_valign(Gtk.Align.CENTER)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.stack.set_hhomogeneous(False)
        self.stack.set_interpolate_size(False)
        self.buttons = Gtk.Box(spacing=8)
        self.stack.add_named(self.buttons, "buttons")
        prog = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        prog.add_css_class("progress-box")
        self.status = label("", "progress-text", ellipsize=True)
        self.bar = Gtk.ProgressBar()
        self.bar.add_css_class("fluent-progress")
        self.bar.set_size_request(180 if small else 220, -1)
        prog.append(self.status)
        prog.append(self.bar)
        self.stack.add_named(prog, "progress")
        self.append(self.stack)
        self._pulse = 0
        self.sync(app)
        win.watch(app.uid, self)

    def _btn(self, text, accent, cb, icon_name=None):
        b = button(text, "fluent-button accent" if accent else "fluent-button", cb, icon_name)
        if self.small:
            b.add_css_class("small")
        self.buttons.append(b)
        return b

    def sync(self, app):
        clear(self.buttons)
        self.main = None
        if app.busy:
            self.stack.set_visible_child_name("progress")
            self._set_progress(app.progress if app.state != QUEUED else -1, status_text(app))
            return
        self._stop_pulse()
        self.stack.set_visible_child_name("buttons")
        st = self.win.store
        if app.state == AVAILABLE:
            self.main = self._btn(_("Install"), True, lambda: st.install(app.uid), "st-download-symbolic")
        elif app.state == INSTALLED:
            if app.has_update:
                self.main = self._btn(_("Update"), True, lambda: st.update(app.uid), "st-update-symbolic")
            if self.show_open:
                b = self._btn(_("Open"), not app.has_update, lambda: self.win.launch(app.uid))
                self.main = self.main or b

    def clicked(self):
        """Activate the main button (tests)."""
        if self.main is not None:
            self.main.emit("clicked")

    def progress(self, frac, text):
        self._set_progress(frac, _(text) if text else "")

    def _set_progress(self, frac, text):
        if text:
            pct = f" {int(frac * 100)}%" if frac is not None and frac > 0 else ""
            self.status.set_label(text + pct)
        if frac is None or frac < 0:
            if not self._pulse:
                self._pulse = GLib.timeout_add(120, lambda: (self.bar.pulse(), True)[1])
        else:
            self._stop_pulse()
            self.bar.set_fraction(frac)

    def _stop_pulse(self):
        if self._pulse:
            GLib.source_remove(self._pulse)
            self._pulse = 0


# --------------------------------------------------------------------------- banner

class Banner(Gtk.Box):
    """Featured banner: rotating highlighted apps on a generated background."""
    ROTATE_MS = 7000

    def __init__(self, win, apps, rotate=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.win = win
        self.apps = apps
        self.index = 0
        self.add_css_class("banner-wrap")
        self.overlay = Gtk.Overlay()
        self.area = Gtk.DrawingArea()
        self.area.set_content_height(260)
        self.area.set_hexpand(True)
        self.area.set_draw_func(self._draw)
        self.area.add_css_class("banner")
        self.overlay.set_child(self.area)
        self.content = Gtk.Box(spacing=24)
        self.content.add_css_class("banner-content")
        self.overlay.add_overlay(self.content)
        self.append(self.overlay)
        nav = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.prev_btn = button("", "round-button", self.prev, "st-chevron-left-symbolic", _("Previous"))
        self.dots = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self.next_btn = button("", "round-button", self.next, "st-chevron-right-symbolic", _("Next"))
        nav.append(self.prev_btn)
        nav.append(self.dots)
        nav.append(self.next_btn)
        self.append(nav)
        self._timer = 0
        self._hover = False
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: setattr(self, "_hover", True))
        motion.connect("leave", lambda *_: setattr(self, "_hover", False))
        self.overlay.add_controller(motion)
        self.show_index(0)
        if rotate and len(apps) > 1:
            self._timer = GLib.timeout_add(self.ROTATE_MS, self._tick)
            self.connect("unrealize", lambda *_: self.stop())

    def stop(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _tick(self):
        if not self._hover and self.get_mapped():
            self.next()
        return True

    def next(self):
        if self.apps:
            self.show_index((self.index + 1) % len(self.apps))

    def prev(self):
        if self.apps:
            self.show_index((self.index - 1) % len(self.apps))

    def _draw(self, _a, cr, w, h):
        if not self.apps:
            return
        hue, name = art.art_for(self.apps[self.index])
        art.draw_banner(cr, w, h, hue, name)

    def show_index(self, i):
        self.index = i
        clear(self.content)
        clear(self.dots)
        if not self.apps:
            return
        app = self.apps[i]
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True, valign=Gtk.Align.CENTER)
        text.append(label(_("Featured"), "banner-kicker"))
        row = Gtk.Box(spacing=14)
        row.append(app_icon(app, 56))
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        names.append(label(app.name, "banner-title", ellipsize=True))
        names.append(label(app.developer, "banner-sub", ellipsize=True))
        row.append(names)
        text.append(row)
        text.append(label(app.summary, "banner-summary", wrap=True, lines=2, ellipsize=True))
        btns = Gtk.Box(spacing=8, margin_top=8)
        btns.append(ActionArea(self.win, app, show_open=True))
        btns.append(button(_("Details"), "fluent-button banner-ghost", lambda: self.win.show_app(app.uid)))
        text.append(btns)
        self.content.append(text)
        if app.screenshots:
            pic = screenshot_picture(app, app.screenshots[0], 480, 300)
            pic.set_size_request(320, 200)
            pic.set_can_shrink(True)
            pic.add_css_class("banner-shot")
            pic.set_valign(Gtk.Align.CENTER)
            frame = Gtk.Box(valign=Gtk.Align.CENTER)
            frame.add_css_class("banner-shot-frame")
            frame.append(pic)
            frame.set_overflow(Gtk.Overflow.HIDDEN)
            self.content.append(frame)
            self.shot_frame = frame
        for j in range(len(self.apps)):
            d = Gtk.Button()
            d.add_css_class("dot")
            if j == i:
                d.add_css_class("active")
            d.set_tooltip_text(self.apps[j].name)
            d.connect("clicked", lambda _b, j=j: self.show_index(j))
            self.dots.append(d)
        self.area.queue_draw()

    def set_narrow(self, narrow):
        frame = getattr(self, "shot_frame", None)
        if frame is not None:
            frame.set_visible(not narrow)


# --------------------------------------------------------------------------- carousel

class Carousel(Gtk.Box):
    """Screenshot carousel: one large picture, arrows, thumbnails strip and caption."""

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.app = app
        self.add_css_class("carousel")
        self.index = 0
        ov = Gtk.Overlay()
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=180)
        self.stack.add_css_class("carousel-stage")
        self.stack.set_size_request(-1, 340)
        self.pages = []
        for i, shot in enumerate(app.screenshots):
            pic = screenshot_picture(app, shot)
            pic.set_can_shrink(True)
            self.stack.add_named(pic, str(i))
            self.pages.append(pic)
        ov.set_child(self.stack)
        self.prev_btn = button("", "round-button overlay-arrow", self.prev, "st-chevron-left-symbolic", _("Previous"))
        self.prev_btn.set_halign(Gtk.Align.START)
        self.prev_btn.set_valign(Gtk.Align.CENTER)
        self.next_btn = button("", "round-button overlay-arrow", self.next, "st-chevron-right-symbolic", _("Next"))
        self.next_btn.set_halign(Gtk.Align.END)
        self.next_btn.set_valign(Gtk.Align.CENTER)
        if len(app.screenshots) > 1:
            ov.add_overlay(self.prev_btn)
            ov.add_overlay(self.next_btn)
        self.append(ov)
        self.caption = label("", "caption", xalign=0.5)
        self.append(self.caption)
        self.thumbs = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        if len(app.screenshots) > 1:
            for i, shot in enumerate(app.screenshots):
                b = Gtk.Button()
                b.add_css_class("thumb-button")
                p = screenshot_picture(app, shot, 240, 150)
                p.set_size_request(96, 60)
                p.set_can_shrink(True)
                b.set_child(p)
                b.connect("clicked", lambda _b, i=i: self.show(i))
                self.thumbs.append(b)
            self.append(self.thumbs)
        self.show(0)

    def show(self, i):
        if not self.pages:
            return
        self.index = i % len(self.pages)
        self.stack.set_visible_child_name(str(self.index))
        self.caption.set_label(self.app.screenshots[self.index].caption or "")
        self.caption.set_visible(bool(self.app.screenshots[self.index].caption))
        j = 0
        c = self.thumbs.get_first_child()
        while c is not None:
            (c.add_css_class if j == self.index else c.remove_css_class)("selected")
            c = c.get_next_sibling()
            j += 1

    def next(self):
        self.show(self.index + 1)

    def prev(self):
        self.show(self.index - 1)


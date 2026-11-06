"""Main window: custom title bar, navigation pane, animated content area, dialogs."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from . import util
from .i18n import _
from .nav import NavPane
from .pages.base import PAGES
from .widgets import Clamp, icon, label

ANIM_MS = 260
COMPACT_WIDTH = 900


def _ease_out(t):
    return 1 - (1 - t) ** 3


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app, start_page="home", animate=True):
        super().__init__(application=app)
        self.set_title(_("Settings"))
        self.set_icon_name("fenestra-settings")
        self.set_default_size(1100, 720)
        self.set_size_request(680, 480)
        self.add_css_class("fenestra-settings")
        self.animate = animate
        self.pages = {}
        self.history: list[tuple[str, str | None]] = []
        self.current = None
        self._anim_id = 0
        self._compact = None

        # ------------------------------------------------------------- titlebar
        # back | title ........ [ search box, centred ] ........ caption buttons
        tb = Gtk.WindowHandle()
        tcenter = Gtk.CenterBox()
        tcenter.add_css_class("titlebar-box")
        tbox = Gtk.Box(spacing=0)
        tbox.add_css_class("titlebar-start")
        self.back_btn = Gtk.Button()
        self.back_btn.set_child(icon("fs-arrow-left-symbolic", 16))
        self.back_btn.add_css_class("back-button")
        self.back_btn.set_tooltip_text(_("Back"))
        self.back_btn.connect("clicked", lambda *_: self.go_back())
        self.back_btn.set_sensitive(False)
        tbox.append(self.back_btn)
        self.menu_btn = Gtk.Button()
        self.menu_btn.set_child(icon("fs-navigation-symbolic", 16))
        self.menu_btn.add_css_class("back-button")
        self.menu_btn.set_visible(False)
        self.menu_btn.connect("clicked", lambda *_: self._toggle_flyout())
        tbox.append(self.menu_btn)
        tbox.append(label(_("Settings"), "title-label"))
        if util.READ_ONLY and not getattr(app, "screenshot", None):
            tbox.append(label(_("(read-only)"), "title-label"))
        tcenter.set_start_widget(tbox)
        self.search_slot = Gtk.Box()
        self.search_slot.add_css_class("title-search")
        self.search_slot.set_valign(Gtk.Align.START)
        tcenter.set_center_widget(self.search_slot)
        controls = Gtk.WindowControls(side=Gtk.PackType.END)
        controls.add_css_class("window-controls")
        controls.set_valign(Gtk.Align.START)
        tcenter.set_end_widget(controls)
        tb.set_child(tcenter)
        self.set_titlebar(tb)

        # ------------------------------------------------------------- body
        self.overlay = Gtk.Overlay()
        self.set_child(self.overlay)
        body = Gtk.Box()
        body.add_css_class("window-body")
        self.overlay.set_child(body)

        self.nav = NavPane(self)
        self.search_slot.append(self.nav.search_wrap)
        self.nav.set_size_request(300, -1)
        self.nav.set_hexpand(False)
        body.append(self.nav)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        content.add_css_class("content-area")
        self.header = Gtk.Box(spacing=0)
        self.header.add_css_class("page-header")
        content.append(self.header)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.set_vexpand(True)
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        content.append(self.stack)
        body.append(content)
        self.content = content

        # smoke layer for dialogs
        self.smoke = Gtk.Box()
        self.smoke.add_css_class("smoke")
        self.smoke.set_visible(False)
        self.smoke.set_can_target(True)
        self.overlay.add_overlay(self.smoke)
        self.dialog_holder = None

        self.toast_box = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.CROSSFADE)
        self.toast_box.set_halign(Gtk.Align.CENTER)
        self.toast_box.set_valign(Gtk.Align.END)
        self.toast_lbl = label("", "toast")
        self.toast_box.set_child(self.toast_lbl)
        self.toast_box.set_can_target(False)
        self.overlay.add_overlay(self.toast_box)
        self._toast_timer = 0

        self.connect("notify::default-width", lambda *_: self._check_compact())
        self.connect("notify::maximized", lambda *_: GLib.idle_add(self._check_compact))
        self.navigate(start_page, record=False)
        self.connect("map", lambda *_: GLib.idle_add(lambda: (self.set_focus(None), False)[1]))

    # ----------------------------------------------------------------- layout
    def do_size_allocate(self, w, h, b):
        Gtk.ApplicationWindow.do_size_allocate(self, w, h, b)
        if self._compact is None or (w < COMPACT_WIDTH) != self._compact:
            GLib.idle_add(self._apply_compact, w < COMPACT_WIDTH)

    def _check_compact(self):
        w = self.get_width() or self.get_default_size()[0]
        self._apply_compact(w < COMPACT_WIDTH)
        return False

    def _apply_compact(self, compact):
        if compact == self._compact:
            return False
        self._compact = compact
        self.nav.set_compact(compact)
        self.nav.set_size_request(64 if compact else 300, -1)
        return False

    def _toggle_flyout(self):
        self._apply_compact(not self._compact)

    # ----------------------------------------------------------------- navigation
    def get_page(self, pid):
        if pid not in self.pages:
            cls = PAGES.get(pid)
            if cls is None:
                return None
            page = cls(self)
            self.pages[pid] = page
            w = page.get_widget()
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroller.set_overlay_scrolling(True)
            scroller.add_css_class("page-scroll")
            clamp = Clamp(w, 1000)
            clamp.add_css_class("page-clamp")
            scroller.set_child(clamp)
            page.scroller = scroller
            self.stack.add_named(scroller, pid)
        return self.pages[pid]

    def navigate(self, pid, key=None, record=True, from_nav=False):
        page = self.get_page(pid)
        if page is None:
            return
        if self.current == pid and key is None:
            return
        if record and self.current is not None:
            self.history.append((self.current, None))
        self.current = pid
        self.back_btn.set_sensitive(bool(self.history))
        self._build_header(page)
        self.nav.select(page.nav_root())
        page.scroller.get_vadjustment().set_value(0)
        self.stack.set_visible_child_name(pid)
        try:
            page.on_show()
        except Exception as e:  # noqa: BLE001 - never crash the UI from a page refresh
            util.log("on_show failed", pid, e)
        self._animate_in(page.scroller)
        if key:
            GLib.timeout_add(ANIM_MS if self.animate else 50, self._highlight, page, key)

    def go_back(self):
        if not self.history:
            return
        pid, _key = self.history.pop()
        self.navigate(pid, record=False)
        self.back_btn.set_sensitive(bool(self.history))

    def _highlight(self, page, key):
        row = page.find_row(key)
        if row is None:
            return False
        # Expand the containing expander if needed
        p = row.get_parent()
        while p is not None and p is not page.widget:
            if hasattr(p, "set_expanded") and hasattr(p, "revealer"):
                p.set_expanded(True)
            p = p.get_parent()
        ok, pt = row.compute_point(page.widget, _graphene_point(0, 0))
        if ok:
            adj = page.scroller.get_vadjustment()
            adj.set_value(max(0, pt.y - 80))
        if hasattr(row, "flash"):
            row.flash()
        else:
            row.add_css_class("highlight")
            GLib.timeout_add(1800, lambda: (row.remove_css_class("highlight"), False)[1])
        return False

    def _build_header(self, page):
        child = self.header.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.header.remove(child)
            child = nxt
        chain = []
        p = page
        while p is not None:
            chain.append(p)
            p = PAGES.get(p.parent) if p.parent else None
            if p is not None:
                p = self.get_page(p.id)
        chain.reverse()
        for i, pg in enumerate(chain):
            last = i == len(chain) - 1
            if last:
                lb = label(pg.tr_title(), "page-title", ellipsize=True)
                self.header.append(lb)
            else:
                b = Gtk.Button(label=pg.tr_title())
                b.add_css_class("crumb")
                b.connect("clicked", lambda _b, pid=pg.id: self.navigate(pid))
                self.header.append(b)
                self.header.append(icon("fs-chevron-right-symbolic", 20, "crumb-sep"))

    def _animate_in(self, w):
        if self._anim_id:
            try:
                self._anim_target.remove_tick_callback(self._anim_id)
            except Exception:  # noqa: BLE001
                pass
            self._anim_target.set_opacity(1)
            self._anim_target.set_margin_top(0)
            self._anim_id = 0
        if not self.animate or not Gtk.Settings.get_default().props.gtk_enable_animations:
            w.set_opacity(1)
            w.set_margin_top(0)
            return
        start = [None]
        w.set_opacity(0)
        w.set_margin_top(36)
        self._anim_target = w

        def tick(widget, clock):
            t_now = clock.get_frame_time()
            if start[0] is None:
                start[0] = t_now
            t = min(1.0, (t_now - start[0]) / 1000.0 / ANIM_MS)
            e = _ease_out(t)
            widget.set_opacity(min(1.0, t * 1.6))
            widget.set_margin_top(int(36 * (1 - e)))
            if t >= 1.0:
                self._anim_id = 0
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        self._anim_id = w.add_tick_callback(tick)

    # ----------------------------------------------------------------- dialogs / toasts
    def show_dialog(self, dlg):
        self.close_dialog(None)
        self.smoke.set_visible(True)
        self.dialog_holder = dlg
        self.overlay.add_overlay(dlg)
        dlg.grab_focus()

    def close_dialog(self, dlg):
        if self.dialog_holder is not None and (dlg is None or dlg is self.dialog_holder):
            self.overlay.remove_overlay(self.dialog_holder)
            self.dialog_holder = None
            self.smoke.set_visible(False)

    def toast(self, text, ms=3000):
        self.toast_lbl.set_label(text)
        self.toast_box.set_reveal_child(True)
        if self._toast_timer:
            GLib.source_remove(self._toast_timer)

        def hide():
            self._toast_timer = 0
            self.toast_box.set_reveal_child(False)
            return False
        self._toast_timer = GLib.timeout_add(ms, hide)


def _graphene_point(x, y):
    from gi.repository import Graphene
    p = Graphene.Point()
    p.x, p.y = x, y
    return p

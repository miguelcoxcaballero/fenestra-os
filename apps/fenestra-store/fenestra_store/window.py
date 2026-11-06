"""Main window: title bar with the search box, navigation rail, page stack, dialogs, toasts."""
from __future__ import annotations

import weakref

from gi.repository import Gdk, GLib, Gtk

from . import util
from .i18n import _
from .pages.base import Page
from .pages.browse import BrowsePage, SearchPage
from .pages.details import DetailsPage
from .pages.home import HomePage, ShowcasePage
from .pages.library import LibraryPage
from .pages.sources import SourcesPage
from .widgets import Clamp, button, icon, label

NAV = [("home", "st-home", "Home"), ("apps", "st-apps", "Apps"), ("games", "st-games", "Games")]
NAV_BOTTOM = [("sources", "st-sources", "Sources"), ("updates", "st-downloads", "Downloads"),
              ("library", "st-library", "Library")]
COMPACT_WIDTH = 900
NARROW_CONTENT = 760

OK_TEXT = {"install": "%s is installed", "remove": "%s was uninstalled", "update": "%s is up to date"}
FAIL_TEXT = {"install": "Could not install %s", "remove": "Could not uninstall %s", "update": "Could not update %s"}


class StoreWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store, start_page="home", start_arg=None):
        super().__init__(application=app)
        self.store = store
        self.set_title(_("Fenestra Store"))
        self.set_icon_name("org.fenestra.Store")
        self.set_default_size(1180, 760)
        self.set_size_request(560, 480)
        self.add_css_class("fenestra-store")
        self.pages: dict[str, Page] = {}
        self.history: list[tuple[str, object]] = []
        self.current = None
        self.current_arg = None
        self.dialog = None
        self.narrow = False
        self._compact = None
        self._watchers: dict[str, list] = {}
        self._search_timer = 0
        self._search_return = None
        self._start = (start_page, start_arg)

        # ------------------------------------------------------------- title bar
        # 48 px: [back] icon title | search box centred on the window | demo pill, caption buttons
        handle = Gtk.WindowHandle()
        tbox = Gtk.CenterBox()
        tbox.add_css_class("titlebar-box")
        self.titlebar_box = tbox
        start = Gtk.Box(spacing=0)
        self.back_btn = button("", "back-button", self.go_back, "st-back-symbolic", _("Back"))
        self.back_btn.set_valign(Gtk.Align.CENTER)
        self.back_btn.set_visible(False)
        start.append(self.back_btn)
        app_icon = icon("org.fenestra.Store", 16, "title-icon")
        app_icon.set_valign(Gtk.Align.CENTER)
        start.append(app_icon)
        title = label(_("Fenestra Store"), "title-label")
        title.set_valign(Gtk.Align.CENTER)
        start.append(title)
        tbox.set_start_widget(start)
        self.search = Gtk.Entry()
        self.search.set_placeholder_text(_("Search apps, games and more"))
        self.search.add_css_class("store-search")
        self.search.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "st-search-symbolic")
        self.search.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, True)
        self.search.connect("icon-press", lambda *_: self._run_search())
        self.search.set_valign(Gtk.Align.CENTER)
        self.search.set_hexpand(False)
        self.search.set_size_request(600, -1)
        self.search.connect("changed", self._on_search_changed)
        self.search.connect("activate", lambda *_: self._run_search())
        esc = Gtk.EventControllerKey()
        esc.connect("key-pressed", lambda _c, kv, *_: kv == Gdk.KEY_Escape and self.search.get_text() != ""
                    and (self.search.set_text(""), True)[1])
        self.search.add_controller(esc)
        tbox.set_center_widget(self.search)
        end = Gtk.Box(spacing=0)
        if util.DEMO:
            pill = label(_("Demo"), "demo-pill")
            pill.set_valign(Gtk.Align.CENTER)
            pill.set_tooltip_text(_("Sample catalogue: nothing on this computer is changed"))
            end.append(pill)
        # own caption buttons (46x32, 10 px glyphs) instead of Gtk.WindowControls, whose icon
        # theme glyphs cannot be resized from CSS
        controls = Gtk.Box()
        controls.add_css_class("window-controls")
        controls.set_valign(Gtk.Align.START)
        self.max_btn = None
        for css, glyph, tip, cb in (("minimize", "st-window-minimize-symbolic", _("Minimize"), self.minimize),
                                    ("maximize", "st-window-maximize-symbolic", _("Maximize"), self._toggle_max),
                                    ("close", "st-window-close-symbolic", _("Close"), self.close)):
            b = Gtk.Button()
            b.add_css_class("caption-button")
            b.add_css_class(css)
            b.set_child(icon(glyph, 10))
            b.set_tooltip_text(tip)
            b.set_focusable(False)
            b.connect("clicked", lambda _b, cb=cb: cb())
            controls.append(b)
            if css == "maximize":
                self.max_btn = b
        self.connect("notify::maximized", self._on_maximized)
        end.append(controls)
        tbox.set_end_widget(end)
        handle.set_child(tbox)
        self.set_titlebar(handle)

        # ------------------------------------------------------------- body
        self.overlay = Gtk.Overlay()
        self.set_child(self.overlay)
        body = Gtk.Box()
        body.add_css_class("window-body")
        self.overlay.set_child(body)

        # 72 px rail: 64x58 items 4 px apart, icon over a small label; the selected item shows
        # only its icon in the accent colour and an accent pill on its left edge
        self.nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.nav.add_css_class("nav-pane")
        self.nav_rows = {}
        top = Gtk.ListBox()
        top.add_css_class("nav-list")
        bottom = Gtk.ListBox()
        bottom.add_css_class("nav-list")
        for lst, items in ((top, NAV), (bottom, NAV_BOTTOM)):
            for pid, icon_name, title_text in items:
                lst.append(self._nav_row(pid, icon_name, _(title_text)))
            lst.connect("row-activated", lambda _l, row: self.navigate(row.page_id, row.page_arg))
        self.nav_lists = (top, bottom)
        self.nav.append(top)
        self.nav.append(Gtk.Box(vexpand=True))
        self.nav.append(bottom)
        body.append(self.nav)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        content.add_css_class("content-area")
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=140)
        self.stack.set_vexpand(True)
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        content.append(self.stack)
        body.append(content)

        loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER,
                          halign=Gtk.Align.CENTER)
        sp = Gtk.Spinner(spinning=True)
        sp.set_size_request(32, 32)
        sp.add_css_class("fluent-spinner")
        loading.append(sp)
        loading.append(label(_("Loading the catalogue…"), "caption", xalign=0.5))
        self.stack.add_named(loading, "loading")

        self.smoke = Gtk.Box()
        self.smoke.add_css_class("smoke")
        self.smoke.set_visible(False)
        self.overlay.add_overlay(self.smoke)
        self.toast_box = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.CROSSFADE)
        self.toast_box.set_halign(Gtk.Align.CENTER)
        self.toast_box.set_valign(Gtk.Align.END)
        self.toast_lbl = label("", "toast", wrap=True)
        self.toast_box.set_child(self.toast_lbl)
        self.toast_box.set_can_target(False)
        self.overlay.add_overlay(self.toast_box)
        self._toast_timer = 0

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        store.connect("loaded", self._on_loaded)
        store.connect("app-changed", self._on_app_changed)
        store.connect("progress", self._on_progress)
        store.connect("job-done", self._on_job_done)
        store.connect("updates-changed", self._on_updates_changed)
        if store.loaded:
            self._on_loaded(store)

    # ----------------------------------------------------------------- navigation rail
    def _nav_row(self, pid, icon_name, title):
        row = Gtk.ListBoxRow()
        row.page_id = pid
        row.page_arg = None
        row.add_css_class("nav-item")
        row.set_tooltip_text(title)
        ov = Gtk.Overlay()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.add_css_class("nav-item-box")
        img = icon(icon_name + "-symbolic", 20, "nav-icon")
        img.set_halign(Gtk.Align.CENTER)
        box.append(img)
        lb = label(title, "nav-label", xalign=0.5, ellipsize=True)
        lb.set_width_chars(1)
        lb.set_max_width_chars(1)
        box.append(lb)
        ov.set_child(box)
        badge = label("", "nav-badge", xalign=0.5)
        badge.set_halign(Gtk.Align.END)
        badge.set_valign(Gtk.Align.START)
        badge.set_visible(False)
        ov.add_overlay(badge)
        pill = Gtk.Box()
        pill.add_css_class("nav-pill")
        pill.set_halign(Gtk.Align.START)
        pill.set_valign(Gtk.Align.START)
        ov.add_overlay(pill)
        row.set_child(ov)
        row.nav_label = lb
        row.nav_icon = img
        row.icon_base = icon_name
        row.nav_box = box
        row.badge = badge
        self.nav_rows[pid] = row
        return row

    def _select_nav(self, nav_id):
        self._nav_sel = nav_id
        for lst in self.nav_lists:
            lst.unselect_all()
        for pid, row in self.nav_rows.items():
            sel = pid == nav_id
            row.nav_label.set_visible(not sel)
            row.nav_icon.set_from_icon_name(row.icon_base + ("-filled-symbolic" if sel else "-symbolic"))
            (row.nav_box.add_css_class if sel else row.nav_box.remove_css_class)("selected")
        row = self.nav_rows.get(nav_id)
        if row is not None:
            row.get_parent().select_row(row)

    def set_compact(self, compact):
        if compact == self._compact:
            return
        self._compact = compact
        self._update_badge()

    # ----------------------------------------------------------------- layout
    @staticmethod
    def layout_for(w):
        compact = w < COMPACT_WIDTH
        return compact, w - 72 < NARROW_CONTENT

    def preset_width(self, w):
        """Apply the layout for a known width before the first frame (no relayout flash)."""
        self._apply_layout(*self.layout_for(w))

    def do_size_allocate(self, w, h, b):
        Gtk.ApplicationWindow.do_size_allocate(self, w, h, b)
        compact, narrow = self.layout_for(w)
        if compact != self._compact or narrow != self.narrow:
            GLib.idle_add(self._apply_layout, compact, narrow)

    def _apply_layout(self, compact, narrow):
        self.set_compact(compact)
        self.search.set_size_request(260 if compact else 600, -1)
        if narrow != self.narrow:
            self.narrow = narrow
            for p in self.pages.values():
                p.set_narrow(narrow)
        return False

    # ----------------------------------------------------------------- pages
    def _make_page(self, pid) -> Page | None:
        if pid == "home":
            return HomePage(self)
        if pid in ("apps", "games"):
            return ShowcasePage(self, pid)
        if pid == "category":
            return BrowsePage(self, pid)
        if pid == "search":
            return SearchPage(self)
        if pid == "details":
            return DetailsPage(self)
        if pid == "library":
            return LibraryPage(self)
        if pid == "sources":
            return SourcesPage(self)
        return None

    def get_page(self, pid) -> Page | None:
        if pid not in self.pages:
            page = self._make_page(pid)
            if page is None:
                return None
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroller.add_css_class("page-scroll")
            scroller.set_child(Clamp(page.box, page.max_width))
            page.scroller = scroller
            self.pages[pid] = page
            self.stack.add_named(scroller, pid)
            page.set_narrow(self.narrow)
        return self.pages[pid]

    def navigate(self, pid, arg=None, record=True):
        if pid == "updates":
            pid, arg = "library", "updates"
        elif pid == "library" and arg is None:
            arg = "installed"
        if not self.store.loaded:
            self._start = (pid, arg)
            return
        page = self.get_page(pid)
        if page is None:
            util.log("unknown page", pid)
            return
        if self.current == pid and arg == self.current_arg and not page.dirty and pid != "details":
            return
        if record and self.current is not None and self.current != "search":
            self.history.append((self.current, self.current_arg))
            del self.history[:-50]
        if pid != "search" and self.search.get_text():
            self._search_return = None
            self.search.set_text("")
            self._cancel_search_timer()
        self.current, self.current_arg = pid, arg
        self._sync_back()
        page.show(arg)
        nav = page.nav_for(arg) if hasattr(page, "nav_for") else page.nav
        if nav is not None:  # app pages and search results keep the rail selection
            self._select_nav(nav)
        elif getattr(self, "_nav_sel", None) is None:
            self._select_nav("home")
        page.scroller.get_vadjustment().set_value(0)
        self.stack.set_visible_child_name(pid)

    def _toggle_max(self):
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    def _on_maximized(self, *_):
        m = self.is_maximized()
        self.max_btn.get_child().set_from_icon_name("st-window-restore-symbolic" if m else "st-window-maximize-symbolic")
        self.max_btn.set_tooltip_text(_("Restore") if m else _("Maximize"))

    def _sync_back(self):
        has = bool(self.history)
        self.back_btn.set_visible(has)
        (self.titlebar_box.add_css_class if has else self.titlebar_box.remove_css_class)("has-back")

    def show_app(self, uid, record=True):
        self.navigate("details", uid, record)

    def go_back(self):
        if not self.history:
            return
        pid, arg = self.history.pop()
        self.navigate(pid, arg, record=False)
        self._sync_back()

    def catalogue_changed(self):
        """Sources changed: rebuild every page next time it is shown, refresh the current one."""
        for p in self.pages.values():
            p.dirty = True
        if self.current:
            cur, arg = self.current, self.current_arg
            self.current = None
            self.navigate(cur, arg, record=False)

    # ----------------------------------------------------------------- search
    def _on_search_changed(self, entry):
        self._cancel_search_timer()
        self._search_timer = GLib.timeout_add(150, self._run_search)

    def _cancel_search_timer(self):
        if self._search_timer:
            GLib.source_remove(self._search_timer)
            self._search_timer = 0

    def _run_search(self):
        self._search_timer = 0
        text = self.search.get_text().strip()
        if not self.store.loaded:
            return False
        if text:
            if self.current != "search":
                self._search_return = (self.current, self.current_arg)
            page = self.get_page("search")
            page.dirty = True
            self.navigate("search", text, record=False)
        elif self.current == "search":
            pid, arg = self._search_return or ("home", None)
            self._search_return = None
            self.navigate(pid, arg, record=False)
        return False

    def search_for(self, text):
        self.search.set_text(text)
        self._cancel_search_timer()
        self._run_search()

    def _on_key(self, _c, keyval, _code, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        alt = state & Gdk.ModifierType.ALT_MASK
        if ctrl and keyval in (Gdk.KEY_f, Gdk.KEY_k):
            self.search.grab_focus()
            return True
        if alt and keyval == Gdk.KEY_Left:
            self.go_back()
            return True
        if keyval == Gdk.KEY_Escape and self.dialog is not None:
            self.close_dialog()
            return True
        return False

    # ----------------------------------------------------------------- store events
    def watch(self, uid, widget):
        """widget.sync(app) on state changes, widget.progress(frac, text) while an operation runs."""
        lst = self._watchers.setdefault(uid, [])
        lst[:] = [r for r in lst if r() is not None]
        lst.append(weakref.ref(widget))

    def _live(self, uid):
        out = []
        for r in self._watchers.get(uid, []):
            w = r()
            if w is not None:
                out.append(w)
        return out

    def open_target(self, pid, arg, record=True):
        """Open a page from the command line: page id + argument, or ("app", id/package/name)."""
        if not self.store.loaded:
            self._start = (pid, arg)
            return
        if pid == "app":
            st = self.store
            app = st.get(arg) or next((a for a in st.catalogue() if arg in (a.app_id, a.pkgname, a.name)), None)
            if app is not None:
                self.navigate("details", app.uid, record)
                return
            self.toast(_("No app called “%s” was found") % arg)
            pid, arg = "home", None
        self.navigate(pid or "home", arg, record)

    def _on_loaded(self, store):
        for p in self.pages.values():
            p.dirty = True
        self._update_badge()
        pid, arg = self._start
        self._start = ("home", None)
        self.current = None
        self.open_target(pid, arg, record=False)
        if self.search.get_text():
            self._run_search()

    def _on_app_changed(self, store, uid):
        app = store.get(uid)
        for w in self._live(uid):
            w.sync(app)

    def _on_progress(self, store, uid, frac, text):
        for w in self._live(uid):
            w.progress(frac, text)

    def _on_updates_changed(self, store):
        self._update_badge()
        lib = self.pages.get("library")
        if lib is not None:
            if self.current == "library":
                lib.on_updates_changed()
            else:
                lib.dirty = True

    def _update_badge(self):
        row = self.nav_rows.get("updates")
        if row is None:
            return
        n = len(self.store.updates()) if self.store.loaded else 0
        row.badge.set_label("")
        row.badge.set_visible(n > 0)
        row.set_tooltip_text(_("Downloads") + (f" ({_('%d updates') % n})" if n else ""))

    def _on_job_done(self, store, uid, op, ok, msg):
        app = store.get(uid)
        name = app.name if app else uid
        if ok:
            self.toast(_(OK_TEXT[op]) % name)
        else:
            self.toast((_(FAIL_TEXT[op]) % name) + (": " + self.explain(msg) if msg else ""), 6000)

    def explain(self, msg):
        if msg == "read-only":
            return _("read-only mode, nothing was changed")
        if msg == "source-disabled":
            return _("its source is turned off")
        return msg

    # ----------------------------------------------------------------- actions
    def launch(self, uid):
        app = self.store.get(uid)
        if app is None:
            return
        if util.DEMO:
            self.toast(_("%s would open now (demo mode)") % app.name)
            return
        if not self.store.launch(uid):
            self.toast(_("Could not open %s") % app.name)

    def confirm_remove(self, uid):
        app = self.store.get(uid)
        if app is None:
            return
        extra = _("Your files and settings for it are kept in your home folder.")
        self.show_dialog(_("Uninstall %s?") % app.name, extra, _("Uninstall"), lambda: self.store.remove(uid))

    # ----------------------------------------------------------------- dialogs / toasts
    def show_dialog(self, title, text, ok_label, on_ok):
        self.close_dialog()
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("content-dialog")
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.CENTER)
        card.set_size_request(420, -1)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.add_css_class("dialog-body")
        body.append(label(title, "dialog-title", wrap=True))
        body.append(label(text, "dialog-text", wrap=True))
        card.append(body)
        foot = Gtk.Box(spacing=8, homogeneous=True)
        foot.add_css_class("dialog-footer")

        def ok():
            self.close_dialog()
            on_ok()
        okb = button(ok_label, "fluent-button accent", ok)
        foot.append(okb)
        foot.append(button(_("Cancel"), "fluent-button", self.close_dialog))
        card.append(foot)
        card.confirm = ok
        self.smoke.set_visible(True)
        self.overlay.add_overlay(card)
        self.dialog = card
        okb.grab_focus()

    def close_dialog(self):
        if self.dialog is not None:
            self.overlay.remove_overlay(self.dialog)
            self.dialog = None
            self.smoke.set_visible(False)

    def toast(self, text, ms=3500):
        self.toast_lbl.set_label(text)
        self.toast_box.set_reveal_child(True)
        if self._toast_timer:
            GLib.source_remove(self._toast_timer)

        def hide():
            self._toast_timer = 0
            self.toast_box.set_reveal_child(False)
            return False
        self._toast_timer = GLib.timeout_add(ms, hide)

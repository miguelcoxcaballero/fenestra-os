"""Main OOBE window: background, card, page flow, footer and shortcuts."""

import logging

from gi.repository import Gdk, GLib, Graphene, Gtk

from .backends import accounts as acc
from .backends import locale as loc
from .backends import run_async
from .i18n import _
from .pages.account import (AccountNamePage, ApplyingPage, ConfirmPasswordPage, DeviceNamePage,
                            HintPage, PasswordPage)
from .pages.network import NetworkPage, OfflinePage, UpdatesPage
from .pages.personal import CustomizePage, ImportPage, PrivacyPage
from .pages.region import KeyboardPage, PickSecondKeyboardPage, RegionPage, SecondKeyboardPage
from .widgets.background import GradientBackground
from .widgets.corner import CornerControls
from .widgets.finale import FinaleView
from .widgets.illustration import Illustration, SvgIcon
from .widgets.layout import CardFrame, PageHost

log = logging.getLogger("fenestra-oobe")

PAGE_CLASSES = {cls.page_id: cls for cls in (
    RegionPage, KeyboardPage, SecondKeyboardPage, PickSecondKeyboardPage, NetworkPage, OfflinePage,
    UpdatesPage, DeviceNamePage, AccountNamePage, PasswordPage, ConfirmPasswordPage, HintPage,
    ApplyingPage, PrivacyPage, CustomizePage, ImportPage,
)}

SYSTEM_PAGES = ["region", "keyboard", "keyboard-second", "keyboard-pick", "network", "network-offline",
                "updates", "device-name", "account-name", "account-password", "account-confirm",
                "account-hint", "applying"]
EXISTING_PAGES = ["privacy", "customize", "import"]
FINALE_IDS = ["finale-1", "finale-2", "finale-3", "finale-4"]
ALL_PAGE_IDS = SYSTEM_PAGES + EXISTING_PAGES + FINALE_IDS


class OobeWindow(Gtk.ApplicationWindow):
    def __init__(self, app, mode: str, state, backends, screenshot: bool = False):
        super().__init__(application=app, title=_("Fenestra Setup"), css_classes=["oobe-window"])
        self.mode = mode  # "system", "existing" or "demo"
        self.state = state
        self.backends = backends
        self.screenshot_mode = screenshot
        self.order = {"system": SYSTEM_PAGES, "existing": EXISTING_PAGES,
                      "demo": SYSTEM_PAGES + EXISTING_PAGES}[mode]
        self.pages = {}
        self.history = []
        self.current_page = None
        self.finished = False

        # Shared data used by several pages.
        self.initial_timezone = state.timezone
        self.locales = loc.available_locales()
        self.layouts = loc.load_layouts(state.ui_lang)
        self.keyboard_suggestion = state.layouts[0]
        self.other_system_root = None
        self._taken_cache = {}

        self._build()
        self._setup_shortcuts()

        if mode == "system":
            backends.gdm.prepare()
        if screenshot:
            self.other_system_root = "/run/media/alex/OS"
        elif mode in ("existing", "demo"):
            run_async(backends.privacy.find_other_system, callback=self._other_system_found)

    # -- construction ----------------------------------------------------
    def _build(self):
        self.root = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=700)
        self.set_child(self.root)

        setup = Gtk.Overlay()
        setup.set_child(GradientBackground("light", animate=not self.screenshot_mode, speed=0.6))

        # One translucent card; illustration centred in the left half,
        # question/content in the right half (reference: 1200x760 @1080p).
        card = Gtk.Overlay(css_classes=["oobe-card"], overflow=Gtk.Overflow.HIDDEN)
        halves = Gtk.Box(homogeneous=True)
        self.art_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                                   transition_duration=320, css_classes=["art-pane"])
        halves.append(self.art_stack)

        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["content-column"])
        self.host = PageHost()
        column.append(self.host)
        footer = Gtk.Box(css_classes=["footer"], spacing=0)
        self.link_button = Gtk.Button(css_classes=["plain-link"], halign=Gtk.Align.START,
                                      valign=Gtk.Align.CENTER)
        self.link_button.connect("clicked", lambda *_: self.current_page and self.current_page.on_link())
        footer.append(self.link_button)
        footer.append(Gtk.Box(hexpand=True))
        self.secondary_button = Gtk.Button(css_classes=["plain-link", "secondary"],
                                           valign=Gtk.Align.CENTER)
        self.secondary_button.connect("clicked", lambda *_: self._secondary())
        footer.append(self.secondary_button)
        self.primary_button = Gtk.Button(css_classes=["oobe-button", "primary"], valign=Gtk.Align.CENTER)
        self.primary_button.connect("clicked", lambda *_: self._primary())
        footer.append(self.primary_button)
        self.footer = footer
        column.append(footer)
        halves.append(column)
        card.set_child(halves)

        self.back_button = Gtk.Button(css_classes=["back-button"], halign=Gtk.Align.START,
                                      valign=Gtk.Align.START, tooltip_text=_("Back"))
        self.back_button.set_child(SvgIcon("back", 16))
        self.back_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Back")])
        self.back_button.connect("clicked", lambda *_: self.back())
        card.add_overlay(self.back_button)
        self.card = card
        self.corner = CornerControls(self, self.backends.system)
        self.card_frame = CardFrame(card, self.corner)
        setup.add_overlay(self.card_frame)
        self.root.add_named(setup, "setup")

        self.finale = FinaleView()
        self.root.add_named(self.finale, "finale")

    def _setup_shortcuts(self):
        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    def _focus_in_wifi_row(self):
        w = self.get_focus()
        while w is not None:
            if w.has_css_class("wifi-row") or isinstance(w, Gtk.Popover):
                return True
            w = w.get_parent()
        return False

    def _on_key(self, _ctl, keyval, _code, mods):
        if self.root.get_visible_child_name() != "setup":
            return False
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter):
            if self._focus_in_wifi_row():
                return False
            if self.primary_button.get_visible() and self.primary_button.get_sensitive():
                self._primary()
                return True
            return False
        if keyval == Gdk.KEY_Escape:
            if self.back_button.get_sensitive():
                self.back()
                return True
            return False
        if keyval in (Gdk.KEY_q, Gdk.KEY_Q) and mods & Gdk.ModifierType.CONTROL_MASK and self.mode == "demo":
            self.get_application().quit()
            return True
        return False

    # -- flow ------------------------------------------------------------
    def username_taken(self, name):
        if self.mode == "demo":
            return name in ("root", "admin", "demo") or acc.system_name_taken(name)
        if name not in self._taken_cache:
            self._taken_cache[name] = acc.system_name_taken(name)
        return self._taken_cache[name]

    def page(self, page_id):
        if page_id not in self.pages:
            self.pages[page_id] = PAGE_CLASSES[page_id](self)
        return self.pages[page_id]

    def _art(self, name):
        if self.art_stack.get_child_by_name(name) is None:
            self.art_stack.add_named(Illustration(name), name)
        return name

    def start(self, page_id=None):
        if page_id is None:
            page_id = self._next_id(-1)
            if page_id is None:
                self.finish()
                return
        self.goto(page_id, record=False, direction=1, animate=False)
        if self.screenshot_mode:
            # Show the back arrow where it would normally be available.
            idx = self.order.index(page_id) if page_id in self.order else 0
            if idx > 0:
                self.history = [self.order[idx - 1]]
                self.update_footer(self.current_page)

    def _next_id(self, index):
        i = index + 1
        while i < len(self.order):
            pid = self.order[i]
            if PAGE_CLASSES[pid].branch:
                i += 1
                continue
            if not self.screenshot_mode and self.page(pid).should_skip():
                i += 1
                continue
            return pid
        return None

    def goto(self, page_id, record=True, direction=1, animate=True):
        if page_id.startswith("finale"):
            self.show_finale(page_id)
            return
        page = self.page(page_id)
        prev = self.current_page
        if prev is not None:
            prev.on_leave()
            if record and not prev.transient:
                self.history.append(prev.page_id)
        self.current_page = page
        self.art_stack.set_visible_child_name(self._art(page.illustration))
        self.host.set_page(page, direction, animate=animate and not self.screenshot_mode)
        page.on_enter(direction)
        self.update_footer(page)
        focus = page.focus_widget()
        if focus is not None:
            GLib.idle_add(lambda: (focus.grab_focus(), False)[1])
        else:
            GLib.idle_add(lambda: (self.primary_button.grab_focus(), False)[1])

    def next(self):
        cur = self.current_page
        idx = self.order.index(cur.page_id) if cur is not None else -1
        nid = self._next_id(idx)
        if nid is None:
            if self.mode == "system":
                return
            self.finish()
            return
        self.goto(nid)

    def back(self):
        page = self.current_page
        if page is None or not page.can_go_back or not self.history or page.busy:
            return
        prev = self.history.pop()
        self.goto(prev, record=False, direction=-1)

    def update_footer(self, page):
        if page is not self.current_page:
            return
        for button, label in ((self.primary_button, page.primary_label),
                              (self.secondary_button, page.secondary_label),
                              (self.link_button, page.link_label)):
            button.set_visible(bool(label))
            if label:
                button.set_label(label)
        self.footer.set_visible(any((page.primary_label, page.secondary_label, page.link_label)))
        self.primary_button.set_sensitive(page.primary_sensitive and not page.busy)
        self.secondary_button.set_sensitive(not page.busy)
        self.link_button.set_sensitive(not page.busy)
        can_back = page.can_go_back and bool(self.history) and not page.busy
        self.back_button.set_sensitive(can_back)
        self.back_button.set_opacity(1.0 if can_back else 0.0)
        self.back_button.set_can_target(can_back)

    def _primary(self):
        page = self.current_page
        if page is not None and not page.busy and page.primary_label and page.primary_sensitive:
            page.on_primary()

    def _secondary(self):
        page = self.current_page
        if page is not None and not page.busy:
            page.on_secondary()

    # -- system integration ----------------------------------------------
    def set_session_keyboard(self, layouts):
        if self.mode == "system":
            try:
                self.backends.system.set_session_input_sources(layouts)
            except Exception as exc:  # noqa: BLE001
                log.warning("could not switch session keyboard: %s", exc)

    def account_created(self):
        st = self.state
        handoff = {"country": st.country, "formats": st.formats, "timezone": st.timezone,
                   "layouts": [list(l) for l in st.layouts], "username": st.username}
        if self.mode == "demo":
            st.forget_secrets()
            GLib.timeout_add(1200, lambda: (self.next(), False)[1])
            return
        self.backends.system.write_handoff(handoff)
        if st.uid is not None:
            self.backends.gdm.write_uid_file(st.uid)
        started = self.backends.gdm.login(st.username, st.password, on_failed=self._login_failed)
        st.forget_secrets()
        if not started:
            self._login_failed("no GDM connection")

    def _login_failed(self, reason):
        log.warning("falling back to the login screen (%s)", reason)
        GLib.timeout_add(800, lambda: (self.get_application().quit(), False)[1])

    def _other_system_found(self, root, _error):
        self.other_system_root = root

    # -- finale ----------------------------------------------------------
    def show_finale(self, page_id="finale-1"):
        self.root.set_visible_child_name("finale")
        self.finale.show_step(FINALE_IDS.index(page_id) if page_id in FINALE_IDS else 0)

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.root.set_visible_child_name("finale")
        if self.mode in ("existing", "demo"):
            run_async(self._apply_user_region)
        self.finale.play(self._finale_done)

    def _apply_user_region(self):
        data = self.backends.system.read_handoff()
        formats = data.get("formats") or self.backends.accounts.user_formats_locale(
            GLib.get_user_name())
        layouts = [tuple(l) for l in data.get("layouts", [])]
        if self.mode == "demo":
            formats, layouts = self.state.formats, self.state.layouts
        self.backends.system.apply_user_region(formats, layouts)

    def _finale_done(self):
        try:
            self.backends.system.mark_done()
        except OSError as exc:
            log.warning("could not mark setup as done: %s", exc)
        self.get_application().quit()

    # -- screenshots -----------------------------------------------------
    def capture(self, path: str) -> tuple[int, int]:
        child = self.get_child()
        w, h = child.get_width(), child.get_height()
        paintable = Gtk.WidgetPaintable.new(child)
        snap = Gtk.Snapshot()
        paintable.snapshot(snap, w, h)
        node = snap.to_node()
        renderer = self.get_renderer()
        texture = renderer.render_texture(node, Graphene.Rect().init(0, 0, w, h))
        # Download explicitly: some GPU drivers hand out tiled/compressed
        # textures that save_to_png() would read back incorrectly.
        downloader = Gdk.TextureDownloader.new(texture)
        downloader.set_format(Gdk.MemoryFormat.R8G8B8A8)
        data, stride = downloader.download_bytes()
        Gdk.MemoryTexture.new(texture.get_width(), texture.get_height(), Gdk.MemoryFormat.R8G8B8A8,
                              data, stride).save_to_png(path)
        return w, h

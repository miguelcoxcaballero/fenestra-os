"""Native Nautilus tab icons and context-menu images; no file actions replaced."""
import gi
import os

gi.require_version('Nautilus', '4.1')
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Nautilus
from fenestra_views import FenestraViews
from fenestra_sidebar import tr, GALLERY


def walk(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


# Icons for menu items that come without one (extension items, generated "Open With <app>").
LABEL_ICONS = {'Copy as path': 'win11-menu-copypath', 'Copiar como ruta de acceso': 'win11-menu-copypath',
               'Open': 'win11-menu-openfile', 'Abrir': 'win11-menu-openfile'}


def decorate_menu(widget):
    for button in walk(widget):
        if GObject.type_name(button.__gtype__) != 'GtkModelButton':
            continue
        if button.get_property('iconic'):
            continue
        text = (button.get_property('text') or '').replace('_', '')
        accel = button.get_property('accel') or ''
        # Nautilus' default-application item ("Open With Text Editor", Return) is Windows' plain "Open".
        if accel == 'Return' and text and text != tr('Open'):
            button.set_property('text', tr('Open'))
            text = tr('Open')
        if text in ('Scripts', 'Scripts'.replace('Scripts', 'Guiones')):
            scripts = os.path.join(GLib.get_user_data_dir(), 'nautilus', 'scripts')
            # Windows has no Scripts entry; keep it only when the user has scripts.
            button.set_visible(bool(os.path.isdir(scripts) and os.listdir(scripts)))
        if button.get_property('icon') is None and text in LABEL_ICONS:
            button.set_property('icon', Gio.ThemedIcon.new(LABEL_ICONS[text]))
        for child in walk(button):
            if isinstance(child, Gtk.Label):
                if child.get_css_name() == 'accelerator':
                    if 'Return' in child.get_label():
                        child.set_label(child.get_label().replace('Return', 'Enter'))
                else:
                    child.set_hexpand(True)
                    child.set_xalign(0)
        icon = button.get_property('icon')
        # GTK receives these icons from GMenu but hides them beside text.
        # Reveal its existing image, leaving action, focus and shortcuts native.
        if icon is None:
            continue
        for image in list(walk(button))[1:]:
            if isinstance(image, Gtk.Image) and image.get_gicon() is not None:
                image.set_pixel_size(16)
                image.set_visible(True)
                image.set_hexpand(False)
                image.add_css_class('windows-menu-icon')


def _popover_mapped(menu):
    decorate_menu(menu)
    # Submenu pages are built lazily; decorate again once they exist.
    GLib.idle_add(lambda: (decorate_menu(menu), GLib.SOURCE_REMOVE)[1])


def _map_hook(widget):
    if isinstance(widget, Gtk.PopoverMenu) and not getattr(widget, '_windows_menu', False):
        widget._windows_menu = True
        widget.connect('map', _popover_mapped)
        _popover_mapped(widget)
    return True


class TabStripSizer:
    """Use the same 200 ms/ease curve as native AdwTabBox open and close."""
    def __init__(self, bar, view, window):
        self.bar, self.view, self.window = bar, view, window
        self.animation = None
        self.target = None

    def resize(self, animate):
        # Windows 11 tabs are 240px wide (+10px tab-box padding).
        available = max(250, self.window.get_width() - 200)
        target = min(max(250, self.view.get_n_pages() * 250), available)
        if target == self.target:
            return
        self.target = target
        current = self.animation.get_value() if self.animation else max(250, self.bar.get_width())
        if self.animation:
            self.animation.pause()
            self.animation = None
        if not animate or not self.bar.get_mapped():
            self.bar.set_size_request(target, -1)
            return
        callback = Adw.CallbackAnimationTarget.new(lambda value: self.bar.set_size_request(round(value), -1))
        animation = Adw.TimedAnimation.new(self.bar, current, target, 200, callback)
        animation.set_easing(Adw.Easing.EASE)
        self.animation = animation
        animation.connect('done', self._done)
        animation.play()

    def _done(self, animation):
        if self.animation == animation:
            self.animation = None


class FenestraExplorer(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "FenestraExplorerAppearance"
    def __init__(self):
        super().__init__()
        GLib.idle_add(self._start)
        # Every popover menu (context menus are recreated per popup) gets Windows icons.
        # (PyGObject has no GObject.type_class_ref; GtkWidget's class is already
        # initialised inside Nautilus, which is all add_emission_hook needs.)
        try:
            GObject.add_emission_hook(Gtk.Widget, 'map', _map_hook)
        except Exception as e:  # never take the rest of the Explorer layer down
            print(f"fenestra-explorer: no menu icon hook: {e}")

    def _start(self):
        app = Gio.Application.get_default()
        if not isinstance(app, Gtk.Application):
            return GLib.SOURCE_REMOVE
        app.connect('window-added', lambda _app, win: GLib.idle_add(self._attach, win))
        for win in app.get_windows():
            self._attach(win)
        return GLib.SOURCE_REMOVE

    def _relabel(self, window):
        for widget in walk(window):
            if isinstance(widget, Gtk.Label) and widget.has_css_class('win11-cmd-label') and not getattr(widget, '_fenestra_tr', False):
                widget._fenestra_tr = True
                widget.set_label(tr(widget.get_label()))
            elif isinstance(widget, Gtk.Widget) and widget.get_tooltip_text() and not getattr(widget, '_fenestra_tip', False):
                widget._fenestra_tip = True
                widget.set_tooltip_text(tr(widget.get_tooltip_text()))

    def _search_label(self, window, title):
        for widget in walk(window):
            if isinstance(widget, Gtk.Label) and widget.has_css_class('win11-search-label'):
                widget.set_label(tr('Search %s') % title if title else tr('Search'))

    def _attach(self, window):
        self._relabel(window)
        if window.find_property("active-slot") and not getattr(window,"_windows_views",None):
            window._windows_views = FenestraViews(window)
        for widget in walk(window):
            if isinstance(widget, Gtk.PopoverMenu) and not getattr(widget, '_windows_menu', False):
                widget._windows_menu = True
                widget.connect('map', lambda menu: decorate_menu(menu))
            if isinstance(widget, Adw.TabView) and not getattr(widget, '_windows_icons', False):
                widget._windows_icons = True
                bar = next((b for b in walk(window) if isinstance(b, Adw.TabBar) and b.get_view() == widget), None)
                if bar:
                    sizer = TabStripSizer(bar, widget, window)
                    bar._windows_sizer = sizer
                    widget.connect('notify::n-pages', lambda *_args, obj=sizer: obj.resize(True))
                    window.connect('notify::default-width', lambda *_args, obj=sizer: obj.resize(False))
                    window.connect('map', lambda *_args, obj=sizer: obj.resize(False))
                    sizer.resize(False)
                widget.connect('page-attached', lambda view, page, _index: self._page(page))
                for i in range(widget.get_n_pages()):
                    self._page(widget.get_nth_page(i))
        return GLib.SOURCE_REMOVE

    def _page(self, page):
        slot = page.get_child()
        if not slot.find_property('location'):
            return
        if not getattr(slot, '_windows_tab_icon', False):
            slot._windows_tab_icon = True
            # Resolve its current page after a tab is transferred to a window.
            slot.connect('notify::location', lambda obj, _ps: self._refresh_slot(obj))
        self._set_icon(page, slot)

    def _refresh_slot(self, slot):
        parent = slot.get_parent()
        while parent and not isinstance(parent, Adw.TabView):
            parent = parent.get_parent()
        if parent:
            page = parent.get_page(slot)
            if page:
                self._set_icon(page, slot)

    def _set_icon(self, page, slot):
        location = slot.get_property('location')
        name = 'folder'
        if location:
            path = location.get_path()
            special = {os.path.expanduser('~'): 'folder-home'}
            for key, icon in [('DIRECTORY_DESKTOP', 'user-desktop'), ('DIRECTORY_DOCUMENTS', 'folder-documents'),
                              ('DIRECTORY_DOWNLOAD', 'folder-download'), ('DIRECTORY_MUSIC', 'folder-music'),
                              ('DIRECTORY_PICTURES', 'folder-pictures'), ('DIRECTORY_VIDEOS', 'folder-videos')]:
                value = GLib.get_user_special_dir(getattr(GLib.UserDirectory, key))
                if value:
                    special[value] = icon
            name = special.get(path, 'folder')
            if not path:
                name = {'trash':'user-trash', 'recent':'document-open-recent', 'starred':'starred',
                        'network':'network-workgroup', 'computer':'computer'}.get(location.get_uri_scheme(), 'folder-remote')
        page.set_icon(Gio.ThemedIcon.new('hwin' if name == 'folder-home' else name))
        if location and location.get_uri_scheme() == 'computer':
            page.set_title(tr('This PC'))
        window = slot.get_root()
        if window:
            title = tr('Home') if location and location.get_path() == os.path.expanduser('~') else page.get_title()
            if location and location.get_path() == os.path.expanduser('~'):
                page.set_title(tr('Home'))
            GLib.idle_add(lambda: (self._search_label(window, title), GLib.SOURCE_REMOVE)[1])
        if location and location.get_uri_scheme()=='computer' and page.get_title()!=tr('This PC'):page.set_title(tr('This PC'))
        if location and location.get_path() == str(GALLERY):
            page.set_title(tr('Gallery'))
            page.set_icon(Gio.ThemedIcon.new('folder-pictures'))
            if window:
                GLib.idle_add(lambda: (self._search_label(window, tr('Gallery')), GLib.SOURCE_REMOVE)[1])

    def _menus(self):
        app = Gio.Application.get_default()
        if isinstance(app, Gtk.Application):
            for window in app.get_windows():
                decorate_menu(window)
        return GLib.SOURCE_REMOVE

    def get_file_items(self, *args):
        GLib.idle_add(self._menus)
        files = args[-1] if args else []
        paths = [f.get_location().get_path() for f in files or [] if f.get_location().get_path()]
        if not paths:
            return []
        item = Nautilus.MenuItem(name='FenestraExplorer::copy-path', label=tr('Copy as path'))
        item.connect('activate', lambda *_a: Gdk.Display.get_default().get_clipboard().set('\n'.join(f'"{p}"' for p in paths)))
        return [item]

    def get_background_items(self, *args):
        GLib.idle_add(self._menus)
        return []

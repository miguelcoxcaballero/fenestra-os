"""Native Nautilus tab icons and context-menu images; no file actions replaced."""
import gi
import os

gi.require_version('Nautilus', '4.1')
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, GObject, Gtk, Nautilus
from fenestra_views import FenestraViews
from fenestra_sidebar import tr


def walk(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


def decorate_menu(widget):
    for button in walk(widget):
        if GObject.type_name(button.__gtype__) != 'GtkModelButton':
            continue
        if button.get_property('iconic'):
            continue
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


class TabStripSizer:
    """Use the same 200 ms/ease curve as native AdwTabBox open and close."""
    def __init__(self, bar, view, window):
        self.bar, self.view, self.window = bar, view, window
        self.animation = None
        self.target = None

    def resize(self, animate):
        available = max(220, self.window.get_width() - 200)
        target = min(max(220, self.view.get_n_pages() * 220), available)
        if target == self.target:
            return
        self.target = target
        current = self.animation.get_value() if self.animation else max(220, self.bar.get_width())
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

    def _start(self):
        app = Gio.Application.get_default()
        if not isinstance(app, Gtk.Application):
            return GLib.SOURCE_REMOVE
        app.connect('window-added', lambda _app, win: GLib.idle_add(self._attach, win))
        for win in app.get_windows():
            self._attach(win)
        return GLib.SOURCE_REMOVE

    def _attach(self, window):
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
        page.set_icon(Gio.ThemedIcon.new(name))
        if location and location.get_uri_scheme()=='computer' and page.get_title()!=tr('This PC'):page.set_title(tr('This PC'))

    def _menus(self):
        app = Gio.Application.get_default()
        if isinstance(app, Gtk.Application):
            for window in app.get_windows():
                decorate_menu(window)
        return GLib.SOURCE_REMOVE

    def get_file_items(self, *args):
        GLib.idle_add(self._menus)
        return []

    def get_background_items(self, *args):
        GLib.idle_add(self._menus)
        return []

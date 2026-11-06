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


# The overlay's context-menu labels have no entry in Nautilus' catalogue; Explorer's wording.
MENU_ES = {'Renombrar…': 'Cambiar nombre', 'Mover a la papelera': 'Eliminar', 'Rename': 'Cambiar nombre', 'Share': 'Compartir', 'Delete': 'Eliminar', 'View': 'Ver', 'Sort by': 'Ordenar por', 'Group by': 'Agrupar por', 'New': 'Nuevo', 'Folder': 'Carpeta',
           'Open in Terminal': 'Abrir en Terminal', 'Open With…': 'Abrir con', 'Open with…': 'Abrir con',
           'Cut': 'Cortar', 'Copy': 'Copiar', 'Paste': 'Pegar', 'Rename…': 'Cambiar nombre', 'Move to Trash': 'Eliminar',
           'Compress to ZIP file': 'Comprimir en archivo ZIP', 'Extract to…': 'Extraer en…', 'Extract': 'Extraer todo',
           'Open in New Tab': 'Abrir en una pestaña nueva', 'Open in New Window': 'Abrir en una ventana nueva',
           'Name': 'Nombre', 'Date modified': 'Fecha de modificación', 'Type': 'Tipo', 'Size': 'Tamaño',
           'Ascending': 'Ascendente', 'Descending': 'Descendente', '(None)': '(Ninguno)',
           'Extra large icons': 'Iconos muy grandes', 'Large icons': 'Iconos grandes', 'Medium icons': 'Iconos medianos',
           'Small icons': 'Iconos pequeños', 'List': 'Lista', 'Details': 'Detalles', 'Tiles': 'Mosaicos',
           'Content': 'Contenido', 'Compact view': 'Vista compacta', 'Show Hidden Files': 'Mostrar archivos ocultos',
           'Set as desktop background': 'Establecer como fondo de escritorio', 'Properties': 'Propiedades',
           'Copy Address': 'Copiar dirección', 'Open Item Location': 'Abrir ubicación del elemento',
           'Paste Into Folder': 'Pegar en la carpeta', 'Unstar': 'Quitar de Favoritos', 'Delete Permanently…': 'Eliminar permanentemente…',
           'Empty Trash…': 'Vaciar papelera de reciclaje…', 'Restore From Trash': 'Restaurar', 'Remove From Recent': 'Quitar de Reciente'}


def iconic_label(button):
    """Explorer's context menu top row (Cut, Copy, Rename, Share, Delete) puts the label under
    the glyph; GtkModelButton hides the label of iconic items, so show it below the image."""
    text = (button.get_property('text') or '').replace('_', '')
    if not text:
        return
    text = MENU_ES.get(text, text) if tr('View') != 'View' else text
    layout = button.get_layout_manager()
    if isinstance(layout, Gtk.BoxLayout):
        layout.set_orientation(Gtk.Orientation.VERTICAL)
        layout.set_spacing(4)
    button.add_css_class('fenestra-iconic')
    label = next((c for c in walk(button) if isinstance(c, Gtk.Label) and c.get_css_name() != 'accelerator'), None)
    if label is None:
        return
    label.set_label(text)
    label.set_wrap(True)
    label.set_justify(Gtk.Justification.CENTER)
    label.set_max_width_chars(8)
    label.set_xalign(0.5)
    label.set_visible(True)
    if not getattr(label, '_fenestra_shown', False):
        label._fenestra_shown = True
        label.connect('notify::visible', lambda l, _p: l.get_visible() or l.set_visible(True))


def decorate_menu(widget):
    for button in walk(widget):
        if GObject.type_name(button.__gtype__) != 'GtkModelButton':
            continue
        if button.get_property('iconic'):
            iconic_label(button)
            continue
        text = (button.get_property('text') or '').replace('_', '')
        if text in MENU_ES and tr('View') != 'View':
            text = MENU_ES[text]
            button.set_property('text', text)
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
                    if 'Intro' in child.get_label() and tr('View') != 'View':
                        # GTK's Spanish name for Return; Explorer writes Entrar.
                        child.set_label(child.get_label().replace('Intro', 'Entrar'))
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


# Nautilus 51 replaced its CSS widget names (#NautilusPathBar, ...) with style
# classes (.nautilus-pathbar, ...). Fenestra's GTK themes and user CSS target the
# names, so give the widgets their Nautilus 49 names back (no-op on 49).
LEGACY_NAMES = {'nautilus-pathbar': 'NautilusPathBar', 'nautilus-path-button': 'NautilusPathButton',
                'nautilus-view-cell': 'NautilusViewCell', 'nautilus-query-editor': 'NautilusQueryEditor',
                'nautilus-progress-indicator': 'NautilusProgressIndicator',
                'nautilus-app-chooser': 'NautilusAppChooser', 'nautilus-file-chooser': 'NautilusFileChooser'}


def legacy_name(widget):
    for cls in widget.get_css_classes():
        name = LEGACY_NAMES.get(cls)
        if name and widget.get_name() != name:
            widget.set_name(name)
            return


def _map_hook(widget):
    legacy_name(widget)
    if isinstance(widget, Gtk.PopoverMenu) and not getattr(widget, '_windows_menu', False):
        widget._windows_menu = True
        widget.connect('map', _popover_mapped)
        _popover_mapped(widget)
    return True


def explorer_search(toolbar):
    """Explorer searches from the search box: while the slot searches, the query editor
    (search_container, moved next to the search button by the toolbar overlay) takes the
    search box's place and the address keeps the path bar."""
    if getattr(toolbar, '_fenestra_search', False):
        return
    switcher = next((w for w in walk(toolbar) if isinstance(w, Gtk.Stack) and w.get_child_by_name('pathbar')), None)
    container = next((w for w in walk(toolbar) if w.has_css_class('fenestra-search-container')), None)
    button = next((w for w in walk(toolbar) if isinstance(w, Gtk.ToggleButton) and w.get_action_name() == 'slot.search-visible'), None)
    holder = button.get_parent() if button else None
    if not (switcher and container and isinstance(holder, Gtk.Stack)):
        return
    toolbar._fenestra_search = True
    state = {'slot': None, 'id': 0}

    def sync(*_args):
        slot = toolbar.get_property('window-slot')
        searching = bool(slot and slot.get_property('search-visible'))
        if searching and switcher.get_visible_child_name() == 'search':
            switcher.set_visible_child_name('pathbar')
        if searching and holder.get_visible():
            width = holder.get_width()
            if width > 0:
                container.set_size_request(width, -1)
        container.set_visible(searching)
        holder.set_visible(not searching)
        # Explorer's box has just the text and a clear button: no folder glyph, no filter menu.
        editor = container.get_first_child()
        if editor is not None:
            for child in list(walk(editor))[1:]:
                if child.get_parent() is editor and (isinstance(child, Gtk.MenuButton) or
                                                     (isinstance(child, Gtk.Image) and child is editor.get_first_child())):
                    child.set_visible(False)
                elif isinstance(child, Gtk.Image) and (child.get_icon_name() or '').startswith('edit-clear'):
                    child.set_from_icon_name('window-close-symbolic')  # Explorer's clear is an X
                    child.set_pixel_size(12)
        if slot is not state['slot']:
            if state['slot'] is not None and state['id']:
                try:
                    state['slot'].disconnect(state['id'])
                except TypeError:
                    pass
            state['slot'] = slot
            state['id'] = slot.connect('notify::search-visible', lambda *_: GLib.idle_add(sync)) if slot else 0
        return GLib.SOURCE_REMOVE

    # Alt+D / Ctrl+L: the entry takes the whole address box like Explorer's.
    entry = next((w for w in walk(switcher) if GObject.type_name(w.__gtype__) == 'NautilusLocationEntry'), None)
    if entry is not None:
        entry.set_hexpand(True)
        entry.get_parent().add_css_class('fenestra-location-box')
    switcher.connect('notify::visible-child-name', lambda *_: GLib.idle_add(sync))
    toolbar.connect('notify::window-slot', lambda *_: GLib.idle_add(sync))
    sync()


def explorer_shortcuts(window):
    """Alt+D edits the address (Nautilus' Ctrl+L, the toolbar's edit-location action)."""
    if getattr(window, '_fenestra_keys', False):
        return
    window._fenestra_keys = True
    keys = Gtk.ShortcutController()
    keys.set_scope(Gtk.ShortcutScope.GLOBAL)
    keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

    def edit_location(*_args):
        toolbar = next((w for w in walk(window) if GObject.type_name(w.__gtype__) == 'NautilusToolbar'), None)
        return bool(toolbar and toolbar.activate_action('toolbar.edit-location', None))
    keys.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string('<Alt>d'), Gtk.CallbackAction.new(edit_location)))
    window.add_controller(keys)
    # A new tab (Ctrl+T, the + button) opens Home in Explorer, not a copy of the current folder.
    original = window.lookup_action('new-tab') if isinstance(window, Gio.ActionMap) else None
    if original is not None and not getattr(window, '_fenestra_new_tab', False):
        window._fenestra_new_tab = True
        window.remove_action('new-tab')
        action = Gio.SimpleAction.new('new-tab', None)

        def new_tab(*_args):
            original.activate(None)
            home = Gio.File.new_for_path(GLib.get_home_dir()).get_uri()
            slot = window.get_property('active-slot')
            if slot is not None:
                slot.activate_action('slot.open-location', GLib.Variant('s', home))
        action.connect('activate', new_tab)
        window.add_action(action)


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
        for widget in walk(window):
            legacy_name(widget)
            if GObject.type_name(widget.__gtype__) == 'NautilusToolbar':
                explorer_search(widget)
        explorer_shortcuts(window)
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
        if not getattr(page, '_fenestra_title', False):
            page._fenestra_title = True
            page.connect('notify::title', lambda p, _ps: self._search_title(p))
        self._set_icon(page, slot)

    def _search_title(self, page):
        """Explorer titles a search tab '<query> - Search Results in <folder>'."""
        slot = page.get_child()
        location = slot.get_property('location') if slot else None
        if not location or location.get_uri_scheme() != 'x-nautilus-search':
            return
        editor = next((w for w in walk(slot.get_root() or slot) if GObject.type_name(w.__gtype__) == 'NautilusQueryEditor'
                       and w.get_mapped()), None)
        text = next((w for w in walk(editor) if isinstance(w, Gtk.Text)), None) if editor is not None else None
        query = text.get_text() if text is not None else ''
        views = getattr(slot.get_root(), '_windows_views', None)
        title = tr('%s - Search Results in %s') % (query, getattr(views, '_folder_title', ''))
        if query and page.get_title() != title:
            GLib.idle_add(lambda: (page.get_title() != title and page.set_title(title), GLib.SOURCE_REMOVE)[1])

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
                name = {'trash':'user-trash', 'recent':'document-open-recent', 'starred':'starred', 'x-nautilus-search':'win11-explorer-search',
                        'network':'network-workgroup', 'computer':'computer'}.get(location.get_uri_scheme(), 'folder-remote')
        page.set_icon(Gio.ThemedIcon.new('hwin' if name == 'folder-home' else name))
        if location and location.get_uri_scheme() == 'computer':
            page.set_title(tr('This PC'))
        window = slot.get_root()
        # A search keeps the box's "Search <folder>" text (the tab title becomes the query).
        if window and not (location and location.get_uri_scheme() == 'x-nautilus-search'):
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

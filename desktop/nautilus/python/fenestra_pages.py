"""Windows 11 File Explorer special pages (Home, This PC, Gallery) shown in place of
Nautilus' file view for those locations. Navigation and file actions stay native:
items open through the slot's own 'open-location' action or the default application."""
import json
import locale
import os
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango

from fenestra_sidebar import _L, tr, GALLERY

_L.setdefault('es', {}).update({
    'Quick access': 'Acceso rápido', 'Stored locally': 'Almacenado localmente', 'Recent': 'Reciente',
    'Favorites': 'Favoritos', 'Shared': 'Compartido', 'Your recent activity will show here': 'Tu actividad reciente se mostrará aquí',
    "You'll get quick access to your recently used files here.": 'Aquí tendrás acceso rápido a los archivos que usaste recientemente.',
    'Name': 'Nombre', 'Date accessed': 'Fecha de acceso', 'File location': 'Ubicación del archivo', 'Activity': 'Actividad',
    'Devices and drives': 'Dispositivos y unidades', 'Local Disk': 'Disco local', '%s free of %s': '%s disponibles de %s',
    'Gallery is a place to view your photos in File Explorer': 'Galería es un lugar para ver tus fotos en el Explorador de archivos',
    'Add any folder with photos in it to get started.': 'Agrega cualquier carpeta que contenga fotos para empezar.',
    'Add a folder': 'Agregar una carpeta', 'Collection': 'Colección', 'Manage collection': 'Administrar colección',
    'Your favorite files will show here': 'Tus archivos favoritos se mostrarán aquí',
    'Files shared with you will show here': 'Los archivos compartidos contigo se mostrarán aquí',
})

IMAGE_TYPES = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.heic', '.avif')
GALLERY_CONFIG = Path(GLib.get_user_config_dir()) / 'fenestra-explorer' / 'gallery.json'


def _special(kind):
    path = GLib.get_user_special_dir(kind)
    return path if path and path != GLib.get_home_dir() else None


def gallery_folders():
    try:
        folders = json.loads(GALLERY_CONFIG.read_text()).get('folders') or []
    except (OSError, ValueError, AttributeError):
        folders = []
    pictures = _special(GLib.UserDirectory.DIRECTORY_PICTURES) or str(Path.home() / 'Pictures')
    return [pictures] + [f for f in folders if f != pictures]


def add_gallery_folder(path):
    folders = [f for f in gallery_folders()[1:] if f != path] + [path]
    try:
        GALLERY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        GALLERY_CONFIG.write_text(json.dumps({'folders': folders}))
    except OSError:
        pass


def page_kind(location):
    """'home', 'computer' or 'gallery' for the Explorer's special locations."""
    if location is None:
        return None
    if location.get_uri_scheme() == 'computer':
        return 'computer'
    path = location.get_path()
    if path == GLib.get_home_dir():
        return 'home'
    if path and (path == str(GALLERY) or location.get_uri() == GALLERY.as_uri()):
        return 'gallery'
    return None


def label(text, *classes, xalign=0.0, ellipsize=True):
    lab = Gtk.Label(label=text, xalign=xalign)
    for c in classes:
        lab.add_css_class(c)
    if ellipsize:
        lab.set_ellipsize(Pango.EllipsizeMode.END)
    return lab


def icon(name, size):
    image = Gtk.Image.new_from_icon_name(name) if isinstance(name, str) else Gtk.Image.new_from_gicon(name)
    image.set_pixel_size(size)
    return image


def human_size(n):
    for unit in ('bytes', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            # Explorer writes the locale's decimal separator (31,1 GB in Spanish).
            return f'{n:.0f} {unit}' if unit == 'bytes' else f'{n:.1f} {unit}'.replace('.', locale.localeconv()['decimal_point'])
        n /= 1024.0


def _unix(stamp):
    if stamp is None:
        return 0
    return stamp.to_unix() if hasattr(stamp, 'to_unix') else int(stamp)


def _double_click(widget, callback):
    gesture = Gtk.GestureClick(button=1)
    gesture.connect('pressed', lambda g, n, x, y: callback() if n == 2 else None)
    widget.add_controller(gesture)


def _shown_name(name):
    """Explorer hides the extension of registered file types; Recent only lists files an
    application opened, so drop it there."""
    stem, dot, ext = name.rpartition('.')
    return stem if dot and stem and ' ' not in ext and len(ext) <= 5 else name


class Page:
    count = 0

    def __init__(self, open_uri):
        self.open_uri = open_uri
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, hexpand=True)
        self.scroller.add_css_class('fenestra-page')

    def launch(self, uri):
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error:
            self.open_uri(uri)


# ------------------------------------------------------------------ Home ---
class HomePage(Page):
    PINNED = [(GLib.UserDirectory.DIRECTORY_DESKTOP, 'Desktop', 'user-desktop'),
              (GLib.UserDirectory.DIRECTORY_DOWNLOAD, 'Downloads', 'folder-download'),
              (GLib.UserDirectory.DIRECTORY_DOCUMENTS, 'Documents', 'folder-documents'),
              (GLib.UserDirectory.DIRECTORY_PICTURES, 'Pictures', 'folder-pictures'),
              (GLib.UserDirectory.DIRECTORY_MUSIC, 'Music', 'folder-music'),
              (GLib.UserDirectory.DIRECTORY_VIDEOS, 'Videos', 'folder-videos')]

    def __init__(self, open_uri):
        super().__init__(open_uri)
        self.tab = 'recent'
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class('fenestra-home')
        self.scroller.set_child(box)
        # Quick access header + pinned folder grid.
        self.quick = self._section_header(tr('Quick access'), box)
        self.grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True, max_children_per_line=3,
                                min_children_per_line=1, halign=Gtk.Align.START, column_spacing=0, row_spacing=0, activate_on_single_click=False)
        self.grid.add_css_class('fenestra-quick-grid')
        self.grid.connect('child-activated', lambda _g, child: self.open_uri(child._uri))
        box.append(self.grid)
        self.quick._content = self.grid
        # Recent / Favorites / Shared
        tabs = Gtk.Box(spacing=8)
        tabs.add_css_class('fenestra-home-tabs')
        chevron = Gtk.ToggleButton(active=True)
        chevron.set_child(icon('win11-explorer-chevron-down', 18))
        chevron.add_css_class('flat')
        chevron.add_css_class('fenestra-section-chevron')
        tabs.append(chevron)
        self.pills = {}
        for key, text, glyph in (('recent', 'Recent', 'win11-explorer-recent'), ('favorites', 'Favorites', 'win11-explorer-favorite'),
                                 ('shared', 'Shared', 'win11-explorer-shared')):
            pill = Gtk.ToggleButton()
            inner = Gtk.Box(spacing=8)
            inner.append(icon(glyph, 16))
            inner.append(label(tr(text), ellipsize=False))
            pill.set_child(inner)
            pill.add_css_class('fenestra-pill')
            pill.connect('clicked', lambda _b, k=key: self.select_tab(k))
            tabs.append(pill)
            self.pills[key] = pill
        box.append(tabs)
        self.stack = Gtk.Stack(vexpand=True)
        box.append(self.stack)
        chevron.connect('toggled', lambda b: (self.stack.set_visible(b.get_active()),
                                               b.get_child().set_from_icon_name('win11-explorer-chevron-down' if b.get_active() else 'win11-explorer-chevron-right')))
        self.listing = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.listing.add_css_class('fenestra-details')
        self.stack.add_named(self.listing, 'list')
        self.empty_title = label('', 'fenestra-empty-title', xalign=0.5)
        self.empty_body = label('', 'fenestra-empty-body', xalign=0.5)
        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, halign=Gtk.Align.CENTER)
        empty.add_css_class('fenestra-home-empty')
        self.empty_art = icon('win11-explorer-recent-empty', 128)
        self.empty_art.set_size_request(128, 104)
        empty.append(self.empty_art)
        empty.append(self.empty_title)
        empty.append(self.empty_body)
        self.stack.add_named(empty, 'empty')
        self.recent = Gtk.RecentManager.get_default()
        self.recent.connect('changed', lambda *_: self.refresh_recent())

    def _section_header(self, text, box):
        button = Gtk.ToggleButton(active=True, halign=Gtk.Align.START)
        inner = Gtk.Box(spacing=12)
        chev = icon('win11-explorer-chevron-down', 18)
        inner.append(chev)
        inner.append(label(text, 'fenestra-section-title', ellipsize=False))
        button.set_child(inner)
        button.add_css_class('fenestra-section-header')

        def toggled(b):
            b._content.set_visible(b.get_active())
            chev.set_from_icon_name('win11-explorer-chevron-down' if b.get_active() else 'win11-explorer-chevron-right')
        button.connect('toggled', toggled)
        box.append(button)
        return button

    def refresh(self):
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt
        n = 0
        for kind, name, glyph in self.PINNED:
            path = _special(kind)
            if not path or not os.path.isdir(path):
                continue
            tile = Gtk.Box(spacing=10)
            tile.add_css_class('fenestra-quick-tile')
            tile.append(icon(glyph, 48))
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            text.append(label(tr(name), 'fenestra-tile-name'))
            sub = label(tr('Stored locally'), 'fenestra-tile-sub')
            sub.set_max_width_chars(19)  # Explorer cuts it at the tile's 114 px text width
            text.append(sub)
            pin = icon('win11-explorer-pin', 12)
            pin.set_halign(Gtk.Align.START)
            pin.add_css_class('fenestra-tile-pin')
            text.append(pin)
            tile.append(text)
            child = Gtk.FlowBoxChild()
            child.set_child(tile)
            child._uri = Gio.File.new_for_path(path).get_uri()
            self.grid.append(child)
            n += 1
        self.pinned = n
        self.refresh_recent()
        GLib.timeout_add(400, self._focus_quick)

    def _focus_quick(self):
        # Keyboard focus starts on Quick access, without a focus ring until a key is used (Explorer).
        if self.quick.get_mapped() and self.quick.grab_focus():
            root = self.quick.get_root()
            if root:
                root.set_focus_visible(False)
        return GLib.SOURCE_REMOVE

    def select_tab(self, key):
        self.tab = key
        for k, pill in self.pills.items():
            pill.set_active(k == key)
            (pill.add_css_class if k == key else pill.remove_css_class)('active')
        self.refresh_recent()

    def refresh_recent(self):
        for k, pill in self.pills.items():
            if pill.get_active() != (k == self.tab):
                pill.set_active(k == self.tab)
            (pill.add_css_class if k == self.tab else pill.remove_css_class)('active')
        child = self.listing.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.listing.remove(child)
            child = nxt
        items = []
        if self.tab == 'recent':
            for info in self.recent.get_items():
                if not info.exists() or not info.get_uri().startswith('file://'):
                    continue
                items.append(info)
            items.sort(key=lambda i: _unix(i.get_visited() or i.get_modified()), reverse=True)
            items = items[:20]
        self.count = getattr(self, 'pinned', 0) + len(items)
        if not items:
            self.empty_art.set_from_icon_name('win11-explorer-recent-empty')
            self.empty_title.set_label({'recent': tr('Your recent activity will show here'), 'favorites': tr('Your favorite files will show here'),
                                        'shared': tr('Files shared with you will show here')}[self.tab])
            self.empty_body.set_label(tr("You'll get quick access to your recently used files here.") if self.tab == 'recent' else '')
            self.empty_body.set_visible(self.tab == 'recent')
            self.stack.set_visible_child_name('empty')
            return
        header = Gtk.Box()
        header.add_css_class('fenestra-details-header')
        # Column minimums shrink with the window (Name takes the slack), like Explorer's Details.
        # Explorer: Name 314 px (takes the slack), Date accessed 184, File location 182, Activity 182.
        for i, (text, width) in enumerate(((tr('Name'), 160), (tr('Date accessed'), 184), (tr('File location'), 182), (tr('Activity'), 182))):
            cell = label(text, 'fenestra-col-title')
            cell.set_size_request(width, -1)
            cell.set_hexpand(i == 0)
            cell.set_max_width_chars(1)
            header.append(cell)
        self.listing.append(header)
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, activate_on_single_click=False)
        rows.add_css_class('fenestra-details-rows')
        rows.connect('row-activated', lambda _l, row: self.launch(row._uri))
        for info in items:
            row = Gtk.ListBoxRow()
            row._uri = info.get_uri()
            line = Gtk.Box()
            name = Gtk.Box(spacing=17, hexpand=True)
            name.set_size_request(160, -1)
            name.append(icon(info.get_gicon() or 'text-x-generic', 16))
            title = label(_shown_name(info.get_display_name()), 'fenestra-cell')
            title.set_max_width_chars(1)
            title.set_hexpand(True)
            name.append(title)
            line.append(name)
            visited = info.get_visited() or info.get_modified()
            stamp = time.strftime('%d/%m/%Y %H:%M', time.localtime(_unix(visited)))
            when = label(stamp, 'fenestra-cell', 'dim')
            when.set_size_request(184, -1)
            line.append(when)
            parent = Gio.File.new_for_uri(info.get_uri()).get_parent()
            where = parent.get_path() if parent else ''
            home = GLib.get_home_dir()
            if where and where.startswith(home):
                rest = where[len(home):].strip('/')
                where = rest.replace('/', '\\') if rest else tr('Home')
                for kind, nm, _g in self.PINNED:
                    p = _special(kind)
                    if p and parent.get_path() == p:
                        where = tr(nm)
            loc = label(where, 'fenestra-cell', 'dim')
            loc.set_size_request(182, -1)
            loc.set_max_width_chars(1)
            when.set_max_width_chars(1)
            line.append(loc)
            activity = label('', 'fenestra-cell', 'dim')
            activity.set_size_request(182, -1)
            line.append(activity)
            row.set_child(line)
            rows.append(row)
        self.listing.append(rows)
        self.stack.set_visible_child_name('list')


# --------------------------------------------------------------- This PC ---
class UsageBar(Gtk.DrawingArea):
    __gtype_name__ = 'FenestraUsageBar'

    def __init__(self, fraction):
        super().__init__()
        self.fraction = fraction
        self.set_size_request(190, 13)
        self.set_content_width(190)
        self.set_content_height(13)
        self.set_halign(Gtk.Align.START)
        self.set_draw_func(self._draw)

    def _draw(self, _area, cr, width, height):
        cr.set_source_rgb(0.902, 0.902, 0.902)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        cr.set_source_rgb(0.737, 0.737, 0.737)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, width - 1, height - 1)
        cr.stroke()
        if self.fraction > 0.9:
            cr.set_source_rgb(0.855, 0.149, 0.149)
        else:
            cr.set_source_rgb(0.0, 0.439, 0.796)
        cr.rectangle(1, 1, max(0, (width - 2) * self.fraction), height - 2)
        cr.fill()


def _labels_by_device():
    labels = {}
    base = '/dev/disk/by-label'
    try:
        for name in os.listdir(base):
            target = os.path.realpath(os.path.join(base, name))
            labels[target] = name.replace('\\x20', ' ')
    except OSError:
        pass
    return labels


def _root_device():
    try:
        with open('/proc/self/mounts') as f:
            for line in f:
                parts = line.split()
                if len(parts) > 2 and parts[1] == '/':
                    return os.path.realpath(parts[0])
    except OSError:
        pass
    return None


class ComputerPage(Page):
    def __init__(self, open_uri):
        super().__init__(open_uri)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class('fenestra-thispc')
        self.scroller.set_child(box)
        header = Gtk.ToggleButton(active=True, halign=Gtk.Align.START)
        inner = Gtk.Box(spacing=6)
        self.chev = icon('win11-explorer-chevron-down', 10)
        inner.append(self.chev)
        inner.append(label(tr('Devices and drives'), 'fenestra-group-title', ellipsize=False))
        header.set_child(inner)
        header.add_css_class('fenestra-group-header')
        box.append(header)
        self.drives = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True, max_children_per_line=6,
                                  min_children_per_line=1, activate_on_single_click=False, valign=Gtk.Align.START,
                                  halign=Gtk.Align.START)
        self.drives.add_css_class('fenestra-drives')
        self.drives.connect('child-activated', lambda _f, child: self.open_uri(child._uri))
        header.connect('toggled', lambda b: (self.drives.set_visible(b.get_active()),
                                             self.chev.set_from_icon_name('win11-explorer-chevron-down' if b.get_active() else 'win11-explorer-chevron-right')))
        box.append(self.drives)
        self.monitor = Gio.VolumeMonitor.get()
        for signal in ('mount-added', 'mount-removed', 'mount-changed'):
            self.monitor.connect(signal, lambda *_: self.refresh())

    def _volumes(self):
        labels = _labels_by_device()
        root_dev = _root_device()
        entries = [('/', labels.get(root_dev) or tr('Local Disk'), 'drive-harddisk-system')]
        seen = {'/'}
        for mount in self.monitor.get_mounts():
            if mount.is_shadowed():
                continue
            root = mount.get_root()
            path = root.get_path()
            if not path or path in seen or not path.startswith(('/run/media/', '/media/', '/mnt/')):
                continue
            seen.add(path)
            glyph = 'drive-removable-media' if mount.can_eject() else 'drive-harddisk'
            entries.append((path, mount.get_name() or tr('Local Disk'), glyph))
        return entries

    def refresh(self):
        child = self.drives.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.drives.remove(child)
            child = nxt
        letters = 'CDEFGHIJKLMNOPQRSTUVWXYZ'
        n = 0
        for i, (path, name, glyph) in enumerate(self._volumes()):
            try:
                info = Gio.File.new_for_path(path).query_filesystem_info('filesystem::size,filesystem::free', None)
                size = info.get_attribute_uint64('filesystem::size')
                free = info.get_attribute_uint64('filesystem::free')
            except GLib.Error:
                size = free = 0
            tile = Gtk.Box(spacing=8)
            tile.add_css_class('fenestra-drive')
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            image = icon(glyph if theme.has_icon(glyph) else 'drive-harddisk', 48)
            image.set_valign(Gtk.Align.START)
            tile.append(image)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            text.append(label(f'{name} ({letters[i]}:)' if i < len(letters) else name, 'fenestra-drive-name'))
            if size:
                text.append(UsageBar((size - free) / size))
                text.append(label(tr('%s free of %s') % (human_size(free), human_size(size)), 'fenestra-drive-free'))
            tile.append(text)
            child = Gtk.FlowBoxChild()
            child.set_child(tile)
            child._uri = Gio.File.new_for_path(path).get_uri()
            self.drives.append(child)
            n += 1
        self.count = n


# --------------------------------------------------------------- Gallery ---
class GalleryPage(Page):
    ROW = 200
    GAP = 4

    def __init__(self, open_uri, window):
        super().__init__(open_uri)
        self.window = window
        self.photos = []
        self.width = 0
        self.textures = {}
        self.stack = Gtk.Stack(vhomogeneous=False, hhomogeneous=False, valign=Gtk.Align.START)
        self.scroller.set_child(self.stack)
        # Empty state
        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
        empty.set_size_request(348, -1)
        empty.add_css_class('fenestra-gallery-empty')
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        art = Gtk.Picture(can_shrink=False, halign=Gtk.Align.CENTER)
        paintable = theme.lookup_icon('win11-explorer-gallery-empty', None, 348, 1, Gtk.TextDirection.NONE, 0)
        if paintable.get_file():
            art.set_file(paintable.get_file())
        art.set_size_request(348, 124)
        empty.append(art)
        title = label(tr('Gallery is a place to view your photos in File Explorer'), 'fenestra-gallery-title', ellipsize=False)
        title.set_wrap(True)
        title.set_max_width_chars(1)
        title.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        title.set_size_request(348, -1)
        empty.append(title)
        body = label(tr('Add any folder with photos in it to get started.'), 'fenestra-gallery-body', ellipsize=False)
        body.set_wrap(True)
        body.set_max_width_chars(1)
        body.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        body.set_size_request(348, -1)
        empty.append(body)
        sep = Gtk.Separator()
        sep.add_css_class('fenestra-gallery-sep')
        empty.append(sep)
        buttons = Gtk.Box(spacing=12, homogeneous=True)
        add = Gtk.Button(label=tr('Add a folder'))
        add.add_css_class('fenestra-accent-button')
        add.connect('clicked', lambda *_: self.add_folder())
        buttons.append(add)
        buttons.append(Gtk.Box())
        empty.append(buttons)
        self.stack.add_named(empty, 'empty')
        self.grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.scroller.get_hadjustment().connect('notify::page-size', lambda adj, _p: GLib.idle_add(self._relayout_idle))
        self.grid.add_css_class('fenestra-gallery')
        self.stack.add_named(self.grid, 'photos')

    def add_folder(self):
        dialog = Gtk.FileDialog(title=tr('Add a folder'))

        def done(d, result):
            try:
                folder = d.select_folder_finish(result)
            except GLib.Error:
                return
            if folder and folder.get_path():
                add_gallery_folder(folder.get_path())
                self.refresh()
        dialog.select_folder(self.window, None, done)

    def _scan(self):
        photos = []
        for folder in gallery_folders():
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                if root.count(os.sep) - folder.count(os.sep) > 3:
                    dirs[:] = []
                for name in files:
                    if name.lower().endswith(IMAGE_TYPES) and not name.startswith('.'):
                        path = os.path.join(root, name)
                        try:
                            mtime = os.stat(path).st_mtime
                        except OSError:
                            continue
                        photos.append((mtime, path))
        photos.sort(reverse=True)
        return photos[:600]

    def refresh(self):
        scanned = self._scan()
        self.photos = []
        for mtime, path in scanned:
            fmt = GdkPixbuf.Pixbuf.get_file_info(path)
            w, h = (fmt[1], fmt[2]) if fmt and fmt[0] else (4, 3)
            self.photos.append((mtime, path, max(1, w) / max(1, h)))
        self.count = len(self.photos)
        self.stack.set_visible_child_name('photos' if self.photos else 'empty')
        self.width = 0
        GLib.idle_add(self._relayout_idle)

    def _relayout_idle(self):
        self._relayout(int(self.scroller.get_hadjustment().get_page_size() or self.scroller.get_width()) - 24)
        return GLib.SOURCE_REMOVE

    def _relayout(self, width):
        if width <= 0 or width == self.width or not self.photos:
            return
        self.width = width
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt
        usable = width
        months = []
        for mtime, path, ratio in self.photos:
            key = time.strftime('%Y-%m', time.localtime(mtime))
            if not months or months[-1][0] != key:
                months.append((key, time.localtime(mtime), []))
            months[-1][2].append((path, ratio))
        for _key, stamp, items in months:
            month = GLib.DateTime.new_local(stamp.tm_year, stamp.tm_mon, 1, 0, 0, 0).format('%B %Y')
            self.grid.append(label(month[:1].upper() + month[1:], 'fenestra-gallery-month'))
            row, ratios = [], 0.0
            for path, ratio in items:
                row.append((path, ratio))
                ratios += ratio
                if ratios * self.ROW + self.GAP * (len(row) - 1) >= usable:
                    self._row(row, (usable - self.GAP * (len(row) - 1)) / ratios)
                    row, ratios = [], 0.0
            if row:
                self._row(row, self.ROW)

    def _row(self, row, height):
        height = int(min(height, self.ROW * 1.4))
        box = Gtk.Box(spacing=self.GAP)
        box.add_css_class('fenestra-gallery-row')
        for path, ratio in row:
            picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            picture.set_size_request(int(height * ratio), height)
            picture.add_css_class('fenestra-photo')
            frame = Gtk.Box()
            frame.add_css_class('fenestra-photo-frame')
            frame.append(picture)
            frame.set_overflow(Gtk.Overflow.HIDDEN)
            uri = Gio.File.new_for_path(path).get_uri()
            _double_click(frame, lambda u=uri: self.launch(u))
            box.append(frame)
            self._load(picture, path, height)
        self.grid.append(box)

    def _load(self, picture, path, height):
        cached = self.textures.get(path)
        if cached:
            picture.set_paintable(cached)
            return
        file = Gio.File.new_for_path(path)

        def thumb_done(f, result):
            try:
                info = f.query_info_finish(result)
                thumb = info.get_attribute_byte_string('thumbnail::path')
            except GLib.Error:
                thumb = None
            source = Gio.File.new_for_path(thumb) if thumb and os.path.exists(thumb) else f
            source.read_async(GLib.PRIORITY_LOW, None, read_done)

        def read_done(f, result):
            try:
                stream = f.read_finish(result)
            except GLib.Error:
                return
            GdkPixbuf.Pixbuf.new_from_stream_at_scale_async(stream, -1, max(height, 256), True, None, pixbuf_done, stream)

        def pixbuf_done(_src, result, stream):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_finish(result)
                pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
            except GLib.Error:
                return
            finally:
                stream.close_async(GLib.PRIORITY_LOW, None, None)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            self.textures[path] = texture
            picture.set_paintable(texture)
        file.query_info_async('thumbnail::path', Gio.FileQueryInfoFlags.NONE, GLib.PRIORITY_LOW, None, thumb_done)


# ------------------------------------------------------------ controller ---
class SpecialPages:
    """Swaps the active slot's NautilusFilesView for a special page when needed."""

    def __init__(self, window, walk, kind_of):
        self.window, self.walk, self.kind_of = window, walk, kind_of
        self.pages = {}
        self.active = None

    def _open(self, uri):
        slot = self.window.get_property('active-slot') if self.window else None
        if slot:
            slot.activate_action('slot.open-location', GLib.Variant('s', uri))

    def page(self, kind):
        if kind not in self.pages:
            if kind == 'home':
                self.pages[kind] = HomePage(self._open)
            elif kind == 'computer':
                self.pages[kind] = ComputerPage(self._open)
            else:
                self.pages[kind] = GalleryPage(self._open, self.window)
        return self.pages[kind]

    def update(self, slot):
        """Returns the special page kind now shown in the slot (or None)."""
        location = slot.get_property('location')
        kind = page_kind(location)
        view = next((w for w in self.walk(slot) if self.kind_of(w) == 'NautilusFilesView'), None)
        if view is None:
            return None
        box = view.get_parent()
        for k, page in self.pages.items():
            widget = page.scroller
            if k != kind and widget.get_parent() is not None:
                widget.get_parent().remove(widget)
        if kind is None:
            view.set_visible(True)
            self.active = None
            return None
        page = self.page(kind)
        if page.scroller.get_parent() is not box:
            if page.scroller.get_parent() is not None:
                page.scroller.get_parent().remove(page.scroller)
            box.append(page.scroller)
        view.set_visible(False)
        if self.active != (kind, location.get_uri(), slot):
            self.active = (kind, location.get_uri(), slot)
            page.refresh()
        return kind

    def count(self, kind):
        page = self.pages.get(kind)
        return page.count if page else 0

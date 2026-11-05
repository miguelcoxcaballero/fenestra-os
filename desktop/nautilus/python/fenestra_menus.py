"""Windows 11 File Explorer command-bar dropdowns (View, Sort, See more) and the
Details/Preview pane. Each dropdown is a popover parented to its own button, so it
opens centred under it like Explorer's, with 16px glyphs and a dot for the active item."""
import os
import time

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from fenestra_sidebar import _L, tr

_L.setdefault('es', {}).update({
    'Details pane': 'Panel de detalles', 'Preview pane': 'Panel de vista previa', 'Show': 'Mostrar',
    'Item check boxes': 'Casillas de elementos', 'File name extensions': 'Extensiones de nombre de archivo',
    'Hidden items': 'Elementos ocultos', 'Name': 'Nombre', 'Date modified': 'Fecha de modificación', 'Type': 'Tipo',
    'Size': 'Tamaño', 'More': 'Más', 'Ascending': 'Ascendente', 'Descending': 'Descendente', 'Group by': 'Agrupar por',
    '(None)': '(Ninguno)', 'Pin to Quick access': 'Anclar a Acceso rápido', 'Select all': 'Seleccionar todo',
    'Select none': 'No seleccionar nada', 'Invert selection': 'Invertir selección', 'Properties': 'Propiedades',
    'Options': 'Opciones', 'Date created': 'Fecha de creación', 'Cut': 'Cortar', 'Copy': 'Copiar', 'Paste': 'Pegar',
    'Rename': 'Cambiar nombre', 'Share': 'Compartir', 'Delete': 'Eliminar', 'No preview available.': 'No hay vista previa disponible.',
    'Select a single file to preview.': 'Selecciona un solo archivo para obtener una vista previa.',
    '%d items selected': '%d elementos seleccionados', 'Sort': 'Ordenar', 'View': 'Ver',
})


def walk(w):
    yield w
    c = w.get_first_child()
    while c:
        yield from walk(c)
        c = c.get_next_sibling()


class WinMenu:
    """A Windows-style dropdown: rows of [dot/check] [16px glyph] label [accel or ›]."""

    def __init__(self, parent_row=None, marks=True):
        self.marks = marks
        self.popover = Gtk.Popover(has_arrow=False, autohide=True)
        self.popover.add_css_class('fenestra-winmenu')
        self.popover.set_offset(0, 6)
        if parent_row is not None:
            self.popover.set_position(Gtk.PositionType.RIGHT)
            self.popover.set_offset(0, -4)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.popover.set_child(self.box)
        self.rows = []
        self.images = []
        self.has_icons = False
        self.popover.connect('show', lambda *_: self.sync())

    def separator(self, visible=None):
        sep = Gtk.Separator()
        sep.add_css_class('fenestra-winmenu-sep')
        self.box.append(sep)
        self.rows.append((sep, None, None, visible, None))
        return sep

    def item(self, text, glyph=None, activate=None, active=None, check=False, submenu=None, accel=None,
             visible=None, sensitive=None):
        button = Gtk.Button()
        button.add_css_class('flat')
        button.add_css_class('fenestra-winmenu-row')
        line = Gtk.Box(spacing=0)
        mark = Gtk.Image.new_from_icon_name('win11-view-check') if check else Gtk.Label(label='•')
        if isinstance(mark, Gtk.Image):
            mark.set_pixel_size(12)
        mark.add_css_class('fenestra-winmenu-mark')
        mark.set_size_request(24, -1)
        mark.set_visible(self.marks)
        line.append(mark)
        image = Gtk.Image()
        image.set_pixel_size(16)
        image.add_css_class('fenestra-winmenu-icon')
        image.set_size_request(16, 16)
        if glyph:
            image.set_from_icon_name(glyph)
            self.has_icons = True
        line.append(image)
        self.images.append(image)
        lab = Gtk.Label(label=text, xalign=0, hexpand=True)
        lab.add_css_class('fenestra-winmenu-label')
        line.append(lab)
        if accel:
            acc = Gtk.Label(label=accel)
            acc.add_css_class('fenestra-winmenu-accel')
            line.append(acc)
        if submenu is not None:
            chev = Gtk.Image.new_from_icon_name('win11-explorer-chevron-right')
            chev.set_pixel_size(10)
            chev.add_css_class('fenestra-winmenu-chevron')
            line.append(chev)
            submenu.popover.set_parent(button)
            motion = Gtk.EventControllerMotion()
            motion.connect('enter', lambda *_: GLib.timeout_add(250, lambda: (button.get_state_flags() & Gtk.StateFlags.PRELIGHT
                                                                              and submenu.popover.popup(), False)[1]))
            button.add_controller(motion)
        button.set_child(line)

        def clicked(_b):
            if submenu is not None:
                submenu.popover.popup()
                return
            if activate:
                activate()
            self.popdown_all()
        button.connect('clicked', clicked)
        self.box.append(button)
        self.rows.append((button, mark, active, visible, sensitive))
        return button

    def popdown_all(self):
        widget = self.popover
        while widget is not None:
            if isinstance(widget, Gtk.Popover):
                widget.popdown()
            widget = widget.get_parent()

    def sync(self):
        for image in self.images:
            image.set_visible(self.has_icons)
        for widget, mark, active, visible, sensitive in self.rows:
            if visible is not None:
                widget.set_visible(bool(visible()))
            if sensitive is not None:
                widget.set_sensitive(bool(sensitive()))
            if mark is not None:
                mark.set_opacity(1.0 if active is not None and active() else 0.0)
        # A separator never leads, trails or doubles up after rows were hidden.
        shown = [r[0] for r in self.rows if r[0].get_visible() or isinstance(r[0], Gtk.Separator)]
        prev_sep = True
        for w in shown:
            if isinstance(w, Gtk.Separator):
                w.set_visible(not prev_sep)
                prev_sep = True
            else:
                prev_sep = False
        for w in reversed(shown):
            if isinstance(w, Gtk.Separator):
                w.set_visible(False)
            elif w.get_visible():
                break


def command_button(text, glyph):
    button = Gtk.MenuButton()
    button.add_css_class('win11-cmd-text')
    button.add_css_class('flat')
    contents = Gtk.Box(spacing=8)
    image = Gtk.Image.new_from_icon_name(glyph)
    image.set_pixel_size(16)
    lab = Gtk.Label(label=tr(text))
    lab.add_css_class('win11-cmd-label')
    chev = Gtk.Image.new_from_icon_name('win11-explorer-chevron-down')
    chev.set_pixel_size(8)
    chev.add_css_class('win11-cmd-chevron')
    contents.append(image)
    contents.append(lab)
    contents.append(chev)
    button.set_child(contents)
    return button


class InfoPane(Gtk.Box):
    """Windows' Details pane (file facts) / Preview pane (image or text preview)."""
    __gtype_name__ = 'FenestraInfoPane'

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class('fenestra-infopane')
        self.set_size_request(280, -1)
        self.mode = 'details'
        self.icon = Gtk.Image()
        self.icon.set_pixel_size(96)
        self.icon.add_css_class('fenestra-infopane-icon')
        self.picture = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.CONTAIN, vexpand=True)
        self.text = Gtk.Label(xalign=0, yalign=0, wrap=True, selectable=False, vexpand=True)
        self.text.add_css_class('fenestra-infopane-text')
        self.title = Gtk.Label(xalign=0, wrap=True)
        self.title.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.title.add_css_class('fenestra-infopane-title')
        self.subtitle = Gtk.Label(xalign=0)
        self.subtitle.add_css_class('fenestra-infopane-sub')
        self.facts = Gtk.Grid(column_spacing=12, row_spacing=6)
        self.facts.add_css_class('fenestra-infopane-facts')
        self.message = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, vexpand=True)
        self.message.add_css_class('fenestra-infopane-message')
        for w in (self.icon, self.picture, self.text, self.title, self.subtitle, self.facts, self.message):
            self.append(w)

    def show_files(self, files, folder):
        """files: list of Gio.File selected (may be empty → describe folder)."""
        for w in (self.icon, self.picture, self.text, self.title, self.subtitle, self.facts, self.message):
            w.set_visible(False)
        child = self.facts.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.facts.remove(child)
            child = nxt
        if self.mode == 'preview':
            if len(files) != 1:
                self.message.set_label(tr('Select a single file to preview.'))
                self.message.set_visible(True)
                return
            info = self._info(files[0])
            ctype = info.get_content_type() if info else ''
            path = files[0].get_path()
            if path and ctype and ctype.startswith('image/'):
                self.picture.set_filename(path)
                self.picture.set_visible(True)
            elif path and ctype and (ctype.startswith('text/') or Gio.content_type_is_a(ctype, 'text/plain')):
                try:
                    with open(path, errors='replace') as f:
                        self.text.set_label(f.read(4000))
                    self.text.set_visible(True)
                except OSError:
                    self.message.set_label(tr('No preview available.'))
                    self.message.set_visible(True)
            else:
                self.message.set_label(tr('No preview available.'))
                self.message.set_visible(True)
            return
        target = files[0] if len(files) == 1 else folder
        info = self._info(target) if target else None
        if len(files) > 1:
            self.icon.set_from_icon_name('emblem-documents')
            self.title.set_label(tr('%d items selected') % len(files))
            self.icon.set_visible(True)
            self.title.set_visible(True)
            return
        if info is None:
            return
        self.icon.set_from_gicon(info.get_icon() or Gio.ThemedIcon.new('text-x-generic'))
        self.icon.set_visible(True)
        self.title.set_label(info.get_display_name())
        self.title.set_visible(True)
        ctype = info.get_content_type() or ''
        self.subtitle.set_label(Gio.content_type_get_description(ctype) if ctype else '')
        self.subtitle.set_visible(True)
        rows = []
        if info.get_file_type() != Gio.FileType.DIRECTORY:
            size = info.get_size()
            rows.append((tr('Size'), GLib.format_size(size)))
        stamp = info.get_modification_date_time()
        if stamp:
            rows.append((tr('Date modified'), stamp.to_local().format('%d/%m/%Y %H:%M')))
        created = info.get_creation_date_time() if hasattr(info, 'get_creation_date_time') else None
        if created:
            rows.append((tr('Date created'), created.to_local().format('%d/%m/%Y %H:%M')))
        for i, (k, v) in enumerate(rows):
            key = Gtk.Label(label=k, xalign=0)
            key.add_css_class('fenestra-infopane-key')
            val = Gtk.Label(label=v, xalign=0, ellipsize=Pango.EllipsizeMode.END)
            self.facts.attach(key, 0, i, 1, 1)
            self.facts.attach(val, 1, i, 1, 1)
        self.facts.set_visible(bool(rows))

    @staticmethod
    def _info(gfile):
        try:
            return gfile.query_info('standard::*,time::*', Gio.FileQueryInfoFlags.NONE, None)
        except GLib.Error:
            return None


class CommandMenus:
    """Owns the View / Sort / See more dropdowns and the info pane for one window."""

    def __init__(self, views):
        self.views = views
        self.window = views.window
        self.folded = False
        self.sort_key, self.sort_desc = 'name', False
        self.pane_mode = getattr(views, 'pane', 'none')
        self.pane = None
        self.selection_model = None
        self.sort_button = self.view_button = None
        self.settings = None
        try:
            source = Gio.SettingsSchemaSource.get_default()
            if source.lookup('org.gnome.nautilus.preferences', True):
                self.settings = Gio.Settings.new('org.gnome.nautilus.preferences')
        except GLib.Error:
            pass

    # ---- helpers -----------------------------------------------------------
    def slot(self):
        return self.window.get_property('active-slot') if self.window else None

    def files_view(self):
        slot = self.slot()
        if not slot:
            return None
        return next((w for w in walk(slot) if GObject.type_name(w.__gtype__) == 'NautilusFilesView'), None)

    def act(self, name, value=None):
        view = self.files_view()
        target = view or self.window
        if target:
            target.activate_action(name, value)

    def slot_act(self, name, value=None):
        slot = self.slot()
        if slot:
            slot.activate_action(name, value)

    def item_view(self):
        slot = self.slot()
        if not slot:
            return None
        return next((w for w in walk(slot) if isinstance(w, (Gtk.ColumnView, Gtk.GridView)) and w.get_visible()), None)

    def select_none(self):
        view = self.item_view()
        if view and view.get_model():
            view.get_model().unselect_all()

    def set_sort(self, key=None, desc=None):
        if key is not None:
            self.sort_key = key
        if desc is not None:
            self.sort_desc = desc
        self.act('view.sort', GLib.Variant('(sb)', (self.sort_key, self.sort_desc)))

    def hidden_files(self):
        return bool(self.settings and self.settings.get_boolean('show-hidden-files'))

    # ---- menus -------------------------------------------------------------
    def build_view_menu(self):
        views = self.views
        menu = WinMenu()
        special = lambda: views.special
        folder = lambda: views.special != 'home'
        for key, text in (('extra-large', 'Extra large icons'), ('large', 'Large icons'), ('medium', 'Medium icons'),
                          ('small', 'Small icons'), ('list', 'List'), ('details', 'Details')):
            menu.item(tr(text), f'win11-view-{key}', activate=lambda k=key: views.select(k, remember=True),
                      active=lambda k=key: folder() and views.mode == k, visible=folder)
        for key, text in (('tiles', 'Tiles'), ('content', 'Content')):
            menu.item(tr(text), f'win11-view-{key}', activate=lambda k=key: views.select(k, remember=True),
                      active=lambda k=key: views.mode == k if folder() else k == 'tiles')
        menu.separator()
        menu.item(tr('Details pane'), 'win11-view-details-pane', activate=lambda: self.toggle_pane('details'),
                  active=lambda: self.pane_mode == 'details')
        menu.item(tr('Preview pane'), 'win11-view-preview-pane', activate=lambda: self.toggle_pane('preview'),
                  active=lambda: self.pane_mode == 'preview')
        menu.separator()
        show = WinMenu(parent_row=True)
        show.item(tr('Compact view'), None, activate=views.toggle_compact, active=lambda: views.compact, check=True)
        show.item(tr('Item check boxes'), None, active=lambda: False, check=True, sensitive=lambda: False)
        show.item(tr('File name extensions'), None, active=lambda: True, check=True, sensitive=lambda: False)
        show.item(tr('Hidden items'), None, activate=lambda: self.act('view.show-hidden-files'),
                  active=self.hidden_files, check=True)
        menu.item(tr('Show'), None, submenu=show)
        return menu

    def build_sort_menu(self):
        menu = WinMenu()
        for key, text in (('name', 'Name'), ('date_modified', 'Date modified'), ('type', 'Type')):
            menu.item(tr(text), None, activate=lambda k=key: self.set_sort(k), active=lambda k=key: self.sort_key == k)
        more = WinMenu(parent_row=True)
        more.item(tr('Size'), None, activate=lambda: self.set_sort('size'), active=lambda: self.sort_key == 'size')
        menu.item(tr('More'), None, submenu=more)
        menu.separator()
        menu.item(tr('Ascending'), None, activate=lambda: self.set_sort(desc=False), active=lambda: not self.sort_desc)
        menu.item(tr('Descending'), None, activate=lambda: self.set_sort(desc=True), active=lambda: self.sort_desc)
        menu.separator()
        group = WinMenu(parent_row=True)
        group.item(tr('(None)'), None, active=lambda: True)
        menu.item(tr('Group by'), None, submenu=group)
        return menu

    def build_more_menu(self):
        menu = WinMenu(marks=False)
        folded = lambda: self.folded
        for text, glyph, action in (('Cut', 'win11-menu-cut', 'view.cut'), ('Copy', 'win11-menu-copy', 'view.copy'),
                                    ('Paste', 'win11-menu-paste', 'view.paste'), ('Rename', 'win11-menu-rename', 'view.rename'),
                                    ('Share', 'win11-menu-share', 'view.open-with-other-application'),
                                    ('Delete', 'win11-menu-delete', 'view.move-to-trash')):
            menu.item(tr(text), glyph, activate=lambda a=action: self.act(a), visible=folded)
        menu.separator(visible=folded)
        menu.item(tr('Pin to Quick access'), 'win11-menu-pin', activate=lambda: self.slot_act('slot.bookmark-current-directory'),
                  visible=lambda: self.views.special is None)
        menu.separator()
        menu.item(tr('Select all'), 'win11-menu-selectall', activate=lambda: self.act('view.select-all'))
        menu.item(tr('Select none'), 'win11-menu-selectnone', activate=self.select_none)
        menu.item(tr('Invert selection'), 'win11-menu-invert', activate=lambda: self.act('view.invert-selection'))
        menu.separator()
        menu.item(tr('Properties'), 'win11-menu-properties', activate=lambda: self.act('view.current-directory-properties'))
        menu.item(tr('Options'), 'win11-menu-settings', activate=lambda: Gio.Application.get_default().activate_action('preferences', None))
        return menu

    def ensure(self, bar):
        """Install the dropdown buttons in the command bar once per window."""
        if getattr(self.window, '_fenestra_menus', False):
            return
        self.window._fenestra_menus = True
        controls = next((w for w in walk(bar) if GObject.type_name(w.__gtype__) == 'NautilusViewControls'), None)
        self.sort_button = command_button('Sort', 'win11-explorer-sort')
        self.sort_button.set_popover(self.build_sort_menu().popover)
        self.view_button = command_button('View', 'win11-explorer-view')
        self.view_button.set_popover(self.build_view_menu().popover)
        anchor = controls.get_prev_sibling() if controls else None
        if controls:
            controls.set_visible(False)
        bar.insert_child_after(self.sort_button, anchor)
        bar.insert_child_after(self.view_button, self.sort_button)
        self.window._windows_sort_menu = self.sort_button
        more = next((w for w in walk(bar) if isinstance(w, Gtk.MenuButton) and w.get_icon_name() == 'win11-explorer-more'), None)
        if more:
            more.set_menu_model(None)
            more.set_popover(self.build_more_menu().popover)
        # Explorer's "Details" button toggles the Details pane.
        for w in walk(bar):
            if isinstance(w, Gtk.Actionable) and w.get_action_name() == 'view.current-directory-properties':
                w.set_action_name(None)
                w.set_sensitive(True)
                w.connect('clicked', lambda *_: self.toggle_pane('details'))
                self.details_button = w
        if self.pane_mode != 'none':
            GLib.idle_add(lambda: (self.toggle_pane(self.pane_mode, force=True), False)[1])

    # ---- Details / Preview pane --------------------------------------------
    def _install_pane(self):
        if self.pane is not None:
            return True
        split = next((w for w in walk(self.window) if GObject.type_name(w.__gtype__) == 'AdwOverlaySplitView'), None)
        if split is None:
            return False
        content = split.get_content()
        box = Gtk.Box()
        split.set_content(box)
        content.set_hexpand(True)
        box.append(content)
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.add_css_class('fenestra-infopane-sep')
        box.append(sep)
        self.pane = InfoPane()
        box.append(self.pane)
        self.pane_sep = sep
        return True

    def toggle_pane(self, mode, force=False):
        new = mode if force or self.pane_mode != mode else 'none'
        self.pane_mode = new
        self.views.pane = new
        self.views.save()
        if new == 'none' and self.pane is None:
            return
        if not self._install_pane():
            return
        self.pane.set_visible(new != 'none')
        self.pane_sep.set_visible(new != 'none')
        if hasattr(self, 'details_button'):
            (self.details_button.add_css_class if new == 'details' else self.details_button.remove_css_class)('fenestra-cmd-on')
        self.pane.mode = new
        self.update_pane()

    def watch_selection(self):
        view = self.item_view()
        model = view.get_model() if view else None
        if model is not self.selection_model:
            if self.selection_model is not None and getattr(self, '_sel_handler', None):
                try:
                    self.selection_model.disconnect(self._sel_handler)
                except TypeError:
                    pass
            self.selection_model = model
            self._sel_handler = model.connect('selection-changed', lambda *_: self.update_pane()) if model else None
        self.update_pane()

    def selected_files(self):
        model = self.selection_model
        files = []
        if model is None:
            return files
        bits = model.get_selection()
        n = bits.get_size()
        for i in range(min(n, 200)):
            item = model.get_item(bits.get_nth(i))
            if isinstance(item, Gtk.TreeListRow):
                item = item.get_item()
            nfile = item.get_property('file') if item is not None and item.find_property('file') else None
            if nfile is not None and hasattr(nfile, 'get_location'):
                files.append(nfile.get_location())
        return files

    def update_pane(self):
        if self.pane is None or not self.pane.get_visible():
            return
        slot = self.slot()
        folder = slot.get_property('location') if slot else None
        self.pane.show_files(self.selected_files(), folder)

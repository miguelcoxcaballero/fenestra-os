# SPDX-License-Identifier: GPL-3.0-or-later
"""Explorer layer for Nautilus' file chooser (the FileChooser portal dialog other apps get when
they open or save a file), laid out as the classic open / save dialog measured in
design/reference/measurements.json (file_dialog_save, file_dialog_open, file_dialog_menus).
The layout comes from the UI overlay (nautilus-file-chooser.ui) and the "Explorer open / save
dialog" block of gtk.css; this module does what they cannot express: labels and their
translations, the navigation row (address box with refresh, search text), the navigation pane
(Explorer's entries, order and pins), the Details columns, the Organize menu, the Open layout
and "Hide folders". For the test bench (tests/explorer-dialogs/), FENESTRA_CHOOSER_SHOT=NAME
asks the session's screenshot probe for NAME-<n> once a dialog is up."""
import os
import re

import gi

gi.require_version('Nautilus', '4.1')
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, GObject, Gtk, Nautilus, Pango  # noqa: E402
from fenestra_sidebar import FenestraSidebar, tr  # noqa: E402

import json

SHOT = os.environ.get('FENESTRA_CHOOSER_SHOT')
SHOT_REQUESTS = os.environ.get('SHOTQA_REQ', '/tmp/shotreq')
# Windows' common item dialog opens at 628 x 474 (outer, 1 px frame included) in any app that never
# resized it (Edge's and Brave's Save as, Paint's Open; reference-shots/filedialog/*-150-edge-*, 942 x 711
# physical px at 150 %); GTK draws the frame outside the content (window.win11-chooser box-shadow),
# so the content is 626 x 472. Notepad's 946 x 533 (design/reference/dialogs.md) is a size Notepad
# remembers. Like Windows, the size the user leaves a dialog at is remembered (STATE), and the size
# stock Nautilus saved before the Explorer layer (initial-size-file-chooser) is ignored.
SIZE = (626, 472)
STATE = os.path.join(GLib.get_user_state_dir(), 'fenestra', 'file-dialog.json')
# Windows lays the dialog out per DPI, not as the 100 % layout scaled: at 150 % the title bar is 43 px,
# the navigation row 74, the command bar 48 + 1 and the buttons strip 99 (physical px), where 1.5 x the
# 100 % layout gives 45, 82.5, 46.5 and 87. The scale class selects those metrics in gtk.css.
SCALES = ((1.375, 1.625, 'fenestra-dlg-150'),)
# Details columns (reference header dividers at x 432, 576, 696, 776 of the window).
COLUMNS = {'name': 273, 'date': 144, 'type': 120, 'size': 80}
SIZE_TEXT = re.compile(r'^[\d.,]+\s*\S*$')  # "1 KB", "5 bytes", "3 items" (dates have ':' and '/')
# Nautilus says Replace when the name exists; Windows keeps Save and asks on confirm.
ACCEPT = {'_Save': '_Save', '_Open': '_Open', '_Select': '_Select', 'Save': '_Save', 'Open': '_Open',
          '_Replace': '_Save', 'Replace': '_Save'}


def walk(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


def kind(widget):
    return GObject.type_name(widget.__gtype__)


def is_chooser(window):
    return kind(window) == 'NautilusFileChooser'


def find(root, pred):
    return next((w for w in walk(root) if pred(w)), None)


def by_id(root, name):
    return find(root, lambda w: w.get_buildable_id() == name)


def by_action(root, action):
    return find(root, lambda w: isinstance(w, Gtk.Actionable) and w.get_action_name() == action)


class Chooser:
    """One open / save dialog."""

    def __init__(self, window):
        self.window = window
        self.ticks = 0
        self.slot = None
        self.sidebar = FenestraSidebar(window, walk)
        # The dialog's navigation pane order: Desktop, Downloads, Documents, Pictures, Music, Videos.
        order = {'user-desktop': 10, 'folder-download': 11, 'folder-documents': 12, 'folder-pictures': 13,
                 'folder-music': 14, 'folder-videos': 15}
        self.sidebar.entries = {uri: (order.get(icon, rank) if 10 <= rank < 50 else rank, label, icon)
                                for uri, (rank, label, icon) in self.sidebar.entries.items()}
        self.default_size()
        self.window.connect('realize', self.scale_class)
        self.window.connect('notify::scale-factor', self.scale_class)
        if self.window.get_realized():
            self.scale_class()
        self.labels()
        self.navigation()
        self.commandbar()
        self.organize()
        self.bottom()
        GLib.timeout_add(100, self.tick)

    # -- window ------------------------------------------------------------------------------
    def default_size(self):
        """Windows' default size, or the size the user left the last dialog at (STATE)."""
        size = SIZE
        try:
            with open(STATE) as f:
                saved = json.load(f).get('size')
            if isinstance(saved, list) and len(saved) == 2 and all(isinstance(v, int) and 200 <= v <= 8000 for v in saved):
                size = tuple(saved)
        except (OSError, ValueError, AttributeError):
            pass
        self.window.set_default_size(*size)
        # Nautilus applies its own remembered size after the template: apply ours again before mapping.
        GLib.idle_add(lambda: (self.window.set_default_size(*size), GLib.SOURCE_REMOVE)[1], priority=GLib.PRIORITY_HIGH)
        self.window.connect('realize', lambda w: w.set_default_size(*size))
        # The dialog is often mapped before this layer attaches; Nautilus then restores its own size
        # (initial-size-file-chooser) while it settles: keep ours for the first 1.5 s (tick()).
        self.want_size = size
        self.window.connect('close-request', self.save_size)
        self.window.connect('unrealize', self.save_size)

    def save_size(self, *_):
        hidden = by_id(self.window, 'fenestra_hide_folders')
        if hidden is not None and hidden.get_active():
            return False  # the folded "Hide folders" height is not a size to reopen at
        width, height = self.window.get_width(), self.window.get_height()
        if width < 200 or height < 200 or self.window.is_maximized():
            return False
        try:
            os.makedirs(os.path.dirname(STATE), exist_ok=True)
            with open(STATE + '.tmp', 'w') as f:
                json.dump({'size': [width, height]}, f)
            os.replace(STATE + '.tmp', STATE)
        except OSError:
            pass
        return False

    def scale_class(self, *_):
        """fenestra-dlg-150 etc. on the window: Windows' per-DPI layout (see SCALES)."""
        surface = self.window.get_surface()
        scale = surface.get_scale() if surface is not None and hasattr(surface, 'get_scale') else self.window.get_scale_factor()
        for lo, hi, css in SCALES:
            (self.window.add_css_class if lo <= scale < hi else self.window.remove_css_class)(css)
        if surface is not None and not getattr(self, '_scale_watch', False):
            self._scale_watch = True
            surface.connect('notify::scale', self.scale_class)

    def labels(self):
        for w in walk(self.window):
            if isinstance(w, Gtk.Label) and any(w.has_css_class(c) for c in ('win11-cmd-label', 'win11-search-label')):
                w.set_label(tr(w.get_label()))
            elif isinstance(w, Gtk.Button) and w.has_css_class('win11-dialog-button') and w.get_label() == 'Cancel':
                w.set_label(tr('Cancel'))
            elif w.get_tooltip_text():
                w.set_tooltip_text(tr(w.get_tooltip_text()))
        hide = by_id(self.window, 'fenestra_hide_folders')
        if hide:
            hide.connect('toggled', self.hide_folders)
            self.hide_label(hide)
        # Mnemonics are always shown, as in the reference dialog (Alt still toggles them).
        self.window.set_mnemonics_visible(True)

    # -- navigation row ----------------------------------------------------------------------
    def navigation(self):
        toolbar = by_id(self.window, 'toolbar')
        if not toolbar:
            return
        for name, icon, css in (('back_button', 'win11-explorer-back', 'fenestra-dlg-back'),
                                ('forward_button', 'win11-explorer-forward', 'fenestra-dlg-forward')):
            button = by_id(toolbar, name)
            if button:
                button.set_icon_name(icon)
                button.add_css_class(css)
        history = by_id(toolbar, 'history_controls')
        if history:
            for box in walk(history):
                if isinstance(box, Gtk.Box):
                    box.set_spacing(0)
            start = history.get_parent().get_parent() if history.get_parent() else None
            if isinstance(start, Gtk.Box):
                start.set_spacing(0)
        up = by_action(toolbar, 'slot.up')
        if up:
            up.add_css_class('fenestra-dlg-up')
            up.set_valign(Gtk.Align.CENTER)
            # "Recent locations" (the chevron between Forward and Up): the folders visited in this
            # dialog, newest first, as Windows lists them.
            self.recent = []
            self.recent_menu = Gio.Menu()
            recent = Gtk.MenuButton(icon_name='win11-explorer-chevron-down', menu_model=self.recent_menu)
            recent.set_tooltip_text(tr('Recent locations'))
            recent.add_css_class('fenestra-dlg-recent')
            recent.set_valign(Gtk.Align.CENTER)
            recent.set_sensitive(False)
            self.recent_button = recent
            parent = up.get_parent()
            if isinstance(parent, Gtk.Box):
                parent.insert_child_after(recent, up.get_prev_sibling()) if up.get_prev_sibling() else parent.prepend(recent)
            pop = recent.get_popover()
            if pop is not None:
                pop.add_css_class('fenestra-dlg-menu')
                pop.set_has_arrow(False)
                pop.set_halign(Gtk.Align.START)
        path = by_id(toolbar, 'path_bar')
        refresh = by_action(toolbar, 'slot.reload')
        if path:
            path.add_css_class('fenestra-dlg-address')
            # The address box: [folder icon] › crumbs ... [history ▾] [refresh], as one framed box.
            lead = Gtk.Box()
            lead.add_css_class('fenestra-dlg-lead')
            self.lead_icon = Gtk.Image.new_from_icon_name('folder')
            self.lead_icon.set_pixel_size(16)
            sep = Gtk.Label(label='›')
            sep.add_css_class('fenestra-dlg-crumb-sep')
            lead.append(self.lead_icon)
            lead.append(sep)
            path.prepend(lead)
            bar = find(toolbar, lambda w: kind(w) == 'AdwHeaderBar')
            if refresh and bar is not None and isinstance(path, Gtk.Box):
                # Refresh sits at the right end of the address box in the reference.
                bar.remove(refresh)
                refresh.add_css_class('fenestra-dlg-refresh')
                path.append(refresh)
            for w in walk(path):
                if isinstance(w, Gtk.MenuButton):
                    w.set_icon_name('win11-explorer-chevron-down')
                    w.add_css_class('fenestra-dlg-history')
        header = by_id(toolbar, 'header_toolbar')
        if header:
            header.set_spacing(12)  # address box to search box
        search = by_id(toolbar, 'search_button')
        if search:
            search.add_css_class('fenestra-dlg-search')
            search.set_size_request(202, -1)
            glass = find(search, lambda w: isinstance(w, Gtk.Image))
            if glass:
                glass.set_pixel_size(16)

    def crumbs(self):
        """Windows shows the folder from its library root: "› Documentos", not "Home / Documentos"."""
        path = by_id(self.window, 'path_bar')
        if not path:
            return
        crumbs = [w for w in walk(path) if isinstance(w, Gtk.Button) and w.has_css_class('nautilus-path-button')]
        for w in walk(path):
            if isinstance(w, Gtk.Label) and w.has_css_class('dim-label') and w.get_label() == '/':
                w.set_label('›')
                w.add_css_class('fenestra-dlg-crumb-sep')
                w.remove_css_class('dim-label')
        for i, crumb in enumerate(crumbs):
            box = crumb.get_parent()
            hidden = i == 0 and len(crumbs) > 1
            if box is not None and box.get_visible() == hidden:
                box.set_visible(not hidden)
            for w in walk(crumb):
                if isinstance(w, Gtk.Image):
                    w.set_visible(False)
                if isinstance(w, Gtk.Label):
                    w.remove_css_class('dim-label')
                    if not getattr(w, '_fenestra_weight', False):
                        w._fenestra_weight = True
                        attrs = Pango.AttrList()
                        attrs.insert(Pango.attr_weight_new(Pango.Weight.NORMAL))
                        w.set_attributes(attrs)
            if i == 1 and box is not None:
                # The crumb after the hidden root starts the box: no separator before it.
                for w in walk(box):
                    if isinstance(w, Gtk.Label) and w.get_label() == '›' and not w.is_ancestor(crumb):
                        w.set_visible(False)

    def location_changed(self, *_):
        location = self.slot.get_property('location') if self.slot else None
        if location is None:
            return
        name = None
        try:
            info = location.query_info('standard::display-name,standard::icon', Gio.FileQueryInfoFlags.NONE, None)
            name = info.get_display_name()
        except GLib.Error:
            pass
        icon = 'folder'
        home = GLib.get_home_dir()
        special = {home: ('hwin', tr('Home'))}
        for key, glyph in (('DIRECTORY_DESKTOP', 'user-desktop'), ('DIRECTORY_DOCUMENTS', 'folder-documents'),
                           ('DIRECTORY_DOWNLOAD', 'folder-download'), ('DIRECTORY_MUSIC', 'folder-music'),
                           ('DIRECTORY_PICTURES', 'folder-pictures'), ('DIRECTORY_VIDEOS', 'folder-videos')):
            value = GLib.get_user_special_dir(getattr(GLib.UserDirectory, key))
            if value and value != home:
                special[value] = (glyph, None)
        path = location.get_path()
        # The lead icon is the library the folder belongs to (Documentos for Documentos/Proyectos).
        for root, (glyph, label) in sorted(special.items(), key=lambda kv: -len(kv[0])):
            if path and (path == root or path.startswith(root + '/')):
                icon = glyph
                if path == root and label:
                    name = label
                break
        if hasattr(self, 'lead_icon'):
            self.lead_icon.set_from_icon_name(icon)
        if hasattr(self, 'recent_menu'):
            uri = location.get_uri()
            self.recent = [(uri, name or uri)] + [r for r in self.recent if r[0] != uri][:9]
            self.recent_menu.remove_all()
            for target, label in self.recent[1:]:
                self.recent_menu.append(label, Gio.Action.print_detailed_name('slot.open-location', GLib.Variant('s', target)))
            self.recent_button.set_sensitive(len(self.recent) > 1)
        for w in walk(self.window):
            if isinstance(w, Gtk.Label) and w.has_css_class('win11-search-label'):
                w.set_label(tr('Search %s') % name if name else tr('Search'))
        GLib.idle_add(lambda: (self.crumbs(), GLib.SOURCE_REMOVE)[1])

    # -- command bar ------------------------------------------------------------------------
    def commandbar(self):
        organize = by_id(self.window, 'organize_button')
        if organize:
            for w in walk(organize):
                if isinstance(w, Gtk.Image) and w.has_css_class('win11-cmd-chevron'):
                    w.set_from_icon_name('win11-dialog-dropdown-symbolic')  # Windows' small filled triangle
                    w.add_css_class('fenestra-dlg-dropdown')
        controls = by_id(self.window, 'view_controls')
        if controls:
            # Help (?) at the right end of the command bar, as in Windows ("Get help": Files' help).
            parent = controls.get_parent()
            if isinstance(parent, Gtk.Box) and not getattr(self, 'help_button', None):
                self.help_button = Gtk.Button(icon_name='win11-dialog-help', action_name='app.help')
                self.help_button.set_tooltip_text(tr('Get help'))
                self.help_button.add_css_class('fenestra-dlg-help')
                self.help_button.set_valign(Gtk.Align.CENTER)
                parent.insert_child_after(self.help_button, controls)
                controls.set_margin_end(0)
            else:
                controls.set_margin_end(54)
            split = find(controls, lambda w: kind(w) == 'AdwSplitButton')
            main = split.get_first_child() if split else None
            if isinstance(main, Gtk.Button):
                main.add_css_class('fenestra-dlg-view')
                # The reference view button is the icon alone; its menu is the chevron beside it.
                for w in walk(main):
                    if isinstance(w, Gtk.Label) or (isinstance(w, Gtk.Image) and w.has_css_class('win11-cmd-chevron')):
                        w.set_visible(False)
                child = main.get_child()
                if child is not None:
                    child.set_halign(Gtk.Align.CENTER)

    def organize(self):
        """Organize, as in the reference (entries that are Nautilus actions; the rest is left out)."""
        organize = by_id(self.window, 'organize_button')
        if not organize:
            return
        menu = Gio.Menu()
        for section in ((('Cut', 'view.cut', 'win11-menu-cut'), ('Copy', 'view.copy', 'win11-menu-copy'),
                         ('Paste', 'view.paste', 'win11-menu-paste')),
                        (('Select all', 'view.select-all', 'win11-menu-selectall'),),
                        (('Delete', 'view.move-to-trash', 'win11-menu-delete'), ('Rename', 'view.rename', 'win11-menu-rename'),
                         ('Properties', 'view.properties', 'win11-menu-properties')),
                        (('Close', 'window.close', 'win11-menu-cancel'),)):
            part = Gio.Menu()
            for label, action, icon in section:
                item = Gio.MenuItem.new(tr(label), action)
                item.set_attribute_value('hidden-when', GLib.Variant('s', 'action-missing'))
                item.set_attribute_value('accel', GLib.Variant('s', ''))  # the reference menu shows no shortcuts
                if icon:
                    item.set_icon(Gio.ThemedIcon.new(icon))
                part.append_item(item)
            menu.append_section(None, part)
        organize.set_menu_model(menu)
        popover = organize.get_popover()
        if popover:
            popover.add_css_class('fenestra-dlg-menu')
            popover.set_has_arrow(False)
            popover.set_halign(Gtk.Align.START)
            popover.set_offset(0, -2)  # the reference menu overlaps the command bar's bottom line

    # -- bottom -------------------------------------------------------------------------------
    def save_mode(self):
        widget = by_id(self.window, 'filename_widget')
        return bool(widget and widget.get_visible())

    def bottom(self):
        filename = by_id(self.window, 'filename_widget')
        filters = by_id(self.window, 'filters_dropdown')
        accept = by_id(self.window, 'accept_button')
        bar = find(self.window, lambda w: w.has_css_class('win11-commandbar'))
        new_folder = by_id(bar, 'new_folder_button') if bar else None
        stack = by_id(self.window, 'filename_widget')
        if isinstance(stack, Gtk.Stack):
            stack.set_vhomogeneous(False)  # the 23 px entry, not the taller edit button page
            # Windows' file name is always an edit box. Nautilus swaps it for a button (centred
            # name and a pencil) when it loses the focus: that page is drawn exactly like the box
            # (gtk.css .fenestra-name-button), so nothing changes shape; a click edits again.
            stack.set_transition_type(Gtk.StackTransitionType.NONE)
            container = by_id(self.window, 'filename_button_container')
            label = by_id(self.window, 'filename_label')
            pencil = by_id(self.window, 'filename_button_end')
            button = container.get_child() if container is not None else None
            if isinstance(button, Gtk.Button) and label is not None:
                button.add_css_class('fenestra-name-button')
                box = button.get_child()
                if isinstance(box, Gtk.CenterBox) and box.get_center_widget() is label:
                    label.set_xalign(0)
                    label.set_hexpand(True)
                    label.set_halign(Gtk.Align.FILL)
                    box.set_center_widget(None)
                    box.set_start_widget(label)
                if pencil is not None:
                    pencil.set_visible(False)
            undo = by_id(self.window, 'filename_undo_button')
            if undo is not None:   # Windows has no "reset name" arrow over the box
                undo.connect('notify::visible', lambda w, _p: w.get_visible() and w.set_visible(False))
                undo.set_visible(False)
        if self.window.find_property('visible-dialog'):
            self.window.connect('notify::visible-dialog', self.confirm)
        if filename:
            filename.connect('notify::visible', lambda *_: self.sync_mode())
        if accept:
            accept.connect('notify::label', lambda *_: self.sync_accept())
            # The accept button is the dialog's default button (Windows' blue-bordered Save / Open).
            self.window.set_default_widget(accept)
        if new_folder:
            # The reference Open dialog has New folder too (view.new-folder works in both modes).
            new_folder.connect('notify::visible', lambda w, _p: w.set_visible(True) if not w.get_visible() else None)
            new_folder.set_visible(True)
        if filters:
            filters.connect('notify::visible', lambda *_: self.sync_accept())
        self.sync_mode()

    def confirm(self, *_):
        """Nautilus' "Replace When Saving?" as Windows' "Confirm Save As": the name, the question,
        Yes and No (No is the default button), Yes on the left."""
        dialog = self.window.get_property('visible-dialog')
        if dialog is None or not hasattr(dialog, 'has_response') or dialog.has_css_class('fenestra-confirm'):
            return
        ids = [r for r in ('replace', 'cancel') if dialog.has_response(r)]
        if len(ids) != 2:
            return
        entry = by_id(self.window, 'filename_entry')
        name = entry.get_text() if entry else ''
        dialog.add_css_class('fenestra-confirm')
        dialog.set_heading(tr('Confirm Save As'))
        dialog.set_body(tr('{0} already exists.\nDo you want to replace it?').format(name))
        dialog.set_response_label('replace', '_' + tr('Yes'))
        dialog.set_response_label('cancel', '_' + tr('No'))
        try:
            import gi as _gi
            _gi.require_version('Adw', '1')
            from gi.repository import Adw
            dialog.set_response_appearance('replace', Adw.ResponseAppearance.DEFAULT)
        except (ValueError, ImportError):
            pass
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')

        if hasattr(dialog, 'set_content_width'):
            dialog.set_content_width(340)
            dialog.set_follows_content_size(False) if hasattr(dialog, 'set_follows_content_size') else None

        def order():
            found = {}
            for w in walk(dialog):
                if isinstance(w, Gtk.Label):
                    text = (w.get_text() or '')
                    if text in (tr('Yes'), tr('No')):
                        button = w.get_ancestor(Gtk.Button)
                        if button is not None:
                            found[text] = button
                    else:
                        if text == tr('Confirm Save As'):
                            w.add_css_class('fenestra-confirm-title')
                        w.set_xalign(0)
                        w.set_halign(Gtk.Align.FILL)
                        w.set_justify(Gtk.Justification.LEFT)
            yes, no = found.get(tr('Yes')), found.get(tr('No'))
            if yes is not None and no is not None and yes.get_parent() is no.get_parent():
                # Windows: Yes, then No. The dialog lays its responses out in its own order: mirror the row.
                yes.get_parent().set_direction(Gtk.TextDirection.RTL)
                for b in (yes, no):
                    b.set_direction(Gtk.TextDirection.LTR)
            return GLib.SOURCE_REMOVE
        GLib.idle_add(order)

    def sync_mode(self):
        save = self.save_mode()
        caption = by_id(self.window, 'filter_caption')
        name_caption = by_id(self.window, 'filename_caption')
        entry = by_id(self.window, 'filename_entry')
        filters = by_id(self.window, 'filters_dropdown')
        if name_caption:
            name_caption.set_label('_' + tr('File name:'))
            if entry:
                name_caption.set_mnemonic_widget(entry)
        if caption:
            caption.set_label('_' + (tr('Save as type:') if save else tr('Files of type:')))
            if filters:
                caption.set_mnemonic_widget(filters)
        if filters:
            # Save: the type list spans the fields area; Open: a 188 px list right of the file name.
            filters.set_hexpand(save)
            filters.set_size_request(-1 if save else 188, -1)
        layouts = by_id(self.window, 'bottom_toolbar')
        if layouts is not None and layouts.get_layout_name() != 'narrow':
            layouts.set_layout_name('wide' if save else 'wide-open')
        for w in walk(self.window):  # the layout just shown may have its own Cancel
            if isinstance(w, Gtk.Button) and w.has_css_class('win11-dialog-button') and w.get_label() == 'Cancel':
                w.set_label(tr('Cancel'))
        self.window.remove_css_class('fenestra-dlg-open' if save else 'fenestra-dlg-save')
        self.window.add_css_class('fenestra-dlg-save' if save else 'fenestra-dlg-open')
        self.sync_accept()

    def sync_accept(self):
        accept = by_id(self.window, 'accept_button')
        if not accept:
            return
        label = accept.get_label() or ''
        if label in ACCEPT:
            want = tr(ACCEPT[label])
            if label == '_Select':
                filters = by_id(self.window, 'filters_dropdown')
                # Open file: "Abrir"; select folder (no file filter): Nautilus' "Select".
                want = tr('_Open') if filters and filters.get_visible() else tr('_Select')
            if want != label:
                accept.set_label(want)
                accept.set_use_underline(True)

    def hide_label(self, button):
        label = find(button, lambda w: isinstance(w, Gtk.Label))
        if label:
            label.set_label(tr('Browse Folders') if button.get_active() else tr('Hide Folders'))
        icon = find(button, lambda w: isinstance(w, Gtk.Image))
        if icon:  # ^ while the folders show, v once they are hidden
            (icon.remove_css_class if button.get_active() else icon.add_css_class)('fenestra-dlg-flip')

    def hide_folders(self, button):
        """Windows' "Hide folders": only the name and type fields and the buttons stay."""
        hidden = button.get_active()
        self.hide_label(button)
        for name in ('toolbar', 'split_view'):
            widget = by_id(self.window, name)
            if widget:
                widget.set_visible(not hidden)
        bar = find(self.window, lambda w: w.has_css_class('win11-commandbar'))
        if bar:
            bar.set_visible(not hidden)
        width, height = self.window.get_width(), self.window.get_height()
        if hidden:
            self._height = height
            self._min = self.window.get_size_request()
            self.window.set_size_request(self._min[0], -1)  # the template's 348 px minimum is for the folders
            GLib.idle_add(self.fit_height)
        else:
            self.window.set_size_request(*getattr(self, '_min', (-1, -1)))
            self.window.set_default_size(width, getattr(self, '_height', SIZE[1]))

    def fit_height(self):
        """With the folders hidden the dialog is its title bar over the name / type fields and buttons."""
        width = self.window.get_width()
        title = find(self.window, lambda w: w.has_css_class('win11-dialog-titlebar'))
        bottom = by_id(self.window, 'bottom_toolbar')
        if title and bottom:
            height = title.measure(Gtk.Orientation.VERTICAL, width)[1] + bottom.measure(Gtk.Orientation.VERTICAL, width)[1]
            self.window.set_default_size(width, height)
        return GLib.SOURCE_REMOVE

    # -- slot: navigation pane, Details view ---------------------------------------------------
    def tick(self):
        """Runs until the slot exists, then follows it (Nautilus builds the view lazily)."""
        if self.window.get_root() is None:
            return GLib.SOURCE_REMOVE
        self.ticks += 1
        want = getattr(self, 'want_size', None)
        if want and self.ticks <= 15 and not self.window.is_maximized() and \
                (self.window.get_width(), self.window.get_height()) != want:
            hidden = by_id(self.window, 'fenestra_hide_folders')
            if hidden is None or not hidden.get_active():
                self.window.set_default_size(*want)
        container = by_id(self.window, 'slot_container')
        slot = container.get_child() if container else None
        if slot is not None and slot is not self.slot and slot.find_property('location'):
            self.slot = slot
            slot.connect('notify::location', self.location_changed)
            slot.connect('notify::location', lambda *_: GLib.timeout_add(150, self.view))
            self.location_changed()
        self.pane()
        if self.window.get_mapped() and not getattr(self, 'mnemonics', False):
            self.mnemonics = True
            self.window.set_mnemonics_visible(True)
        if self.slot is not None and self.slot.get_property('location') is not None:
            self.view()
            self.crumbs()
            if self.ticks > 40:
                return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE if self.ticks < 100 else GLib.SOURCE_REMOVE

    def pane(self):
        sidebar = by_id(self.window, 'places_sidebar')
        if not sidebar:
            return
        try:
            self.sidebar.refresh()
        except TypeError:
            pass  # the part after the pane needs an Explorer window (active-slot)
        for w in walk(sidebar):
            if isinstance(w, Gtk.ScrolledWindow) and w.get_overlay_scrolling():
                w.set_overlay_scrolling(False)
                w.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
            if isinstance(w, Gtk.ScrolledWindow) and self.ticks < 30:
                # The pane opens at its top (Home first) while the selected folder is visible there.
                adj = w.get_vadjustment()
                row = find(w, lambda r: isinstance(r, Gtk.ListBoxRow) and r.is_selected())
                if row is not None and adj.get_value() > 0:
                    ok, b = row.compute_bounds(w.get_child())
                    if ok and b.get_y() + b.get_height() <= adj.get_page_size():
                        adj.set_value(0)
            if isinstance(w, Gtk.Box) and getattr(w, '_fenestra_spacing', False) and w.get_spacing() != 0:
                w.set_spacing(0)  # icon, label (4 px margin) and pin fill the 137 px row
            if isinstance(w, Gtk.Label) and w.has_css_class('sidebar-label') and w.get_ellipsize() != Pango.EllipsizeMode.END:
                w.set_ellipsize(Pango.EllipsizeMode.END)  # long names must not widen the pane

    def view(self):
        slot = self.slot
        if slot is None:
            return GLib.SOURCE_REMOVE
        if not find(slot, lambda w: kind(w) == 'NautilusListView'):
            # The Explorer's view ids (fenestra_views.py): 1 = list, shown as the details view.
            self.window.add_css_class('windows-view-details')
            slot.activate_action('slot.files-view-mode', GLib.Variant('u', 1))
            return GLib.SOURCE_REMOVE
        for cv in (w for w in walk(slot) if isinstance(w, Gtk.ColumnView)):
            columns = cv.get_columns()
            for i in range(columns.get_n_items()):
                column = columns.get_item(i)
                key = column.get_id() or ''
                title = column.get_title() or ''
                if key == 'starred' or title == '':
                    column.set_visible(False)
                    continue
                which = {'name': 'name', 'date_modified': 'date', 'type': 'type', 'size': 'size'}.get(key)
                if which is None:
                    which = {'Name': 'name', 'Modified': 'date', 'Type': 'type', 'Size': 'size'}.get(title)
                if which is None:
                    continue
                want = {'name': tr('Name'), 'date': tr('Date modified'), 'type': tr('Type'), 'size': tr('Size')}[which]
                if title != want:
                    column.set_title(want)
                if not getattr(column, '_fenestra_cells', False):
                    column._fenestra_cells = True
                    factory = column.get_factory()
                    if factory is not None:
                        factory.connect_after('bind', lambda _f, item: self.cell(item.get_child()))
                if column.get_fixed_width() != COLUMNS[which]:
                    column.set_fixed_width(COLUMNS[which])
                    column.set_expand(False)
                    column.set_resizable(True)
        for cell in (w for w in walk(slot) if kind(w) in ('NautilusLabelCell', 'NautilusNameCell')):
            self.cell(cell)
        for page in (w for w in walk(slot) if kind(w) == 'AdwStatusPage'):
            # An empty folder: Windows writes one line under the column headers, no picture.
            if page.get_icon_name():
                page.set_icon_name(None)
            want = tr('No items match your search.')
            if page.get_title() != want:
                page.set_title(want)
                page.set_description(None)
            page.add_css_class('fenestra-dlg-empty')
            box = find(page, lambda w: isinstance(w, Gtk.Box))
            if box is not None and box.get_valign() != Gtk.Align.START:
                box.set_valign(Gtk.Align.START)
        return GLib.SOURCE_REMOVE

    @staticmethod
    def cell(cell):
        """Reference alignment: dates left, sizes right; the name 1 px after its 16 px icon."""
        if cell is None:
            return
        if kind(cell) == 'NautilusNameCell':
            for box in walk(cell):
                if isinstance(box, Gtk.Box) and box.get_spacing():
                    box.set_spacing(0)
            return
        for label in walk(cell):
            if isinstance(label, Gtk.Label) and label.has_css_class('numeric'):
                size = SIZE_TEXT.match(label.get_label() or '') is not None
                label.set_xalign(1 if size else 0)
                label.set_margin_end(2 if size else 0)


class ChooserWatcher:
    """Started at import: Nautilus may only instantiate the provider below when it needs a menu."""

    def __init__(self):
        self.count = 0
        GLib.idle_add(self._start)

    def _start(self):
        # The chooser is not added to the GtkApplication (no window-added): watch all toplevels.
        self.toplevels = Gtk.Window.get_toplevels()
        self.toplevels.connect('items-changed', lambda model, *_: self._scan(model))
        self._scan(self.toplevels)
        return GLib.SOURCE_REMOVE

    def _scan(self, model):
        for i in range(model.get_n_items()):
            window = model.get_item(i)
            if is_chooser(window) and not getattr(window, '_fenestra_chooser', None):
                window._fenestra_chooser = True
                self._attach(window)

    def _attach(self, window):
        if window.has_css_class('win11-chooser'):  # the UI overlay is active (Nautilus 51)
            window._fenestra_chooser = Chooser(window)
        if SHOT and os.path.isdir(SHOT_REQUESTS):
            self.count += 1
            name = f'{SHOT}-{self.count}'
            GLib.timeout_add(3000, lambda: (open(os.path.join(SHOT_REQUESTS, name), 'w').close(), GLib.SOURCE_REMOVE)[1])


WATCHER = ChooserWatcher()


class FenestraChooser(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = 'FenestraChooserLayer'

    def get_file_items(self, *args):
        return []

    def get_background_items(self, *args):
        return []

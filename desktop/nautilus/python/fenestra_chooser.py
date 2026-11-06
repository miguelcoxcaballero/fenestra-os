# SPDX-License-Identifier: GPL-3.0-or-later
"""Explorer layer for Nautilus' file chooser (the FileChooser portal dialog other apps get when
they open or save a file). Layout comes from the UI overlay (nautilus-file-chooser.ui); this
module only fills in the labels the layout adds. For the test bench (tests/explorer-dialogs/),
FENESTRA_CHOOSER_SHOT=NAME asks the session's screenshot probe for NAME-<n> once a dialog is up."""
import os

import gi

gi.require_version('Nautilus', '4.1')
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, GObject, Gtk, Nautilus  # noqa: E402
from fenestra_sidebar import tr  # noqa: E402

SHOT = os.environ.get('FENESTRA_CHOOSER_SHOT')
SHOT_REQUESTS = '/tmp/shotreq'


def walk(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


def is_chooser(window):
    return GObject.type_name(window.__gtype__) == 'NautilusFileChooser'


def find(window, pred):
    return next((w for w in walk(window) if pred(w)), None)


def setup(window):
    """Labels, the Organize menu and the Details view: what the overlay cannot express."""
    for w in walk(window):
        if isinstance(w, Gtk.Label) and any(w.has_css_class(c) for c in
                                            ('win11-cmd-label', 'win11-chooser-caption', 'win11-search-label')):
            w.set_label(tr(w.get_label()))
        elif w.get_tooltip_text():
            w.set_tooltip_text(tr(w.get_tooltip_text()))
        elif isinstance(w, Gtk.Button) and w.get_buildable_id() == 'cancel_button':
            w.set_label(tr('Cancel'))
    # Open dialogs call the filter "Files of type"; save dialogs "Save as type".
    caption = find(window, lambda w: isinstance(w, Gtk.Label) and w.get_buildable_id() == 'filter_caption')
    new_folder = find(window, lambda w: isinstance(w, Gtk.Button) and w.get_buildable_id() == 'new_folder_button')

    def sync_caption(*_):
        if caption:
            caption.set_label(tr('Save as type:') if new_folder and new_folder.get_visible() else tr('Files of type:'))
    if new_folder:
        new_folder.connect('notify::visible', sync_caption)
    sync_caption()
    organize = find(window, lambda w: isinstance(w, Gtk.MenuButton) and w.get_buildable_id() == 'organize_button')
    if organize:
        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(tr('New folder'), 'view.new-folder')
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(tr('Select all'), 'view.select-all')
        section.append(tr('Show hidden files'), 'view.show-hidden-files')
        menu.append_section(None, section)
        organize.set_menu_model(menu)
    # Details view, as the reference dialogs open (the Explorer's own view is not changed).
    window._fenestra_view_tries = 0
    GLib.timeout_add(100, details_view, window)


def details_view(window):
    window._fenestra_view_tries += 1
    if window._fenestra_view_tries > 100:  # 10 s without a location: leave the view alone
        return GLib.SOURCE_REMOVE
    container = find(window, lambda w: w.get_buildable_id() == 'slot_container')
    slot = container.get_child() if container else None
    if slot is None or slot.get_property('location') is None:
        return GLib.SOURCE_CONTINUE  # the slot arrives once the dialog has a location
    # The Explorer's view ids (fenestra_views.py): 1 = list, shown as the details view.
    window.add_css_class('windows-view-details')
    slot.activate_action('slot.files-view-mode', GLib.Variant('u', 1))
    return GLib.SOURCE_REMOVE


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
            if is_chooser(window) and not getattr(window, '_fenestra_chooser', False):
                window._fenestra_chooser = True
                self._attach(window)

    def _attach(self, window):
        if window.has_css_class('win11-chooser'):  # the UI overlay is active (Nautilus 51)
            setup(window)
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

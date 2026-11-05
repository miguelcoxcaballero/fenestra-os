"""Windows 11 folder icons: empty folder vs folder with files (white sheet).

Sets metadata::custom-icon on each folder Nautilus shows, and keeps it in sync
when the folder gains or loses items. User-chosen custom icons and the special
XDG folders (Documents, Downloads, ...) are left untouched.
"""
import os

from gi.repository import Gio, GLib

def _asset(name):
    for base in (os.path.join(GLib.get_user_data_dir(), 'fenestra', 'assets'), '/usr/share/fenestra/assets'):
        path = os.path.join(base, 'folders', name)
        if os.path.exists(path):
            return path
    return os.path.join('/usr/share/fenestra/assets/folders', name)


EMPTY = Gio.File.new_for_path(_asset('folder-empty.png')).get_uri()
FULL = Gio.File.new_for_path(_asset('folder-full.png')).get_uri()
OURS = (EMPTY, FULL)
ATTR = 'metadata::custom-icon'
MAX_MONITORS = 4000


def special_dirs():
    dirs = {GLib.get_home_dir()}
    for i in range(int(GLib.UserDirectory.N_DIRECTORIES)):
        path = GLib.get_user_special_dir(GLib.UserDirectory(i))
        if path:
            dirs.add(path)
    return dirs


def has_items(path):
    try:
        with os.scandir(path) as it:
            return next(it, None) is not None
    except OSError:
        return None


class FolderIcons:
    def __init__(self):
        self.special = special_dirs()
        self.monitors = {}

    def sync(self, gfile, current=None):
        path = gfile.get_path()
        if not path or path in self.special:
            return
        if current is None:
            try:
                info = gfile.query_info(ATTR, Gio.FileQueryInfoFlags.NONE, None)
                current = info.get_attribute_string(ATTR)
            except GLib.Error:
                return
        if current and current not in OURS:
            return  # icon chosen by the user
        full = has_items(path)
        if full is None:
            return
        wanted = FULL if full else EMPTY
        if current != wanted:
            info = Gio.FileInfo()
            info.set_attribute_string(ATTR, wanted)
            gfile.set_attributes_async(info, Gio.FileQueryInfoFlags.NONE, GLib.PRIORITY_LOW, None, self._done)
        self.watch(gfile)

    def _done(self, gfile, result):
        try:
            gfile.set_attributes_finish(result)
        except GLib.Error:
            pass

    def watch(self, gfile):
        path = gfile.get_path()
        if path in self.monitors or len(self.monitors) >= MAX_MONITORS:
            return
        try:
            monitor = gfile.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        except GLib.Error:
            return
        monitor.connect('changed', self._changed, gfile)
        self.monitors[path] = monitor

    def _changed(self, _monitor, _child, _other, event, gfile):
        if event in (Gio.FileMonitorEvent.CREATED, Gio.FileMonitorEvent.DELETED,
                     Gio.FileMonitorEvent.MOVED_IN, Gio.FileMonitorEvent.MOVED_OUT,
                     Gio.FileMonitorEvent.RENAMED):
            self.sync(gfile)
        elif event == Gio.FileMonitorEvent.UNMOUNTED:
            self.monitors.pop(gfile.get_path(), None)





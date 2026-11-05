"""Fenestra: Windows-11-style empty/full folder icons in Nautilus (logic in /usr/share/fenestra/lib)."""
import os
import sys

import gi
gi.require_version('Nautilus', '4.1')
from gi.repository import GObject, Nautilus

sys.path.insert(0, '/usr/share/fenestra/lib')
from folder_icons import FolderIcons  # noqa: E402

_icons = FolderIcons()


class WindowsFolderIcons(GObject.GObject, Nautilus.InfoProvider):
    def update_file_info(self, file):
        if file.get_uri_scheme() == 'file' and file.is_directory():
            _icons.sync(file.get_location())

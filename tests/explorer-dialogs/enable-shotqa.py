# SPDX-License-Identifier: GPL-3.0-or-later
from gi.repository import Gio
s = Gio.Settings.new("org.gnome.shell")
l = s.get_strv("enabled-extensions")
if "shotqa@local" not in l:
    s.set_strv("enabled-extensions", ["shotqa@local"] + l)
s.set_boolean("disable-user-extensions", False)
Gio.Settings.sync()

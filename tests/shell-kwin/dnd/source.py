# A drag source like a browser's download row: offers one file as text/uri-list, copy/link only.
import gi, sys
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Gio
path, actions = sys.argv[1], sys.argv[2]
def act(app):
    w = Gtk.ApplicationWindow(application=app, title="dragsource", default_width=400, default_height=300)
    b = Gtk.Label(label="DRAG ME"); b.set_hexpand(True); b.set_vexpand(True)
    src = Gtk.DragSource()
    src.set_actions({"copy": Gdk.DragAction.COPY | Gdk.DragAction.LINK, "all": Gdk.DragAction.COPY | Gdk.DragAction.MOVE | Gdk.DragAction.LINK}[actions])
    def prepare(s, x, y):
        f = Gio.File.new_for_path(path)
        return Gdk.ContentProvider.new_union([Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([f]))])
    src.connect("prepare", prepare)
    src.connect("drag-end", lambda s, d, delete: print("drag-end delete=", delete, flush=True))
    src.connect("drag-cancel", lambda s, d, reason: (print("drag-cancel", reason, flush=True), False)[1])
    b.add_controller(src); w.set_child(b); w.present()
app = Gtk.Application(application_id="org.fenestra.DragSrc"); app.connect("activate", act); app.run()

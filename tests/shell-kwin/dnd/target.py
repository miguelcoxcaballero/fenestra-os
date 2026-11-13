# A drop target like a file manager or an upload area: prints the files it is given.
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk
def act(app):
    w = Gtk.ApplicationWindow(application=app, title="droptarget", default_width=400, default_height=300)
    b = Gtk.Label(label="DROP HERE"); b.set_hexpand(True); b.set_vexpand(True)
    t = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
    def drop(t, value, x, y):
        print("dropped", [f.get_path() for f in value.get_files()], "action", t.get_current_drop().get_actions(), flush=True); return True
    t.connect("drop", drop); b.add_controller(t); w.set_child(b); w.present()
app = Gtk.Application(application_id="org.fenestra.DropDst"); app.connect("activate", act); app.run()

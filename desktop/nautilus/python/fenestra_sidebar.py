import os
from pathlib import Path
from gi.repository import Gio,Gtk,GLib

_LANG = (os.environ.get('LANGUAGE') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG') or 'en').split(':')[0][:2]
_L = {
    'es': {'Home': 'Inicio', 'Gallery': 'Galería', 'This PC': 'Este equipo', 'Network': 'Red', 'Desktop': 'Escritorio',
           'Downloads': 'Descargas', 'Documents': 'Documentos', 'Pictures': 'Imágenes', 'Music': 'Música', 'Videos': 'Vídeos'},
}


def tr(text):
    return _L.get(_LANG, {}).get(text, text)

GALLERY = Path(GLib.get_user_data_dir())/'fenestra-explorer'/'Gallery'

class FenestraSidebar:
    def __init__(self,window,walk):
        self.window=window;self.walk=walk;self.lists=set()
        self.home=Path.home()
        U=GLib.UserDirectory
        names=[(U.DIRECTORY_DESKTOP,'Desktop','user-desktop'),(U.DIRECTORY_DOWNLOAD,'Downloads','folder-download'),(U.DIRECTORY_DOCUMENTS,'Documents','folder-documents'),(U.DIRECTORY_PICTURES,'Pictures','folder-pictures'),(U.DIRECTORY_MUSIC,'Music','folder-music'),(U.DIRECTORY_VIDEOS,'Videos','folder-videos')]
        self.entries={}
        for i,(kind,label,icon) in enumerate(names):
            path=GLib.get_user_special_dir(kind)
            if path and path!=str(self.home):self.entries[Path(path).as_uri()]=(i+10,tr(label),icon)
        self.entries[GALLERY.as_uri()]=(1,tr('Gallery'),'folder-pictures')
        self.entries.update({self.home.as_uri():(0,tr('Home'),'folder-home'),'computer:///':(50,tr('This PC'),'computer'),'x-network-view:///':(90,tr('Network'),'network-workgroup'),'network:///':(90,tr('Network'),'network-workgroup')})
    def refresh(self):
        for row in self.walk(self.window):
            if not row.has_css_class('sidebar-row') or not row.find_property('uri'):continue
            uri=row.get_property('uri')
            if uri in ['recent:///','starred:///','trash:///']:
                row.set_visible(False);continue
            if uri in self.entries:
                rank,label,icon=self.entries[uri];row.set_property('label',label)
                row.set_property('start-icon',Gio.ThemedIcon.new(icon))
            parent=row.get_parent()
            if isinstance(parent,Gtk.ListBox) and parent not in self.lists:
                self.lists.add(parent)
                def rank(r):
                    uri=r.get_property('uri') if r.find_property('uri') else None
                    return self.entries.get(uri,(60,''))[0]
                parent.set_sort_func(lambda a,b: (rank(a)>rank(b))-(rank(a)<rank(b)))
        slot=self.window.get_property('active-slot')
        if not slot:return
        location=slot.get_property('location')
        if not location or location.get_path()!=str(self.home):return
        for cell in self.walk(slot):
            if cell.get_css_name()!='widget' or cell.__gtype__.name!='NautilusNameCell':continue
            children=list(self.walk(cell));label=next((c for c in children if isinstance(c,Gtk.Label)),None);image=next((c for c in children if isinstance(c,Gtk.Image)),None)
            entry=next((e for u,e in self.entries.items() if label and e[1]==label.get_text()),None)
            if entry and image:image.set_from_icon_name(entry[2]);image.set_pixel_size(16)

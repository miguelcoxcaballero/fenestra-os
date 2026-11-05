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
PLACES_STAMP = Path(GLib.get_user_config_dir())/'fenestra-explorer'/'places-v1'


def ensure_places():
    """Once per user: Explorer-style quick access (Gallery, Desktop, Downloads,
    Documents, Pictures, Music, Videos) as GTK bookmarks, which is what the
    Files sidebar shows. Later user changes are kept."""
    if PLACES_STAMP.exists():
        return
    try:
        U = GLib.UserDirectory
        GALLERY.mkdir(parents=True, exist_ok=True)
        pictures = GLib.get_user_special_dir(U.DIRECTORY_PICTURES)
        link = GALLERY / Path(pictures or 'Pictures').name
        if pictures and not link.exists() and not link.is_symlink():
            link.symlink_to(pictures)
        wanted = [GALLERY.as_uri()]
        for kind in (U.DIRECTORY_DESKTOP, U.DIRECTORY_DOWNLOAD, U.DIRECTORY_DOCUMENTS,
                     U.DIRECTORY_PICTURES, U.DIRECTORY_MUSIC, U.DIRECTORY_VIDEOS):
            path = GLib.get_user_special_dir(kind)
            if path and path != str(Path.home()) and os.path.isdir(path):
                wanted.append(Path(path).as_uri())
        bookmarks = Path(GLib.get_user_config_dir())/'gtk-3.0'/'bookmarks'
        lines = bookmarks.read_text().splitlines() if bookmarks.exists() else []
        have = {line.split(' ', 1)[0] for line in lines if line.strip()}
        lines += [uri for uri in wanted if uri not in have]
        bookmarks.parent.mkdir(parents=True, exist_ok=True)
        bookmarks.write_text('\n'.join(lines) + '\n')
        PLACES_STAMP.parent.mkdir(parents=True, exist_ok=True)
        PLACES_STAMP.touch()
    except OSError as e:
        print(f'fenestra-explorer: could not set up quick access: {e}')

class FenestraSidebar:
    def __init__(self,window,walk):
        ensure_places()
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

import os
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio,Gtk,GLib

_LANG = (os.environ.get('LANGUAGE') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG') or 'en').split(':')[0][:2]
_L = {
    'es': {'New': 'Nuevo', 'Sort': 'Ordenar', 'View': 'Ver', 'Filter': 'Filtro', 'Details': 'Detalles',
           'Search': 'Buscar', 'Search %s': 'Buscar en %s', 'New folder': 'Nueva carpeta', 'Cut': 'Cortar',
           'Copy': 'Copiar', 'Paste': 'Pegar', 'Rename': 'Cambiar nombre', 'Share': 'Compartir', 'Delete': 'Eliminar',
           'See more': 'Ver más', 'Copy as path': 'Copiar como ruta de acceso', 'Open': 'Abrir', 'Home': 'Inicio', 'Gallery': 'Galería', 'This PC': 'Este equipo', 'Network': 'Red', 'Desktop': 'Escritorio',
           'Downloads': 'Descargas', 'Documents': 'Documentos', 'Pictures': 'Imágenes', 'Music': 'Música', 'Videos': 'Vídeos',
           # file chooser (fenestra_chooser.py)
           'Organize': 'Organizar', 'File name:': 'Nombre:', 'Save as type:': 'Tipo:', 'Files of type:': 'Tipo:',
           'Cancel': 'Cancelar', 'Select all': 'Seleccionar todo', 'Show hidden files': 'Mostrar archivos ocultos',
           'Properties': 'Propiedades', 'Close': 'Cerrar', 'Hide Folders': 'Ocultar carpetas',
           'Browse Folders': 'Examinar carpetas', '_Save': '_Guardar', '_Open': '_Abrir', '_Select': '_Seleccionar',
           'Name': 'Nombre', 'Date modified': 'Fecha de modificación', 'Type': 'Tipo', 'Size': 'Tamaño'},
}


def tr(text):
    return _L.get(_LANG, {}).get(text, text)

GALLERY = Path(GLib.get_user_data_dir())/'fenestra-explorer'/'Gallery'
_OLD_GALLERY = Path(GLib.get_user_data_dir())/'windows-explorer'/'Galería'
if not GALLERY.exists() and _OLD_GALLERY.exists():
    GALLERY = _OLD_GALLERY


def ensure_gallery():
    """Explorer's 'Gallery' entry: a link to Pictures pinned in the sidebar (GTK bookmarks)."""
    try:
        if not GALLERY.exists():
            GALLERY.parent.mkdir(parents=True, exist_ok=True)
            pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or str(Path.home())
            GALLERY.symlink_to(pictures)
        bookmarks = Path(GLib.get_user_config_dir())/'gtk-3.0'/'bookmarks'
        text = bookmarks.read_text() if bookmarks.exists() else ''
        if GALLERY.as_uri() not in text:
            bookmarks.parent.mkdir(parents=True, exist_ok=True)
            bookmarks.write_text(f'{GALLERY.as_uri()} {tr("Gallery")}\n' + text)
    except OSError:
        pass

class FenestraSidebar:
    def __init__(self,window,walk):
        self.window=window;self.walk=walk;self.lists=set()
        self.home=Path.home()
        U=GLib.UserDirectory
        ensure_gallery()
        names=[(U.DIRECTORY_DESKTOP,'Desktop','user-desktop'),(U.DIRECTORY_DOWNLOAD,'Downloads','folder-download'),(U.DIRECTORY_DOCUMENTS,'Documents','folder-documents'),(U.DIRECTORY_PICTURES,'Pictures','folder-pictures'),(U.DIRECTORY_MUSIC,'Music','folder-music'),(U.DIRECTORY_VIDEOS,'Videos','folder-videos')]
        self.entries={}
        for i,(kind,label,icon) in enumerate(names):
            path=GLib.get_user_special_dir(kind)
            if path and path!=str(self.home):self.entries[Path(path).as_uri()]=(i+10,tr(label),icon)
        self.entries[GALLERY.as_uri()]=(1,tr('Gallery'),'folder-pictures')
        self.entries.update({self.home.as_uri():(0,tr('Home'),'hwin'),'computer:///':(50,tr('This PC'),'computer'),'x-network-view:///':(90,tr('Network'),'network-workgroup'),'network:///':(90,tr('Network'),'network-workgroup')})
    def refresh(self):
        for row in self.walk(self.window):
            if not row.has_css_class('sidebar-row') or not row.find_property('uri'):continue
            uri=row.get_property('uri')
            if uri in ['recent:///','starred:///','trash:///'] or (uri or '').startswith(('file:///mnt/','file:///run/media/','file:///media/')):
                row.set_visible(False);continue
            if uri in self.entries:
                rank,label,icon=self.entries[uri];row.set_property('label',label)
                row.set_property('start-icon',Gio.ThemedIcon.new(icon))
                for child in self.walk(row):
                    if isinstance(child,Gtk.Box) and not getattr(child,'_fenestra_spacing',False):
                        child._fenestra_spacing=True;child.set_spacing(6)
                    if isinstance(child,Gtk.Label):
                        child.set_ellipsize(0)
                if 10 <= rank < 50 and not getattr(row,'_fenestra_pin',False):
                    box=next((c for c in self.walk(row) if isinstance(c,Gtk.Box)),None)
                    if box:
                        pin=Gtk.Image.new_from_icon_name('win11-explorer-pin');pin.set_pixel_size(12);pin.add_css_class('fenestra-pin')
                        pin.set_hexpand(True);pin.set_halign(Gtk.Align.END);box.append(pin);row._fenestra_pin=True
            parent=row.get_parent()
            if isinstance(parent,Gtk.ListBox) and parent not in self.lists:
                self.lists.add(parent)
                def rank_of(r):
                    uri=r.get_property('uri') if r.find_property('uri') else None
                    return self.entries.get(uri,(60,''))[0]
                parent.set_sort_func(lambda a,b: (rank_of(a)>rank_of(b))-(rank_of(a)<rank_of(b)))
                # Windows separators: after Home/Gallery and before This PC.
                def header(r, before):
                    cur, prev = rank_of(r), (rank_of(before) if before else None)
                    need = prev is not None and ((prev < 10 <= cur) or (prev < 50 <= cur))
                    if need and not isinstance(r.get_header(), Gtk.Separator):
                        sep = Gtk.Separator(); sep.add_css_class('fenestra-sidebar-sep'); r.set_header(sep)
                    elif not need and r.get_header() is not None:
                        r.set_header(None)
                parent.set_header_func(header)
        slot=self.window.get_property('active-slot')
        if not slot:return
        location=slot.get_property('location')
        if not location or location.get_path()!=str(self.home):return
        for cell in self.walk(slot):
            if cell.get_css_name()!='widget' or cell.__gtype__.name!='NautilusNameCell':continue
            children=list(self.walk(cell));label=next((c for c in children if isinstance(c,Gtk.Label)),None);image=next((c for c in children if isinstance(c,Gtk.Image)),None)
            entry=next((e for u,e in self.entries.items() if label and e[1]==label.get_text()),None)
            if entry and image:image.set_from_icon_name(entry[2]);image.set_pixel_size(16)

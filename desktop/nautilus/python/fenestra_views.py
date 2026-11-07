"""Explorer-style view choices using Nautilus' own models, selection and file actions."""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, GObject, Gtk, Pango
from pathlib import Path
import json
import re
from fenestra_sidebar import FenestraSidebar, GALLERY
from fenestra_pages import SpecialPages, gallery_folders
from fenestra_menus import CommandMenus

from fenestra_sidebar import _L, _LANG, tr
_L.setdefault('es', {}).update({'Extra large icons': 'Iconos muy grandes', 'Large icons': 'Iconos grandes', 'Medium icons': 'Iconos medianos',
    'Small icons': 'Iconos pequeños', 'List': 'Lista', 'Details': 'Detalles', 'Tiles': 'Mosaicos', 'Content': 'Contenido', 'Sort': 'Ordenar', 'Compact view': 'Vista compacta', 'View': 'Ver', '1 item': '1 elemento', '%d items': '%d elementos',
    'Date modified': 'Fecha de modificación', 'This folder is empty.': 'Esta carpeta está vacía.',
    'Search Results in %s': 'Resultados de la búsqueda en %s', '%s - Search Results in %s': '%s - Resultados de la búsqueda en %s',
    '1 item selected': '1 elemento seleccionado', '%d items selected': '%d elementos seleccionados', '%d bytes': '%d bytes', 'Collection': 'Colección', 'Add a folder': 'Agregar una carpeta'})
VIEWS = [(k, tr(v)) for k, v in [('extra-large','Extra large icons'),('large','Large icons'),('medium','Medium icons'),('small','Small icons'),('list','List'),('details','Details'),('tiles','Tiles'),('content','Content')]]

def walk(w):
    yield w
    c=w.get_first_child()
    while c:
        yield from walk(c)
        c=c.get_next_sibling()

def kind(w):return GObject.type_name(w.__gtype__)

def _count_items(location):
    try:
        en=location.enumerate_children('standard::name,standard::is-hidden',Gio.FileQueryInfoFlags.NONE,None)
        n=0
        for info in en:
            if not info.get_is_hidden(): n+=1
        return n
    except GLib.Error:
        return None


_NAUTILUS_DATE=re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4}),? (\d{1,2}:\d{2})$')


def _cell_file(cell):
    """The Gio.File a Nautilus view cell shows (its item's NautilusFile is a Nautilus.FileInfo)."""
    try:
        item=cell.get_property('item')
        nfile=item.get_property('file') if item else None
        return nfile.get_location() if nfile else None
    except (TypeError,AttributeError):
        return None


def windows_size(gfile):
    """Explorer's Size column: whole KB rounded up (1 KB for 1..1024 bytes, 0 KB when empty),
    nothing for folders."""
    try:
        info=gfile.query_info('standard::size,standard::type',Gio.FileQueryInfoFlags.NONE,None)
    except GLib.Error:
        return None
    if info.get_file_type()==Gio.FileType.DIRECTORY:return ''
    kb=(info.get_size()+1023)//1024
    return f'{kb:,}'.replace(',','.')+' KB'


# Explorer's Type column for the extensions a clean Windows 11 registers (es-ES / en-US); those
# extensions are also hidden in the Name column ("Hide extensions for known file types").
# Anything else reads "Archivo EXT" / "EXT File" and keeps its extension, like «Archivo MD».
_ES=_LANG=='es'
WINDOWS_TYPES={
    'txt':('Documento de texto','Text Document'),'log':('Documento de texto','Text Document'),
    'ini':('Opciones de configuración','Configuration settings'),
    'jpg':('Archivo JPG','JPG File'),'jpeg':('Archivo JPEG','JPEG File'),'png':('Archivo PNG','PNG File'),
    'gif':('Archivo GIF','GIF File'),'bmp':('Archivo BMP','BMP File'),'webp':('Archivo WEBP','WEBP File'),
    'svg':('Archivo SVG','SVG File'),'ico':('Icono','Icon'),'tif':('Archivo TIF','TIF File'),'tiff':('Archivo TIFF','TIFF File'),
    'wav':('Archivo WAV','WAV File'),'mp3':('Archivo MP3','MP3 File'),'wma':('Archivo WMA','WMA File'),
    'flac':('Archivo FLAC','FLAC File'),'m4a':('Archivo M4A','M4A File'),'ogg':('Archivo OGG','OGG File'),
    'mp4':('Archivo MP4','MP4 File'),'mkv':('Archivo MKV','MKV File'),'avi':('Archivo AVI','AVI File'),
    'mov':('Archivo MOV','MOV File'),'wmv':('Archivo WMV','WMV File'),'webm':('Archivo WEBM','WEBM File'),
    'zip':('Carpeta comprimida (en zip)','Compressed (zipped) Folder'),
    'pdf':('Documento PDF','PDF Document'),'htm':('Documento HTML','HTML Document'),'html':('Documento HTML','HTML Document'),
    'xml':('Documento XML','XML Document'),'json':('Archivo JSON','JSON File'),'csv':('Archivo CSV','CSV File'),
    'rtf':('Formato de texto enriquecido','Rich Text Format'),'exe':('Aplicación','Application'),
    'lnk':('Acceso directo','Shortcut'),'url':('Acceso directo a Internet','Internet Shortcut'),
    'ttf':('Archivo de fuente TrueType','TrueType font file'),'otf':('Archivo de fuente OpenType','OpenType font file'),
}


def _split_ext(name):
    stem,dot,ext=name.rpartition('.')
    return (stem,ext.lower()) if dot and stem and not stem.endswith('.') else (name,'')


def windows_type(gfile):
    """Explorer's Type column: «Carpeta de archivos», the registered type name, else «Archivo EXT»."""
    try:
        info=gfile.query_info('standard::type,standard::display-name',Gio.FileQueryInfoFlags.NONE,None)
    except GLib.Error:
        return None
    if info.get_file_type()==Gio.FileType.DIRECTORY:return 'Carpeta de archivos' if _ES else 'File folder'
    _stem,ext=_split_ext(info.get_display_name())
    if ext in WINDOWS_TYPES:return WINDOWS_TYPES[ext][0 if _ES else 1]
    if not ext:return 'Archivo' if _ES else 'File'
    return f'Archivo {ext.upper()}' if _ES else f'{ext.upper()} File'


def windows_name(gfile,text):
    """The Name column hides the extension of the types above (not of folders or unknown types)."""
    stem,ext=_split_ext(text)
    if ext not in WINDOWS_TYPES:return text
    try:
        if gfile.query_file_type(Gio.FileQueryInfoFlags.NONE,None)==Gio.FileType.DIRECTORY:return text
    except GLib.Error:
        return text
    return stem


def _reformat(label,role,cell):
    if getattr(label,'_windows_busy',False):return
    text=label.get_label() or ''
    if role=='date':
        m=_NAUTILUS_DATE.match(text)
        new=f'{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)} {m.group(4)}' if m else text
    elif role in ('type','name'):
        gfile=_cell_file(cell)
        new=(windows_type(gfile) if role=='type' else windows_name(gfile,text)) if gfile else None
        if new is None:new=text
    else:
        gfile=_cell_file(cell)
        new=windows_size(gfile) if gfile else None
        if new is None:new=text
    if new!=text:
        label._windows_busy=True;label.set_label(new);label._windows_busy=False


def details_cell(cell,role):
    """Details view cells as Explorer writes them: dd/mm/yyyy h:mm dates (left aligned) and
    sizes in KB (right aligned). Nautilus updates the label after binding, so follow it."""
    if cell is None:return
    label=next((w for w in walk(cell) if isinstance(w,Gtk.Label)),None)
    if label is None:return
    label.set_xalign(1.0 if role=='size' else 0.0);label.set_halign(Gtk.Align.FILL);label.set_hexpand(True)
    if not getattr(label,'_windows_cell',False):
        label._windows_cell=True
        label.connect('notify::label',lambda l,_p:_reformat(l,l._windows_role,cell))
    label._windows_role=role
    _reformat(label,role,cell)


def status_size(n):
    """Explorer's status-bar size: bytes below 1 KB, else three significant digits (1,23 KB, 12,3 KB, 123 KB)."""
    if n<1024:return tr('%d bytes')%n
    value=float(n)
    for unit in ('KB','MB','GB','TB'):
        value/=1024.0
        if value<1000 or unit=='TB':break
    digits=2 if value<10 else 1 if value<100 else 0  # truncated, not rounded, like Explorer
    value=int(value*10**digits)/10**digits
    text=f'{value:.{digits}f}'
    return text.replace('.',',' if tr('View')!='View' else '.')+' '+unit


class FenestraViews:
    def __init__(self, window):
        self.window=window;self.mode='details';self.compact=False;self.pending=0;self.changing=False;self.special=None
        self.sidebar=FenestraSidebar(window,walk)
        self.initial=True
        self.pages=SpecialPages(window,walk,kind)
        self.pane='none'
        self.folders={}
        self.config=Path(GLib.get_user_config_dir())/'fenestra-explorer/view.json'
        try:
            state=json.loads(self.config.read_text());self.compact=bool(state.get('compact',False))
            self.pane=state.get('pane','none') if state.get('pane') in ('none','details','preview') else 'none'
            self.folders={k:v for k,v in (state.get('folders') or {}).items() if v in dict(VIEWS)}
        except (OSError,ValueError,TypeError,AttributeError):pass
        self.action=Gio.SimpleAction.new_stateful('windows-view',GLib.VariantType.new('s'),GLib.Variant('s',self.mode))
        self.action.connect('activate',lambda a,v:self.select(v.get_string(),remember=True))
        window.add_action(self.action)
        self.order=Gio.SimpleAction.new_stateful('fenestra-sort-order',GLib.VariantType.new('s'),GLib.Variant('s','ascending'))
        self.order.connect('activate',self.sort_order);window.add_action(self.order)
        group=Gio.SimpleAction.new_stateful('fenestra-group',GLib.VariantType.new('s'),GLib.Variant('s','none'))
        group.connect('activate',lambda a,v:a.set_state(v));window.add_action(group)
        add=Gio.SimpleAction.new('fenestra-gallery-add',None)
        add.connect('activate',lambda *_:self.pages.page('gallery').add_folder());window.add_action(add)
        opener=Gio.SimpleAction.new('fenestra-open',GLib.VariantType.new('s'))
        opener.connect('activate',lambda a,v:self.pages._open(v.get_string()));window.add_action(opener)
        self.density=Gio.SimpleAction.new_stateful('windows-row-spacing',None,GLib.Variant('b',self.compact))
        self.density.connect('activate',self.toggle_compact);window.add_action(self.density)
        window.connect('notify::active-slot',lambda *_:self.queue())
        window.connect('destroy',self.destroy)
        if self.compact:window.add_css_class('win11-compact')
        self._width=0;self._tick_n=0
        self.menus=CommandMenus(self)
        window.add_tick_callback(self._tick)
        self.queue()

    def _tick(self,window,_clock):
        if self.window is None:return False
        width=window.get_width()
        if width and width!=self._width:
            self._width=width;self._tick_n=0;self._responsive(width)
        elif width and self._tick_n<20:
            # The address bar request depends on its own x; settle it over a few frames.
            self._tick_n+=1;self._responsive(width)
        return True

    def _responsive(self,width):
        # Address bar takes all the width left of the search box (Windows), not a centred title.
        # GtkCenterBox only gives the title its natural width, so request the width
        # Windows gives the address bar (window - nav buttons - search - gaps). The
        # request trails the window width, so the window can still be made narrower.
        path=next((w for w in walk(self.window) if kind(w)=='NautilusPathBar'),None)
        stack=path.get_parent() if path else None
        if stack is not None:
            search=max(150,min(261,int((width-560)*0.48)))
            ok,b=stack.compute_bounds(self.window)
            left=int(b.get_x()) if ok and b.get_x()>0 else 201
            # Address box, 6 px box spacing + the search box's 2 px margin (inside its request),
            # the search box, then 12 px to the edge (header spacing around the empty end box).
            want=max(120,width-left-search-18)
            if stack.get_size_request()[0]!=want:stack.set_size_request(want,-1)
        """Explorer shrinks the search box and folds command-bar buttons into "See more"
        instead of letting the window's minimum width grow past the screen."""
        for w in walk(self.window):
            if w.has_css_class('win11-search'):
                w.set_size_request(max(150,min(261,int((width-560)*0.48))),-1)
                break
        bar=next((a for a in walk(self.window) if a.has_css_class('win11-commandbar')),None)
        if not bar:return
        children=[];c=bar.get_first_child()
        while c:children.append(c);c=c.get_next_sibling()
        clip=[c for c in children if isinstance(c,Gtk.Actionable) and (c.get_action_name() or '') in
              ('view.cut','view.copy','view.paste','view.rename','view.open-with-other-application','view.move-to-trash')]
        seps=[c for c in children if c.has_css_class('win11-cmd-separator')]
        collapse=width<820
        for c in clip:c.set_visible(not collapse)
        if seps:seps[0].set_visible(not collapse)
        for c in children:
            if isinstance(c,Gtk.Actionable) and c.get_action_name()=='slot.search-visible':
                c.set_visible(width>=700 and self.special=='home')
            if isinstance(c,Gtk.Actionable) and c.get_action_name()=='view.current-directory-properties':
                for lab in walk(c):
                    if isinstance(lab,Gtk.Label):lab.set_visible(width>=900)
        self.menus.folded=collapse

    def destroy(self,*_):
        if self.pending:GLib.source_remove(self.pending)
        self.pending=0;self.window=None

    def queue(self,*_):
        if not self.pending and self.window:self.pending=GLib.idle_add(self.refresh)

    def slot(self):return self.window.get_property('active-slot') if self.window else None

    def wanted(self,location):
        """Windows keeps a view per folder: Details by default, Large icons for Pictures/Videos."""
        uri=location.get_uri()
        # Explorer lists results as Content, but Nautilus crashes when a search's view is rebuilt
        # (list -> grid), so a search keeps the folder's view.
        if location.get_uri_scheme()=='x-nautilus-search':return self.mode
        if uri in self.folders:return self.folders[uri]
        media=[GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES),GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)]+gallery_folders()
        return 'large' if location.get_path() and location.get_path() in media else 'details'

    def save(self):
        try:
            self.config.parent.mkdir(parents=True,exist_ok=True)
            self.config.write_text(json.dumps({'compact':self.compact,'folders':self.folders,'pane':self.pane}))
        except OSError:pass

    def select(self,mode,remember=False):
        if mode not in dict(VIEWS) or self.changing:return
        slot=self.slot()
        if not slot:return
        self.mode=mode
        location=slot.get_property('location')
        if remember and location and not self.special:
            self.folders[location.get_uri()]=mode;self.save()
        for name,_ in VIEWS:self.window.remove_css_class('windows-view-'+name)
        self.window.add_css_class('windows-view-'+mode)
        self.action.set_state(GLib.Variant('s',mode));self.changing=True
        # Recreate the grid when switching presentations so native cell bindings
        # never retain a layout or a caption style belonging to another view.
        target=1 if mode=='details' else 2
        current=next((w for w in walk(slot) if kind(w) in ('NautilusGridView','NautilusListView')),None)
        if target==2 and current and kind(current)=='NautilusGridView':
            slot.activate_action('slot.files-view-mode',GLib.Variant('u',1))
        slot.activate_action('slot.files-view-mode',GLib.Variant('u',target))
        GLib.idle_add(self.finish_select,slot)

    def finish_select(self,slot):
        if not self.window:return False
        for _ in range(5):slot.activate_action('view.zoom-out',None)
        zoom={'extra-large':4,'large':2,'medium':0,'small':0,'list':0,'tiles':2,'content':2,'details':0}[self.mode]
        for _ in range(zoom):slot.activate_action('view.zoom-in',None)
        self.changing=False;self.queue();return False

    def toggle_compact(self,*_):
        self.compact=not self.compact;self.density.set_state(GLib.Variant('b',self.compact));self.save()
        self.window.add_css_class('win11-compact') if self.compact else self.window.remove_css_class('win11-compact')
        self.select(self.mode)

    def sort_order(self,action,value):
        action.set_state(value)
        slot=self.slot()
        view=next((w for w in walk(slot) if kind(w)=='NautilusFilesView'),None) if slot else None
        key=getattr(self,'sort_key','name')
        if view:view.activate_action('view.sort',GLib.Variant('(sb)',(key,value.get_string()=='descending')))

    def _sort_state(self,slot):
        cv=next((w for w in walk(slot) if isinstance(w,Gtk.ColumnView)),None)
        sorter=cv.get_sorter() if cv else None
        column=sorter.get_primary_sort_column() if sorter else None
        if column:
            title=column.get_title() or ''
            self.sort_key={tr('Name'):'name','Name':'name',tr('Date modified'):'date_modified','Size':'size',tr('Size'):'size','Type':'type',tr('Type'):'type'}.get(title,'name')
            descending=sorter.get_primary_sort_order()==Gtk.SortType.DESCENDING
            self.order.set_state(GLib.Variant('s','descending' if descending else 'ascending'))
            self.menus.sort_key,self.menus.sort_desc=self.sort_key,descending

    def _commandbar(self,special):
        bar=next((a for a in walk(self.window) if a.has_css_class('win11-commandbar')),None)
        if not bar:return
        for w in walk(bar):
            if isinstance(w,Gtk.Actionable) and w.get_action_name()=='slot.search-visible':
                # Windows shows Filter on Home only.
                w.set_visible(special=='home' and (not self._width or self._width>=700))
        sort=getattr(self.window,'_windows_sort_menu',None)
        if sort:sort.set_sensitive(special not in ('gallery','home'))
        for w in walk(bar):
            if isinstance(w,Gtk.Actionable) and (w.get_action_name() or '') in ('view.new-folder','view.cut','view.copy','view.paste','view.rename','view.open-with-other-application','view.move-to-trash'):
                if special is not None:
                    w.set_sensitive(False);w._fenestra_off=True
                elif getattr(w,'_fenestra_off',False):
                    # Re-sync with the action's enabled state (GtkActionHelper owns sensitivity).
                    w._fenestra_off=False;name=w.get_action_name();w.set_action_name(None);w.set_action_name(name)
        coll=getattr(self.window,'_fenestra_collection',None)
        if coll is None and special=='gallery':
            coll=Gtk.MenuButton();coll.add_css_class('win11-cmd-text');coll.add_css_class('flat')
            contents=Gtk.Box(spacing=8)
            image=Gtk.Image.new_from_icon_name('win11-explorer-collection');image.set_pixel_size(16)
            lab=Gtk.Label(label=tr('Collection'));lab.add_css_class('win11-cmd-label')
            chev=Gtk.Image.new_from_icon_name('win11-explorer-chevron-down');chev.set_pixel_size(8);chev.add_css_class('win11-cmd-chevron')
            contents.append(image);contents.append(lab);contents.append(chev);coll.set_child(contents)
            control=next((a for a in walk(bar) if kind(a)=='NautilusViewControls'),None)
            if control:bar.insert_child_after(coll,control)
            else:bar.append(coll)
            self.window._fenestra_collection=coll
        if coll is not None:
            coll.set_visible(special=='gallery')
            if special=='gallery':
                menu=Gio.Menu();folders=Gio.Menu()
                for path in gallery_folders():
                    item=Gio.MenuItem.new(GLib.path_get_basename(path),None)
                    item.set_action_and_target_value('win.fenestra-open',GLib.Variant('s',Gio.File.new_for_path(path).get_uri()))
                    folders.append_item(item)
                menu.append_section(None,folders);menu.append(tr('Add a folder'),'win.fenestra-gallery-add')
                coll.set_menu_model(menu)

    def _crumbs(self,special=None):
        bar=next((w for w in walk(self.window) if kind(w)=='NautilusPathBar'),None)
        if not bar:return
        boxes=[]
        for w in walk(bar):
            if isinstance(w,Gtk.Label) and w.has_css_class('dim-label') and w.get_label()=='/' :
                w.set_label('›');w.add_css_class('fenestra-crumb-sep')
            if isinstance(w,Gtk.Label) and w.has_css_class('fenestra-crumb-tail'):
                w.get_parent().remove(w)
        crumbs=[w for w in walk(bar) if isinstance(w,Gtk.Button) and not isinstance(w.get_parent(),Gtk.MenuButton) and isinstance(w.get_parent(),Gtk.Box)]
        crumbs=[c for c in crumbs if kind(c)=='GtkButton' and c.get_ancestor(Gtk.ScrolledWindow)]
        if not crumbs:return
        for c in crumbs:
            for lab in walk(c):
                if isinstance(lab,Gtk.Label) and not getattr(lab,'_fenestra_weight',False):
                    lab._fenestra_weight=True
                    attrs=Pango.AttrList();attrs.insert(Pango.attr_weight_new(Pango.Weight.NORMAL));lab.set_attributes(attrs)
            if c.get_parent():c.get_parent().set_visible(True)
        if special in ('gallery','computer'):
            # Virtual locations in Windows: one crumb (icon › name), no filesystem path.
            for c in crumbs[:-1]:c.get_parent().set_visible(False)
            for w in walk(crumbs[-1].get_parent()):
                if isinstance(w,Gtk.Label) and w.get_label()=='›' and not w.is_ancestor(crumbs[-1]):w.set_visible(False)
            box=crumbs[-1].get_child()
            if isinstance(box,Gtk.Box):
                lab=next((c for c in walk(box) if isinstance(c,Gtk.Label) and not c.has_css_class('fenestra-crumb-sep')),None)
                if lab:lab.set_label(tr('Gallery') if special=='gallery' else tr('This PC'))
                if not next((c for c in walk(box) if isinstance(c,Gtk.Image)),None):
                    box.prepend(Gtk.Image.new_from_icon_name('win11-explorer-gallery'))
            crumbs=crumbs[-1:]
        self._home_crumb(crumbs,special)
        first=crumbs[0].get_child()
        image=None
        if isinstance(first,Gtk.Box):
            image=next((c for c in walk(first) if isinstance(c,Gtk.Image)),None)
            if image and not getattr(first,'_fenestra_lead',False):
                first._fenestra_lead=True
                sep=Gtk.Label(label='›');sep.add_css_class('fenestra-crumb-sep');sep.add_css_class('fenestra-crumb-lead')
                first.insert_child_after(sep,image)
        bar.add_css_class('fenestra-crumbs')
        if isinstance(first,Gtk.Box) and image:
            name=next((c.get_label() for c in walk(first) if isinstance(c,Gtk.Label) and not c.has_css_class('fenestra-crumb-sep')),'')
            glyph={tr('Home'):'win11-explorer-home',tr('This PC'):'win11-explorer-thispc',tr('Gallery'):'win11-explorer-gallery'}.get(name)
            if any(isinstance(c,Gtk.Label) and getattr(c,'_fenestra_home',False) and not c.get_visible() for c in walk(first)):glyph=None
            if glyph:image.set_from_icon_name(glyph);image.set_pixel_size(16);image.set_visible(True);image.add_css_class('fenestra-mono')
        last=crumbs[-1].get_child()
        if isinstance(last,Gtk.Box) and self._has_subfolders(special):
            tail=Gtk.Label(label='›');tail.add_css_class('fenestra-crumb-sep');tail.add_css_class('fenestra-crumb-tail')
            last.append(tail)

    def _history_icons(self):
        """Back / Forward are Explorer's arrows, not Adwaita's chevrons (Up already is)."""
        controls=next((w for w in walk(self.window) if kind(w)=='NautilusHistoryControls'),None)
        if controls is None or getattr(controls,'_fenestra_icons',False):return
        buttons=[w for w in walk(controls) if isinstance(w,Gtk.Button)]
        for button,name in zip(buttons,('win11-explorer-back','win11-explorer-forward')):
            button.set_icon_name(name)
        controls._fenestra_icons=len(buttons)>=2

    def _has_subfolders(self,special):
        """Explorer ends the address with a chevron only when the folder has subfolders."""
        if special:return True
        slot=self.slot();location=slot.get_property('location') if slot else None
        if location is not None and location.get_uri_scheme()=='x-nautilus-search':return False
        if not location or not location.get_path():return True
        try:
            for info in location.enumerate_children('standard::type,standard::is-hidden',Gio.FileQueryInfoFlags.NONE,None):
                if info.get_file_type()==Gio.FileType.DIRECTORY and not info.get_is_hidden():return True
        except GLib.Error:return True
        return False

    def _home_crumb(self,crumbs,special):
        """Nautilus' home crumb ('Carpeta personal') is Explorer's Home; inside a known folder
        (Documents, Music, ...) Explorer starts the address at that folder behind This PC's icon."""
        home=crumbs[0];box=home.get_child()
        if special in ('gallery','computer') or not isinstance(box,Gtk.Box):return
        slot=self.slot();location=slot.get_property('location') if slot else None
        if location is not None and location.get_uri_scheme()=='x-nautilus-search':
            self._search_crumb(crumbs);return
        lab=next((c for c in walk(box) if isinstance(c,Gtk.Label) and not c.has_css_class('fenestra-crumb-sep')),None)
        if lab is None:return
        names={GLib.dgettext('nautilus','Home'),'Home',tr('Home')}
        if lab.get_label() in names or getattr(lab,'_fenestra_home',False):
            lab._fenestra_home=True;lab.set_label(tr('Home'))
        else:return
        path=location.get_path() if location else None
        known={GLib.get_user_special_dir(getattr(GLib.UserDirectory,k)) for k in ('DIRECTORY_DESKTOP','DIRECTORY_DOCUMENTS','DIRECTORY_DOWNLOAD','DIRECTORY_MUSIC','DIRECTORY_PICTURES','DIRECTORY_VIDEOS')}
        known.discard(None);known.discard(GLib.get_home_dir())
        inside=bool(path) and len(crumbs)>1 and any(path==k or path.startswith(k+'/') for k in known)
        lab.set_visible(not inside)
        image=next((c for c in walk(box) if isinstance(c,Gtk.Image)),None)
        if image:
            image.set_from_icon_name('win11-explorer-thispc' if inside else 'win11-explorer-home')
            image.set_pixel_size(16);image.set_visible(True);image.add_css_class('fenestra-mono')
        # The separator Nautilus puts before the second crumb doubles the lead chevron.
        if len(crumbs)>1:(crumbs[1].add_css_class if inside else crumbs[1].remove_css_class)('fenestra-crumb-known')
        nxt=crumbs[1].get_parent() if len(crumbs)>1 else None
        if nxt is not None:
            for w in walk(nxt):
                if isinstance(w,Gtk.Label) and w.has_css_class('fenestra-crumb-sep') and not w.is_ancestor(crumbs[1]):w.set_visible(not inside)

    def _search_crumb(self,crumbs):
        """A search reads '[This PC] > Search results in <folder>' in Explorer's address bar."""
        for c in crumbs[1:]:c.get_parent().set_visible(False)
        for w in walk(crumbs[0].get_parent()):
            if isinstance(w,Gtk.Label) and w.has_css_class('fenestra-crumb-sep') and not w.is_ancestor(crumbs[0]):w.set_visible(False)
        box=crumbs[0].get_child()
        if isinstance(box,Gtk.Box) and not next((c for c in walk(box) if isinstance(c,Gtk.Image)),None):
            box.prepend(Gtk.Image.new_from_icon_name('win11-explorer-thispc'))
        labels=[c for c in walk(box) if isinstance(c,Gtk.Label) and not c.has_css_class('fenestra-crumb-sep')]
        if labels:
            labels[0].set_label(tr('Search Results in %s')%getattr(self,'_folder_title',''));labels[0].set_visible(True)
        image=next((c for c in walk(box) if isinstance(c,Gtk.Image)),None)
        if image:
            image.set_from_icon_name('win11-explorer-thispc');image.set_pixel_size(16);image.set_visible(True);image.add_css_class('fenestra-mono')

    def _empty(self,slot):
        for w in walk(slot):
            if kind(w)=='AdwStatusPage' and w.has_css_class('view'):
                if w.get_title()!=tr('This folder is empty.') and w.get_title():
                    w._fenestra_orig=True
                if getattr(w,'_fenestra_orig',False):
                    w.set_icon_name(None);w.set_paintable(None);w.set_description(None)
                    w.set_title(tr('This folder is empty.'));w.add_css_class('fenestra-empty-folder')
                    w.set_valign(Gtk.Align.START)

    def _statusbar(self,label):
        """Windows' status bar: 'N items |' on the left, Details/Large icons toggles on the right."""
        if getattr(label,'_fenestra_bar',False):return
        parent=label.get_parent()
        if not isinstance(parent,Gtk.Box):return
        label._fenestra_bar=True
        bar=Gtk.Box();bar.add_css_class('fenestra-statusbar')
        parent.insert_child_after(bar,label);parent.remove(label);bar.append(label)
        label.set_hexpand(False)
        sep=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL);bar.append(sep)
        # "1 elemento seleccionado  79 bytes |" while something is selected.
        self.sel_label=Gtk.Label();self.sel_label.add_css_class('win11-status');self.sel_label.add_css_class('fenestra-status-selection')
        self.sel_sep=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        bar.append(self.sel_label);bar.append(self.sel_sep)
        self.sel_label.set_visible(False);self.sel_sep.set_visible(False)
        bar.append(Gtk.Box(hexpand=True))
        self.status_buttons={}
        for mode,glyph in (('details','win11-view-details'),('large','win11-view-large')):
            b=Gtk.ToggleButton();img=Gtk.Image.new_from_icon_name(glyph);img.set_pixel_size(12 if mode=='details' else 16);b.set_child(img)
            b.set_tooltip_text(dict(VIEWS)[mode])
            b.connect('clicked',lambda btn,m=mode:self.select(m,remember=True) if btn.get_active() else None)
            bar.append(b);self.status_buttons[mode]=b

    def selection_status(self,files):
        label=getattr(self,'sel_label',None)
        if label is None:return
        n=len(files)
        text=''
        if n:
            text=tr('1 item selected') if n==1 else tr('%d items selected')%n
            total=0
            for f in files:
                try:
                    info=f.query_info('standard::size,standard::type',Gio.FileQueryInfoFlags.NONE,None)
                except GLib.Error:
                    total=None;break
                if info.get_file_type()!=Gio.FileType.REGULAR:total=None;break
                total+=info.get_size()
            if total is not None:text+='  '+status_size(total)
        label.set_label(text);label.set_visible(bool(n));self.sel_sep.set_visible(bool(n))

    def _status(self,slot,special=None):
        label=next((w for w in walk(self.window) if isinstance(w,Gtk.Label) and w.has_css_class('win11-status')),None)
        if not label: return
        self._statusbar(label)
        for m,b in getattr(self,'status_buttons',{}).items():
            if b.get_active()!=(self.mode==m and not special):b.set_active(self.mode==m and not special)
        loc=slot.get_property('location') if slot else None
        n=self.pages.count(special) if special else (_count_items(loc) if loc and loc.get_path() else None)
        label.set_label('' if n is None else (tr('1 item') if n==1 else tr('%d items') % n))

    def refresh(self):
        self.pending=0
        if not self.window:return False
        slot=self.slot()
        if not slot:return False
        self.sidebar.refresh()
        self._history_icons()
        if not getattr(slot,'_windows_views_signals',False):
            slot._windows_views_signals=True
            slot.connect('notify::loading',self.queue)
            slot.connect('notify::location',self.queue)
        location=slot.get_property('location')
        uri=location.get_uri() if location else None
        if location is not None and location.get_uri_scheme()!='x-nautilus-search':
            self._folder_title=tr('Home') if location.get_path()==GLib.get_home_dir() else (slot.get_property('title') if slot.find_property('title') else '') or location.get_basename()
        self.special=self.pages.update(slot)
        self._commandbar(self.special)
        self._crumbs(self.special)
        if uri!=getattr(self,'_last_view_uri',None) and location and not self.special:
            self._last_view_uri=uri
            mode=self.wanted(location)
            view=next((w for w in walk(slot) if kind(w) in ('NautilusGridView','NautilusListView')),None)
            matches=view is not None and (kind(view)=='NautilusListView')==(mode=='details')
            if self.initial or mode!=self.mode or not matches:
                self.initial=False;self.select(mode);return False
        elif self.special:
            self._last_view_uri=None
        self._status(slot,self.special)
        if not self.special:
            self._empty(slot);self._sort_state(slot)
        commandbar=next((a for a in walk(self.window) if a.has_css_class('win11-commandbar')),None)
        if commandbar:self.menus.ensure(commandbar)
        if not self.special:self.menus.watch_selection()
        for w in walk(self.window):
            if isinstance(w,Gtk.ColumnView) and w.is_ancestor(slot):
                columns=w.get_columns()
                for index in range(columns.get_n_items()):
                    column=columns.get_item(index)
                    title=column.get_title() or ''
                    if title=='':column.set_visible(False)
                    if title in ('Modified','Date Modified','Modificado','Fecha de modificación'):
                        column.set_title(tr('Date modified'));title=tr('Date modified')
                    if not getattr(column,'_windows_width_set',False):
                        # Windows 11 Details column widths.
                        width={'Name':258,'Nombre':258,tr('Date modified'):144,'Type':120,'Tipo':120,'Size':80,'Tamaño':80}.get(title)
                        if width:column.set_fixed_width(width);column.set_expand(False);column.set_resizable(True)
                        column._windows_width_set=True
                    role={tr('Date modified'):'date','Size':'size','Tamaño':'size','Type':'type','Tipo':'type','Name':'name','Nombre':'name'}.get(title)
                    factory=column.get_factory()
                    if role and factory and not getattr(factory,'_windows_cells',False):
                        factory._windows_cells=True
                        factory.connect_after('bind',lambda _f,item,r=role:details_cell(item.get_child(),r))
                        # Rows bound before the hook: cells sit in column order in each row.
                        visible=[columns.get_item(i) for i in range(columns.get_n_items()) if columns.get_item(i).get_visible()]
                        at=visible.index(column) if column in visible else -1
                        for row in walk(w):
                            if row.get_css_name()!='row' or kind(row)!='GtkColumnViewRowWidget':continue
                            cells=[c for c in walk(row) if kind(c)=='GtkColumnViewCellWidget']
                            if 0<=at<len(cells):details_cell(cells[at].get_first_child(),role)
            if kind(w)=='GtkGridView':
                # Only alter widgets inside the active slot (is_ancestor is reversed).
                if not w.is_ancestor(slot):continue
                if not getattr(w,'_windows_factory',False):
                    w._windows_factory=True
                    w.get_factory().connect_after('bind',lambda _f,item:self.cell(item.get_child()))
                w.set_halign(Gtk.Align.FILL);w.set_hexpand(True)
                w.set_max_columns(1 if self.mode=='content' else 20)
                w.set_min_columns(1)
                if isinstance(w,Gtk.Orientable):w.set_orientation(Gtk.Orientation.HORIZONTAL if self.mode=='list' else Gtk.Orientation.VERTICAL)
                for c in walk(w):
                    if kind(c)=='NautilusGridCell':self.cell(c)
        return False

    def cell(self,cell):
        if not cell or kind(cell)!='NautilusGridCell':return
        mode=self.mode
        if mode in ('extra-large','large','medium'):
            for label in walk(cell):
                if isinstance(label,Gtk.Label) and label.has_css_class('caption'):
                    label.set_visible(False)
                    if not getattr(label,'_fenestra_hidden',False):
                        # Nautilus re-shows captions when file info updates; icon views show the name only.
                        label._fenestra_hidden=True
                        label.connect('notify::visible',lambda l,_p:l.set_visible(False) if l.get_visible() and self.mode in ('extra-large','large','medium') else None)
            return
        if mode=='details':return
        horizontal=mode in ('small','list','tiles','content')
        if not horizontal:return
        if not getattr(cell,'_windows_layout',False):
            layout=Gtk.BoxLayout.new(Gtk.Orientation.HORIZONTAL);layout.set_spacing(10 if mode in ('tiles','content') else 6)
            cell.set_layout_manager(layout);cell._windows_layout=True
        size=16 if mode in ('small','list') else 48
        if cell.get_property('icon-size')!=size:cell.set_property('icon-size',size)
        parent=cell.get_parent()
        if parent:parent.set_halign(Gtk.Align.FILL if mode=='content' else Gtk.Align.START)
        # Content rows fill the view (hexpand); a width taken from the slot would feed back into it.
        cell.set_size_request(210 if mode!='content' else 360,24 if self.compact and size==16 else 32 if size==16 else 64)
        cell.set_valign(Gtk.Align.START);cell.set_halign(Gtk.Align.FILL);cell.set_hexpand(True)
        cell.add_css_class('windows-horizontal-cell')
        children=[];c=cell.get_first_child()
        while c:children.append(c);c=c.get_next_sibling()
        for c in children:
            if isinstance(c,Gtk.Picture):
                c.set_size_request(size,size);c.set_can_shrink(True);c.set_halign(Gtk.Align.START);c.set_valign(Gtk.Align.CENTER)
            if any(isinstance(v,Gtk.Label) for v in walk(c)):
                c.set_hexpand(True);c.set_valign(Gtk.Align.CENTER)
                labels=[v for v in walk(c) if isinstance(v,Gtk.Label)]
                for i,label in enumerate(labels):
                    label.set_xalign(0);label.set_justify(Gtk.Justification.LEFT);label.set_wrap(False);label.set_lines(1);label.set_ellipsize(Pango.EllipsizeMode.END)
                    label.set_max_width_chars(32 if mode=='content' else 24)
                    if i>0:label.set_visible(mode in ('tiles','content') and bool(label.get_text()))

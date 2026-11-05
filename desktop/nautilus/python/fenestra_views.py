"""Explorer-style view choices using Nautilus' own models, selection and file actions."""
from gi.repository import Gio, GLib, GObject, Gtk, Pango
from pathlib import Path
import json
from fenestra_sidebar import FenestraSidebar, GALLERY

from fenestra_sidebar import _L, tr
_L.setdefault('es', {}).update({'Extra large icons': 'Iconos muy grandes', 'Large icons': 'Iconos grandes', 'Medium icons': 'Iconos medianos',
    'Small icons': 'Iconos pequeños', 'List': 'Lista', 'Details': 'Detalles', 'Tiles': 'Mosaicos', 'Content': 'Contenido', 'Sort': 'Ordenar', 'Compact view': 'Vista compacta', 'View': 'Ver', '1 item': '1 elemento', '%d items': '%d elementos'})
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


class FenestraViews:
    def __init__(self, window):
        self.window=window;self.mode='details';self.compact=False;self.pending=0;self.changing=False
        self.sidebar=FenestraSidebar(window,walk)
        self.initial=True
        self.config=Path(GLib.get_user_config_dir())/'fenestra-explorer/view.json'
        try:
            state=json.loads(self.config.read_text());self.mode=state.get('view','details');self.compact=bool(state.get('compact',False))
            if self.mode not in dict(VIEWS):self.mode='details'
        except (OSError,ValueError,TypeError):pass
        self.action=Gio.SimpleAction.new_stateful('windows-view',GLib.VariantType.new('s'),GLib.Variant('s',self.mode))
        self.action.connect('activate',lambda a,v:self.select(v.get_string()))
        window.add_action(self.action)
        self.density=Gio.SimpleAction.new_stateful('windows-row-spacing',None,GLib.Variant('b',not self.compact))
        self.density.connect('activate',self.toggle_compact);window.add_action(self.density)
        window.connect('notify::active-slot',lambda *_:self.queue())
        window.connect('destroy',self.destroy)
        if self.compact:window.add_css_class('win11-compact')
        self.queue()

    def destroy(self,*_):
        if self.pending:GLib.source_remove(self.pending)
        self.pending=0;self.window=None

    def queue(self,*_):
        if not self.pending and self.window:self.pending=GLib.idle_add(self.refresh)

    def slot(self):return self.window.get_property('active-slot') if self.window else None

    def select(self,mode):
        if mode not in dict(VIEWS) or self.changing:return
        slot=self.slot()
        if not slot:return
        self.mode=mode
        try:
            self.config.parent.mkdir(parents=True,exist_ok=True)
            self.config.write_text(json.dumps({'view':self.mode,'compact':self.compact}))
        except OSError:pass
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
        self.compact=not self.compact;self.density.set_state(GLib.Variant('b',not self.compact))
        self.window.add_css_class('win11-compact') if self.compact else self.window.remove_css_class('win11-compact')
        self.select(self.mode)

    def _status(self,slot):
        label=next((w for w in walk(self.window) if isinstance(w,Gtk.Label) and w.has_css_class('win11-status')),None)
        if not label: return
        loc=slot.get_property('location') if slot else None
        n=_count_items(loc) if loc and loc.get_path() else None
        label.set_label('' if n is None else (tr('1 item') if n==1 else tr('%d items') % n))

    def refresh(self):
        self.pending=0
        if not self.window:return False
        slot=self.slot()
        if not slot:return False
        self.sidebar.refresh()
        location=slot.get_property('location')
        uri=location.get_uri() if location else None
        if uri!=getattr(self,'_last_sidebar_uri',None):
            self._last_sidebar_uri=uri
            if uri==GALLERY.as_uri():
                self.initial=False;self.select('large');return False
        if self.initial:
            self.initial=False;self.select(self.mode);return False
        if not getattr(slot,'_windows_views_signals',False):
            slot._windows_views_signals=True
            slot.connect('notify::loading',self.queue)
            slot.connect('notify::location',self.queue)
        self._status(slot)
        for w in walk(self.window):
            if isinstance(w,Gtk.PopoverMenu):
                model=w.get_menu_model()
                if model and model.get_n_items() and not getattr(w,'_windows_views_menu',False):
                    section=model.get_item_link(0,'section')
                    label=model.get_item_attribute_value(0,'label',None)
                    # Identify the native view menu by its zoom-out custom slot.
                    if section and any((section.get_item_attribute_value(i,'custom',None) or GLib.Variant('s','')).unpack()=='zoom-out' for i in range(section.get_n_items())):
                        w._windows_views_menu=True
                        views=Gio.Menu()
                        for key,name in VIEWS:
                            item=Gio.MenuItem.new(name,None);item.set_action_and_target_value('win.windows-view',GLib.Variant('s',key));views.append_item(item)
                        views.append(tr('Compact view'),'win.windows-row-spacing')
                        model.remove(0);model.insert_section(0,tr('View'),views)
                        commandbar=next((a for a in walk(self.window) if a.has_css_class('win11-commandbar')),None)
                        if commandbar and not getattr(self.window,'_windows_sort_menu',None):
                            sortmodel=model.get_item_link(1,'section')
                            if sortmodel:
                                sortbutton=Gtk.MenuButton(menu_model=sortmodel)
                                sortbutton.add_css_class('win11-cmd-text');sortbutton.add_css_class('flat')
                                contents=Gtk.Box(spacing=8)
                                image=Gtk.Image.new_from_icon_name('win11-explorer-sort');image.set_pixel_size(16)
                                lab=Gtk.Label(label=tr('Sort'));lab.add_css_class('win11-cmd-label')
                                chev=Gtk.Image.new_from_icon_name('win11-explorer-chevron-down');chev.set_pixel_size(8);chev.add_css_class('win11-cmd-chevron')
                                contents.append(image);contents.append(lab);contents.append(chev)
                                sortbutton.set_child(contents)
                                control=next((a for a in walk(commandbar) if kind(a)=='NautilusViewControls'),None)
                                if control:commandbar.insert_child_after(sortbutton,control.get_prev_sibling())
                                else:commandbar.append(sortbutton)
                                self.window._windows_sort_menu=sortbutton

            if kind(w)=='AdwSplitButton' and not getattr(w,'_fenestra_dropdown',False):
                w._fenestra_dropdown=True
                if not self.window.lookup_action('fenestra-view-menu'):
                    act=Gio.SimpleAction.new('fenestra-view-menu',None)
                    act.connect('activate',lambda *_a,b=w:b.popup())
                    self.window.add_action(act)
                w.set_action_name('win.fenestra-view-menu')
                w.add_css_class('win11-cmd-split')
            if isinstance(w,Gtk.ColumnView) and w.is_ancestor(slot):
                columns=w.get_columns()
                for index in range(columns.get_n_items()):
                    column=columns.get_item(index)
                    title=column.get_title() or ''
                    if title=='':column.set_visible(False)
                    if not getattr(column,'_windows_width_set',False):
                        width={'Modified':160,'Date Modified':160,'Modificado':160,'Fecha de modificación':160,'Type':120,'Tipo':120,'Size':80,'Tamaño':80}.get(title)
                        if width:column.set_fixed_width(width);column.set_expand(False)
                        column._windows_width_set=True
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
                if isinstance(label,Gtk.Label) and label.has_css_class('caption'):label.hide()
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
        cell.set_size_request(210 if mode!='content' else max(360,self.slot().get_width()-48),24 if self.compact and size==16 else 32 if size==16 else 64)
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

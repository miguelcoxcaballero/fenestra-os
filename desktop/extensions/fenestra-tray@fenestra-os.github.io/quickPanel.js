import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Pango from 'gi://Pango';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {QuickToggle,QuickMenuToggle,QuickSlider} from 'resource:///org/gnome/shell/ui/quickSettings.js';

export function installQuickPanel(){
 const q=Main.panel.statusArea.quickSettings,menu=q.menu,grid=menu._grid;
 const layout=grid.layout_manager,columns=layout.nColumns,original=grid.get_children();
 const states=[];const wrappers=new Set();let busy=false,pending=0;
 menu.actor.add_style_class_name('windows-quick-panel');layout.nColumns=3;
 const span=(item,n)=>layout.child_set_property(grid,item,'column-span',n);
 function tile(item){
  if(states.some(s=>s.item===item))return;
  const toggle=item instanceof QuickMenuToggle?item._box.get_first_child():item;
  if(!toggle?._title)return;
  const titleBox=toggle._title.get_parent();
  const state={item,titleBox,titleVisible:titleBox.visible,iconAlign:toggle._icon.x_align,boxAlign:toggle._box.x_align,index:grid.get_children().indexOf(item)};
  const wrap=new St.BoxLayout({orientation:Clutter.Orientation.VERTICAL,x_expand:true,style_class:'windows-quick-tile',visible:item.visible});
  state.wrap=wrap;wrap.menu=item.menu;wrappers.add(wrap);
  grid.remove_child(item);grid.insert_child_at_index(wrap,state.index);wrap.add_child(item);item.x_expand=true;
  const label=new St.Label({style_class:'windows-quick-caption',x_align:Clutter.ActorAlign.CENTER});
  state.bind=item.bind_property('title',label,'text',GObject.BindingFlags.SYNC_CREATE);wrap.add_child(label);
  const visible=()=>{wrap.visible=Boolean(item.visible&&item.title);};
  state.signal=item.connect('notify::visible',visible);state.titleSignal=item.connect('notify::title',visible);label.clutter_text.ellipsize=Pango.EllipsizeMode.END;visible();
  titleBox.hide();toggle._box.x_align=Clutter.ActorAlign.CENTER;toggle._icon.x_align=Clutter.ActorAlign.CENTER;
  item.add_style_class_name('windows-quick-button');span(wrap,1);states.push(state);
 }
 function sync(){
  if(busy)return;busy=true;
  for(const item of grid.get_children())if(item instanceof QuickToggle||item instanceof QuickMenuToggle)tile(item);
  const system=q._system?._systemItem;
  const sliders=grid.get_children().filter(x=>x instanceof QuickSlider);
  // Brightness before volume; preserve any other native sliders underneath.
  sliders.sort((a,b)=>Number(/brightness/i.test(b.constructor.name))-Number(/brightness/i.test(a.constructor.name)));
  for(const item of [...sliders,system].filter(Boolean))if(item.get_parent()===grid){grid.set_child_above_sibling(item,null);span(item,3);}
  busy=false;
 }
 const changed=grid.connect('child-added',()=>{if(busy||pending)return;pending=GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE,()=>{pending=0;sync();return GLib.SOURCE_REMOVE;});});
 sync();
 const system=q._system?._systemItem;const hidden=[];
 if(system){
  system.add_style_class_name('windows-quick-footer');
  if(system.get_parent()===grid){grid.remove_child(system);menu.box.add_child(system);}
  for(const child of system.child.get_children())if(/ScreenshotItem|LockItem|ShutdownItem/.test(child.constructor.name)){hidden.push([child,child.visible]);child.hide();}
 }
 return ()=>{
  if(system?.get_parent()===menu.box){menu.box.remove_child(system);grid.add_child(system);}
  grid.disconnect(changed);if(pending)GLib.source_remove(pending);busy=true;
  for(const s of states){s.item.disconnect(s.signal);s.item.disconnect(s.titleSignal);s.bind.unbind();s.wrap.remove_child(s.item);grid.remove_child(s.wrap);s.wrap.destroy();grid.add_child(s.item);span(s.item,1);s.item.remove_style_class_name('windows-quick-button');s.titleBox.visible=s.titleVisible;const toggle=s.item instanceof QuickMenuToggle?s.item._box.get_first_child():s.item;toggle._icon.x_align=s.iconAlign;toggle._box.x_align=s.boxAlign;}
  layout.nColumns=columns;
  for(const item of original)if(item.get_parent()===grid){grid.set_child_above_sibling(item,null);if(!(item instanceof QuickToggle||item instanceof QuickMenuToggle))span(item,columns);}
  for(const [child,visible]of hidden)child.visible=visible;
  system?.remove_style_class_name('windows-quick-footer');menu.actor.remove_style_class_name('windows-quick-panel');
 };
}

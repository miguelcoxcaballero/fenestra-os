import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const _LANG=(GLib.getenv('LANGUAGE')||GLib.getenv('LC_MESSAGES')||GLib.getenv('LANG')||'en').split(':')[0].slice(0,2);
const _ES={'Decrease duration':'Reducir duración','Increase duration':'Aumentar duración','Focus':'Concentración'};
const _t=t=>(_LANG==='es'&&_ES[t])||t;
const box=style=>new St.BoxLayout({vertical:true,style_class:style,x_expand:true});
const button=(icon,action,name)=>{const b=new St.Button({style_class:'windows-panel-small-button',can_focus:true,accessible_name:name});b.set_child(new St.Icon({icon_name:icon,icon_size:16}));b.connect('clicked',action);return b;};
export function installCalendarPanel(){
 const d=Main.panel.statusArea.dateMenu, list=d._messageList, area=list.get_parent(), column=d._calendar.get_parent();
 const old={orientation:area.orientation,layout:column.layout_manager,dateVisible:d._date.visible,displaysVisible:d._displaysSection.visible,iconVisible:list._placeholder._icon.visible};
 const settings=new Gio.Settings({schema_id:'org.gnome.desktop.notifications'});
 area.orientation=Clutter.Orientation.VERTICAL;area.add_style_class_name('windows-calendar-stack');
 d.menu.actor.add_style_class_name('windows-calendar-menu');
 column.layout_manager=new Clutter.BoxLayout({orientation:Clutter.Orientation.VERTICAL});column.add_style_class_name('windows-calendar-card');
 const notifications=box('windows-notification-card');area.remove_child(list);area.insert_child_at_index(notifications,0);
 const head=new St.BoxLayout({style_class:'windows-notification-heading'}),title=new St.Label({text:'Notificaciones',x_expand:true,y_align:Clutter.ActorAlign.CENTER});head.add_child(title);
 const dnd=button('notifications-disabled-symbolic',()=>settings.set_boolean('show-banners',!settings.get_boolean('show-banners')),'No molestar');head.add_child(dnd);notifications.add_child(head);notifications.add_child(list);
 const syncDnd=()=>dnd.set_checked(!settings.get_boolean('show-banners'));const ds=settings.connect('changed::show-banners',syncDnd);syncDnd();
 list._placeholder._icon.hide();
 const oldPlaceholder=list._placeholder._label.text;
 list._placeholder._label.text='Sin notificaciones nuevas';
 const cal=d._calendar;
 const oldMonthAlign=cal._monthLabel.x_align;
 const polishMonth=()=>{
  cal._topBox.set_child_at_index(cal._monthLabel,0);cal._monthLabel.x_align=Clutter.ActorAlign.START;
  cal._backButton.icon_name='pan-up-symbolic';cal._forwardButton.icon_name='pan-down-symbolic';
  const month=GLib.DateTime.new_from_unix_local(cal._selectedDate.getTime()/1000).format('%B %Y');
  if(cal._monthLabel.text!==month)cal._monthLabel.text=month;
 };
 polishMonth();const monthId=cal._monthLabel.connect('notify::text',polishMonth);
 const weekdays=[];for(const actor of cal.get_children())if(actor.has_style_class_name?.('calendar-day-heading')){weekdays.push([actor,actor.text]);actor.text=actor.accessible_name?.slice(0,2)??actor.text;}
 const clearSync=()=>{list._clearButton.visible=list._clearButton.reactive;};
 const clearId=list._clearButton.connect('notify::reactive',clearSync);clearSync();

 const header=box('windows-calendar-header'),clock=new St.Label({style_class:'windows-calendar-time'}),date=new St.Label({style_class:'windows-calendar-date'});
 const clockRow=new St.BoxLayout({x_expand:true});clock.x_expand=true;clockRow.add_child(clock);
 const collapse=button('pan-down-symbolic',()=>{d._calendar.visible=!d._calendar.visible;collapse.child.icon_name=d._calendar.visible?'pan-down-symbolic':'pan-up-symbolic';},'Mostrar u ocultar calendario');clockRow.add_child(collapse);
 header.add_child(clockRow);header.add_child(date);column.insert_child_at_index(header,0);d._date.hide();d._displaysSection.hide();
 const tick=()=>{const now=new Date();clock.text=new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(now);date.text=new Intl.DateTimeFormat(undefined,{weekday:'long',day:'numeric',month:'long'}).format(now);};tick();let clockTimer=0;
 const openId=d.menu.connect('open-state-changed',(_m,open)=>{if(clockTimer)GLib.source_remove(clockTimer);clockTimer=0;if(open){tick();clockTimer=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,1,()=>{tick();return GLib.SOURCE_CONTINUE;});}});
 let duration=30,focusTimer=0,remaining=0,priorBanners=true;
 const focusRow=new St.BoxLayout({style_class:'windows-focus-footer'}),durationLabel=new St.Label({text:'30 min',y_align:Clutter.ActorAlign.CENTER});
 const adjust=n=>{if(!focusTimer){duration=Math.max(5,Math.min(240,duration+n));durationLabel.text=`${duration} min`;}};
 focusRow.add_child(button('list-remove-symbolic',()=>adjust(-5),_t('Decrease duration')));focusRow.add_child(durationLabel);focusRow.add_child(button('list-add-symbolic',()=>adjust(5),_t('Increase duration')));
 focusRow.add_child(new St.Widget({x_expand:true}));const focus=new St.Button({label:'▶  '+_t('Focus'),can_focus:true,style_class:'windows-panel-small-button'});focusRow.add_child(focus);column.add_child(focusRow);
 const stop=()=>{if(focusTimer)GLib.source_remove(focusTimer);focusTimer=0;settings.set_boolean('show-banners',priorBanners);focus.label='▶  '+_t('Focus');durationLabel.text=`${duration} min`;};
 focus.connect('clicked',()=>{if(focusTimer){stop();return;}priorBanners=settings.get_boolean('show-banners');settings.set_boolean('show-banners',false);remaining=duration*60;focus.label='■  Terminar';focusTimer=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,1,()=>{remaining--;durationLabel.text=`${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`;if(remaining<=0){focusTimer=0;stop();return GLib.SOURCE_REMOVE;}return GLib.SOURCE_CONTINUE;});});
 return()=>{cal._monthLabel.disconnect(monthId);cal._monthLabel.x_align=oldMonthAlign;cal._topBox.set_child_at_index(cal._backButton,0);cal._backButton.icon_name='pan-start-symbolic';cal._forwardButton.icon_name='pan-end-symbolic';for(const[a,t]of weekdays)a.text=t;list._placeholder._label.text=oldPlaceholder;list._clearButton.disconnect(clearId);list._clearButton.visible=!list._placeholder.visible;if(focusTimer)stop();if(clockTimer)GLib.source_remove(clockTimer);d.menu.disconnect(openId);settings.disconnect(ds);notifications.remove_child(list);area.insert_child_at_index(list,0);notifications.destroy();header.destroy();focusRow.destroy();area.orientation=old.orientation;area.remove_style_class_name('windows-calendar-stack');column.remove_style_class_name('windows-calendar-card');d.menu.actor.remove_style_class_name('windows-calendar-menu');column.layout_manager=old.layout;d._date.visible=old.dateVisible;d._displaysSection.visible=old.displaysVisible;d._calendar.show();list._placeholder._icon.visible=old.iconVisible;};
}

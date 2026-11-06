import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
export function installMediaPanel(){
 const q=Main.panel.statusArea.quickSettings,source=Main.panel.statusArea.dateMenu._messageList._messageView._mediaSource;
 const card=new St.BoxLayout({orientation:Clutter.Orientation.VERTICAL,style_class:'windows-media-card popup-menu-content',visible:false});
 // A separate surface above the native quick settings surface.
 const stack=new St.BoxLayout({orientation:Clutter.Orientation.VERTICAL,style_class:'windows-quick-stack'}),parent=q.menu.box.get_parent(),index=parent.get_children().indexOf(q.menu.box);
 parent.remove_child(q.menu.box);parent.insert_child_at_index(stack,index);stack.add_child(card);stack.add_child(q.menu.box);
 const app=new St.Label({style_class:'windows-media-app'});card.add_child(app);
 const row=new St.BoxLayout({style_class:'windows-media-track'}),text=new St.BoxLayout({orientation:Clutter.Orientation.VERTICAL,x_expand:true});
 const title=new St.Label({style_class:'windows-media-title'}),artist=new St.Label({style_class:'windows-media-artist'});title.clutter_text.ellipsize=3;artist.clutter_text.ellipsize=3;text.add_child(title);text.add_child(artist);row.add_child(text);
 const art=new St.Icon({icon_size:64,style_class:'windows-media-art'});row.add_child(art);card.add_child(row);
 const controls=new St.BoxLayout({x_align:Clutter.ActorAlign.CENTER,style_class:'windows-media-controls'});card.add_child(controls);let selected=null;
 const control=(icon,action,name)=>{const b=new St.Button({can_focus:true,style_class:'windows-media-button',accessible_name:name});b.set_child(new St.Icon({icon_name:icon,icon_size:22}));b.connect('clicked',()=>{if(selected)action(selected);});controls.add_child(b);return b;};
 const prev=control('media-skip-backward-symbolic',p=>p.previous(),'Anterior');control('media-playback-pause-symbolic',p=>p.playPause(),'Pausar');const next=control('media-skip-forward-symbolic',p=>p.next(),'Siguiente');
 const signals=new Map();
 function sync(){selected=source.players.find(p=>p.canPlay&&p.status==='Playing')??null;card.visible=!!selected;if(!selected)return;app.text=selected.app?.get_name()??selected.source?.title??'Multimedia';title.text=selected.trackTitle||'Reproduciendo';artist.text=selected.trackArtists.join(', ');prev.reactive=selected.canGoPrevious;next.reactive=selected.canGoNext;
  const uri=selected.trackCoverUrl;art.gicon=uri?new Gio.FileIcon({file:Gio.File.new_for_uri(uri)}):new Gio.ThemedIcon({name:'audio-x-generic'});
 }
 const watch=p=>{if(!signals.has(p))signals.set(p,p.connect('changed',sync));sync();};
 const added=source.connect('player-added',(_s,p)=>watch(p)),removed=source.connect('player-removed',(_s,p)=>{if(signals.has(p)){p.disconnect(signals.get(p));signals.delete(p);}sync();});source.players.forEach(watch);sync();
 return()=>{source.disconnect(added);source.disconnect(removed);for(const[p,id]of signals)p.disconnect(id);stack.remove_child(q.menu.box);parent.insert_child_at_index(q.menu.box,index);stack.destroy();};
}

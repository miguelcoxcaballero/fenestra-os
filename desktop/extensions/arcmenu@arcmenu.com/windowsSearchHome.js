import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Pango from 'gi://Pango';
import {WindowsSearchResults} from './windowsSearchResults.js';
const fenestraAsset=rel=>{for(const base of [GLib.build_filenamev([GLib.get_user_data_dir(),'fenestra','assets']),'/usr/share/fenestra/assets']){const p=GLib.build_filenamev([base,rel]);if(GLib.file_test(p,GLib.FileTest.EXISTS))return p;}return GLib.build_filenamev(['/usr/share/fenestra/assets',rel]);};

let styleUsers=0;
const stylesheet=Gio.File.new_for_uri(import.meta.url).get_parent().get_child('windows-search.css');
const box=(vertical,cls='')=>new St.BoxLayout({orientation:vertical?Clutter.Orientation.VERTICAL:Clutter.Orientation.HORIZONTAL,x_expand:true,style_class:cls});
const heading=text=>new St.Label({text,style_class:'win-search-heading'});
function button(text,fn,icon=null,cls='win-search-row'){
 const b=new St.Button({can_focus:true,reactive:true,x_expand:true,style_class:cls});
 const row=box(false,'win-search-row-content');
 if(icon)row.add_child(typeof icon==='string'?new St.Icon({icon_name:icon,icon_size:20}):icon);
 const label=new St.Label({text,y_align:Clutter.ActorAlign.CENTER,x_expand:true});label.clutter_text.ellipsize=Pango.EllipsizeMode.END;
 row.add_child(label);b.set_child(row);b.connect('clicked',fn);return b;
}
export class WindowsSearchHome {
 constructor(layout){
  this.layout=layout;this.category='all';this.buttons=new Map();this.destroyed=false;
  this.theme=St.ThemeContext.get_for_stage(global.stage).get_theme();if(styleUsers++===0)this.theme.load_stylesheet(stylesheet);
  layout.add_style_class_name('windows-search-layout');
  this.file=Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_state_dir(),'windows-search','history.json']));
  this.history=[];this.appHistory=[];this.entries=[];
  try{const [ok,data]=this.file.load_contents(null);if(ok){const state=JSON.parse(new TextDecoder().decode(data));this.history=(Array.isArray(state)?state:state.queries??[]).filter(x=>typeof x==='string').slice(0,8);this.appHistory=(state.apps??[]).filter(x=>typeof x==='string').slice(0,10);this.entries=(state.entries??[]).filter(x=>x&&['app','query'].includes(x.kind)&&typeof x.value==='string').slice(0,10);}}catch{}
  this.appSystem=Shell.AppSystem.get_default();
  if(!this.entries.length)this.entries=[...this.history.map(value=>({kind:'query',value,at:null})),...this.appHistory.map(value=>({kind:'app',value,at:null}))].slice(0,10);
  this.filters=box(false,'win-search-filters');
  const iconButton=(icon,cls,fn,name)=>{const b=new St.Button({can_focus:true,reactive:true,style_class:cls,accessible_name:name,y_align:Clutter.ActorAlign.CENTER,child:new St.Icon({icon_name:icon,icon_size:16})});b.connect('clicked',fn);return b;};
  const back=new St.Button({can_focus:true,reactive:true,style_class:'win-search-back',accessible_name:'Back',y_align:Clutter.ActorAlign.CENTER,label:'\u2190'});back.connect('clicked',()=>{layout.searchEntry.setText('');layout.searchEntry.grab_key_focus();});this.filters.add_child(back);
  for(const [id,label]of [['all','All'],['web','Web'],['apps','Apps'],['files','Documents'],['settings','Settings'],['folders','Folders'],['photos','Photos']]){
   const b=button(label,()=>this.filter(id),null,'win-search-filter');b.x_expand=false;b.y_align=Clutter.ActorAlign.CENTER;this.buttons.set(id,b);this.filters.add_child(b);
  }
  const more=new St.Button({can_focus:true,reactive:true,style_class:'win-search-more',accessible_name:'More filters',y_align:Clutter.ActorAlign.CENTER,label:'\u25B6'});more.connect('clicked',()=>{const ids=[...this.buttons.keys()];this.filter(ids[(ids.indexOf(this.category)+1)%ids.length]);});this.filters.add_child(more);
  const spring=new St.Widget({x_expand:true});this.filters.add_child(spring);
  const openSettings=()=>{Gio.Subprocess.new(['fenestra-settings','--page','privacy'],Gio.SubprocessFlags.NONE);layout.arcMenu.close();};
  this.filters.add_child(iconButton('system-users-symbolic','win-search-icon-button',()=>{Gio.Subprocess.new(['fenestra-settings','--page','yourinfo'],Gio.SubprocessFlags.NONE);layout.arcMenu.close();},'Accounts'));
  this.filters.add_child(iconButton('emblem-system-symbolic','win-search-icon-button',openSettings,'Search settings'));
  this.results=new WindowsSearchResults(this);
  this.home=box(true,'win-search-home');
  const top=box(false,'win-search-home-title');this.home.add_child(top);
  const title=heading('Recent searches');title.x_expand=true;title.y_align=Clutter.ActorAlign.CENTER;top.add_child(title);
  const settings=new St.Button({can_focus:true,reactive:true,style_class:'win-search-settings',accessible_name:'Search settings',child:new St.Icon({icon_name:'emblem-system-symbolic',icon_size:16})});
  settings.connect('clicked',()=>{Gio.Subprocess.new(['fenestra-settings','--page','privacy'],Gio.SubprocessFlags.NONE);layout.arcMenu.close();});
  const account=new St.Button({can_focus:true,reactive:true,style_class:'win-search-account',accessible_name:'Accounts',child:new St.Icon({icon_name:'system-users-symbolic',icon_size:16})});
  account.connect('clicked',()=>{Gio.Subprocess.new(['fenestra-settings','--page','yourinfo'],Gio.SubprocessFlags.NONE);layout.arcMenu.close();});
  top.add_child(account);top.add_child(settings);
  this.recent=box(true,'win-search-recent');this.home.add_child(this.recent);
  // Windows 11: "Top apps" under the recent list (most used apps, then pinned ones).
  this.topTitle=heading('Top apps');this.topTitle.add_style_class_name('win-search-top-title');this.home.add_child(this.topTitle);
  this.top=box(false,'win-search-top');this.home.add_child(this.top);
  this.web=button('Search the web',()=>{const q=layout.searchEntry.getText().trim();if(q){this.save(q);Gio.AppInfo.launch_default_for_uri(`https://www.bing.com/search?q=${encodeURIComponent(q)}`,global.create_app_launch_context(0,-1));layout.arcMenu.close();}},'web-browser-symbolic');this.web.visible=false;
  this.originalProvider=layout.searchResults._doProviderSearch;const helper=this;
  layout.searchResults._doProviderSearch=async function(provider,previous){
   const id=provider.id??'';const allow=helper.category==='all'||(helper.category==='apps'&&id==='applications')||(['files','folders','photos'].includes(helper.category)&&/Nautilus|recent-files|nemo/i.test(id))||(helper.category==='settings'&&/Settings|ControlCenter/i.test(id));
   if(!allow){await this._updateResults(provider,this._terms,[]);return;}return helper.originalProvider.call(this,provider,previous);
  };
  this.openId=layout.arcMenu.connect('open-state-changed',(_menu,open)=>{if(open){this.renderRecent();layout.searchEntry.grab_key_focus();}else this.save(layout.searchEntry.getText().trim());});
  // Windows: coloured search glyph, no clear button.
  try{layout.searchEntry._findIcon.gicon=new Gio.FileIcon({file:Gio.File.new_for_path(fenestraAsset('search/search.png'))});layout.searchEntry._findIcon.icon_size=16;}catch{}
  if(layout.searchEntry._clearIcon){layout.searchEntry._clearIcon.opacity=0;layout.searchEntry._clearIcon.reactive=false;}
  layout.searchEntry.hint_text='';layout.searchEntry.add_style_class_name('win-search-entry');this.filter('all');
 }
 persist(){try{GLib.mkdir_with_parents(this.file.get_parent().get_path(),0o700);this.file.replace_contents(JSON.stringify({queries:this.history,apps:this.appHistory,entries:this.entries}),null,false,Gio.FileCreateFlags.PRIVATE,null);}catch(e){console.debug(`Windows search history: ${e.message}`);}}
 remember(kind,value){this.entries=[{kind,value,at:Date.now()},...this.entries.filter(e=>e.kind!==kind||e.value!==value)].slice(0,10);this.persist();}
 save(q){if(!q||q.length>200)return;this.history=[q,...this.history.filter(x=>x!==q)].slice(0,8);this.remember('query',q);}
 launch(app){this.appHistory=[app.get_id(),...this.appHistory.filter(id=>id!==app.get_id())].slice(0,10);this.remember('app',app.get_id());app.activate();this.layout.arcMenu.close();}
 age(at){if(!Number.isFinite(at))return '';const m=Math.max(0,Math.floor((Date.now()-at)/60000));const u=(n,w)=>`${n} ${w}${n===1?'':'s'} ago`;if(m<1)return 'Just now';if(m<60)return u(m,'minute');const h=Math.floor(m/60);return h<24?u(h,'hour'):u(Math.floor(h/24),'day');}
 renderRecent(){
  this.recent.destroy_all_children();let count=0;
  for(const entry of this.entries){
   const app=entry.kind==='app'?this.appSystem.lookup_app(entry.value):null;if(entry.kind==='app'&&!app)continue;
   const b=new St.Button({reactive:true,can_focus:true,x_expand:true,style_class:'win-search-row'});
   const row=box(false,'win-search-row-content');
   const iconBox=new St.Bin({style_class:'win-search-recent-icon',y_align:Clutter.ActorAlign.CENTER,child:app?app.create_icon_texture(32):new St.Icon({icon_name:'system-search-symbolic',icon_size:20})});row.add_child(iconBox);
   const content=box(true,'win-search-recent-text');content.y_align=Clutter.ActorAlign.CENTER;
   const name=new St.Label({text:app?app.get_name():entry.value,style_class:'win-search-recent-name'});name.clutter_text.ellipsize=Pango.EllipsizeMode.END;content.add_child(name);
   content.add_child(new St.Label({text:app?'App':'Search',style_class:'win-search-recent-type'}));row.add_child(content);
   row.add_child(new St.Label({text:this.age(entry.at),style_class:'win-search-age',y_align:Clutter.ActorAlign.CENTER}));b.set_child(row);
   b.connect('clicked',()=>{if(app)this.launch(app);else {this.layout.searchEntry.setText(entry.value);this.layout.searchEntry.grab_key_focus();}});this.recent.add_child(b);count++;
  }
  if(!count){const empty=new St.Label({text:'Your recent searches will appear here.',style_class:'win-search-empty'});empty.clutter_text.line_wrap=true;this.recent.add_child(empty);}
  this.renderTop();
 }
 topApps(){
  const seen=new Set(['fenestra-search.desktop']);const apps=[];
  const add=app=>{if(app&&apps.length<6&&!seen.has(app.get_id())&&app.get_app_info()?.should_show()){seen.add(app.get_id());apps.push(app);}};
  try{Shell.AppUsage.get_default().get_most_used().forEach(add);}catch{}
  try{new Gio.Settings({schema_id:'org.gnome.shell'}).get_strv('favorite-apps').forEach(id=>add(this.appSystem.lookup_app(id)));}catch{}
  for(const id of ['org.gnome.Nautilus.desktop','fenestra-settings.desktop','org.mozilla.firefox.desktop','org.fenestra.Notepad.desktop','org.gnome.TextEditor.desktop','org.gnome.Calculator.desktop','org.gnome.Ptyxis.desktop'])add(this.appSystem.lookup_app(id));
  return apps;
 }
 renderTop(){
  this.top.destroy_all_children();const apps=this.topApps();
  this.topTitle.visible=this.top.visible=apps.length>0;
  for(const app of apps){
   const b=new St.Button({reactive:true,can_focus:true,style_class:'win-search-top-app',accessible_name:app.get_name()});
   const col=box(true,'win-search-top-content');col.add_child(app.create_icon_texture(32));
   const name=new St.Label({text:app.get_name(),style_class:'win-search-top-name',x_align:Clutter.ActorAlign.CENTER});name.clutter_text.ellipsize=Pango.EllipsizeMode.END;col.add_child(name);
   b.set_child(col);b.connect('clicked',()=>this.launch(app));this.top.add_child(b);
  }
 }
 attach(){const l=this.layout;for(const a of [this.filters,this.home,this.web,this.results.actor])if(a.get_parent())a.get_parent().remove_child(a);l.insert_child_at_index(this.filters,1);l.add_child(this.home);l.add_child(this.results.actor);this.update();}
 filter(id){this.category=id;for(const [key,b]of this.buttons){if(key===id)b.add_style_pseudo_class('checked');else b.remove_style_pseudo_class('checked');}const q=this.layout.searchEntry.getText().trim();this.layout.searchResults.setTerms([]);if(q)this.layout.searchResults.setTerms(q.split(/\s+/));this.update();}
 update(){const q=this.layout.searchEntry.getText().trim();this.filters.visible=Boolean(q);this.home.visible=!q;this.web.visible=false;this.layout.applicationsScrollBox.visible=false;this.results.actor.visible=Boolean(q);if(q)this.results.queueRender();}
 destroy(){if(this.destroyed)return;this.destroyed=true;this.layout.arcMenu.disconnect(this.openId);this.layout.searchResults._doProviderSearch=this.originalProvider;this.layout.remove_style_class_name('windows-search-layout');this.layout.searchEntry.remove_style_class_name('win-search-entry');this.results.destroy();for(const a of [this.filters,this.home,this.web])a.destroy();if(--styleUsers===0)this.theme.unload_stylesheet(stylesheet);}
}

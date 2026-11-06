import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
Gio._promisify(Shell.Screenshot.prototype,'screenshot_stage_to_content');Gio._promisify(Shell.Screenshot,'composite_to_stream');
const wait=ms=>new Promise(r=>GLib.timeout_add(GLib.PRIORITY_DEFAULT,ms,()=>{r();return GLib.SOURCE_REMOVE;}));
export default class QA extends Extension {
 enable(){GLib.timeout_add(GLib.PRIORITY_DEFAULT,15000,()=>{this.run().catch(e=>print('QA_FAIL '+e+'\n'+e.stack));return GLib.SOURCE_REMOVE;});}
 async cap(n){try{const sh=new Shell.Screenshot();const [c]=await sh.screenshot_stage_to_content();const t=c.get_texture();const st=Gio.MemoryOutputStream.new_resizable();await Shell.Screenshot.composite_to_stream(t,0,0,-1,-1,1,null,0,0,1,st);st.close(null);GLib.file_set_contents('/out/'+n+'.png',st.steal_as_bytes().toArray());}catch(e){print('QA_FAIL cap '+e);}}
 async run(){
  Main.overview.hide();await wait(800);
  for(const [uuid,e] of Main.extensionManager._extensions){print('QA_EXT '+uuid+' state='+e.state+(e.error?' ERROR='+e.error:''));}
  await this.cap('desktop');
  try{const c=Main.extensionManager.lookup('arcmenu@arcmenu.com')?.stateObj?.menuControllers?.[0];c?._menuButton.toggleMenu();await wait(800);await this.cap('start');c?._menuButton.arcMenu.close();await wait(300);
   c?._runnerMenu?.toggleMenu();await wait(800);await this.cap('search');c?._runnerMenu?.arcMenu.close();}catch(e){print('QA_FAIL arcmenu '+e);}
  await wait(300);try{Main.panel.statusArea.quickSettings.menu.open();await wait(800);await this.cap('quick');Main.panel.statusArea.quickSettings.menu.close();}catch(e){print('QA_FAIL qs '+e);}
  await wait(300);try{Main.panel.statusArea.dateMenu.menu.open();await wait(800);await this.cap('calendar');Main.panel.statusArea.dateMenu.menu.close();}catch(e){print('QA_FAIL cal '+e);}
  try{Gio.Subprocess.new(['gnome-weather'],0);await wait(6000);await this.cap('window');for(const a of global.get_window_actors())print('QA_WIN '+a.meta_window.title+' effects='+a.get_effects().map(e=>e.constructor.name).join(','));}catch(e){print('QA_FAIL win '+e);}
  print('QA_DONE');
 }
 disable(){}
}

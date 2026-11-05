import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import PolkitAgent from 'gi://PolkitAgent';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {styleAuthorization,setConsentMode} from './presentation.js';
export default class FenestraConsent extends Extension {
 enable(){
  this._injections=new InjectionManager();const path=this.path;
  this._injections.overrideMethod(PolkitAgent.Session.prototype,'initiate',original=>function(...args){
   const current=()=>Main.componentManager?._allComponents?.polkitAgent?._currentDialog;
   const d=current();if(d && d._session===this)styleAuthorization(d,path);
   this.connect('request',(_session,request)=>{
    const dialog=current();if(!dialog||dialog._session!==this)return;
    styleAuthorization(dialog,path);
    setConsentMode(dialog);
   });
   return original.apply(this,args);
  });
  this._ready=GLib.build_filenamev([GLib.get_user_runtime_dir(),'fenestra-consent-enabled']);
  GLib.file_set_contents(this._ready,String(new Gio.Credentials().get_unix_pid()));
 }
 disable(){if(this._ready)GLib.unlink(this._ready);this._injections?.clear();}
}

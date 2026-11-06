import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
// GNOME 51 moved the verifier to gdm/userVerifier.js; 49/50 have it in gdm/util.js.
let ShellUserVerifier, MessageType;
try {
    ({ShellUserVerifier, MessageType} = await import('resource:///org/gnome/shell/gdm/userVerifier.js'));
} catch {
    ({ShellUserVerifier, MessageType} = await import('resource:///org/gnome/shell/gdm/util.js'));
}
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {UnlockDialog} from 'resource:///org/gnome/shell/ui/unlockDialog.js';
import {createClockFace} from './face.js';

export default class WindowsLockClock extends Extension {
    enable() {
        this._injections=new InjectionManager();this._dialogs=new Map();
        const ext=this;
        this._injections.overrideMethod(UnlockDialog.prototype,'_init',original=>function(...args){
            original.apply(this,args);ext._attach(this);
        });
        this._injections.overrideMethod(UnlockDialog.prototype,'_setTransitionProgress',original=>function(progress){
            if(ext._dialogs.has(this))ext._sync(this,progress);
            else original.call(this,progress);
        });
        this._injections.overrideMethod(UnlockDialog.prototype,'_showPrompt',original=>function(...args){
            if(!ext._dialogs.has(this))return original.apply(this,args);
            this._ensureAuthPrompt();
            if(this._activePage===this._promptBox)return;
            this._activePage=this._promptBox;
            this._adjustment.ease(1,{duration:300,mode:Clutter.AnimationMode.EASE_OUT_CUBIC});
        });
        // Fast unlock: once a service has authenticated, GNOME still waits for the
        // verifier's message queue to drain before hiding the lock screen. Each
        // queued hint stays up for max(2 s, 48 ms/char), so a fingerprint prompt
        // ("Place your finger…") or Howdy notice that happened to be on screen
        // delayed the desktop by ~1.5 s. Drop those hints on success; keep only
        // the succeeding service's short success messages (the 260 ms Hello tick).
        if(typeof ShellUserVerifier.prototype._onVerificationComplete==='function')this._injections.overrideMethod(ShellUserVerifier.prototype,'_onVerificationComplete',original=>function(client,serviceName){
            try{
                const queue=this._messageQueue??[];
                const keep=queue.filter(m=>m.serviceName===serviceName&&m.text&&m.interval<=400);
                if(keep.length!==queue.length){
                    if(this._messageQueueTimeoutId){GLib.source_remove(this._messageQueueTimeoutId);this._messageQueueTimeoutId=0;}
                    if(keep.length){this._messageQueue=keep;this._queueMessageTimeout();}
                    else (this.finishMessageQueue??this._finishMessageQueue).call(this);
                }
            }catch(e){console.warn(`Fenestra fast unlock: ${e.message}`);}
            return original.call(this,client,serviceName);
        });
        const dialog=Main.screenShield?._dialog;
        if(dialog?._clock)this._attach(dialog);
    }
    _attach(dialog) {
        if(this._dialogs.has(dialog))return;
        const face=createClockFace(dialog);
        face.dimmer=new St.Widget({reactive:false,opacity:0,style:'background-color: black;'});
        face.dimmer.add_constraint(new Clutter.BindConstraint({source:dialog,coordinate:Clutter.BindCoordinate.SIZE}));
        dialog.insert_child_above(face.dimmer,dialog._backgroundGroup);
        this._dialogs.set(dialog,face);
        dialog.connectObject('destroy',()=>this._dialogs.delete(dialog),this);
        this._sync(dialog,dialog._adjustment.value);
    }
    _sync(dialog,progress) {
        const face=this._dialogs.get(dialog);if(!face)return;
        // Keep GNOME's native clock layout for authentication transitions,
        // displaying the same independent clock component used by GDM.
        dialog._clock.opacity=0;
        dialog._clock.visible=progress<1;
        dialog._promptBox.visible=progress>0;
        dialog._otherUserButton.set({reactive:progress>0,can_focus:progress>0,opacity:255*progress,scale_x:1,scale_y:1,translation_y:0});
        face.actor.visible=progress<1;
        const p=Math.max(0,Math.min(1,progress));
        face.actor.opacity=255*(1-p);
        face.actor.translation_y=-Math.round(Main.layoutManager.primaryMonitor.height*0.12)*p;
        face.dimmer.opacity=82*p;
        dialog._promptBox.scale_x=1;dialog._promptBox.scale_y=1;
        dialog._promptBox.translation_y=16*(1-p);
        dialog._promptBox.opacity=255*Math.max(0,(p-0.25)/0.75);
    }
    disable() {
        this._injections?.clear();
        for(const [dialog,face] of this._dialogs){
            dialog.disconnectObject(this);face.dimmer.destroy();face.destroy();
            dialog._setTransitionProgress(dialog._adjustment.value);
        }
        this._dialogs.clear();
    }
}

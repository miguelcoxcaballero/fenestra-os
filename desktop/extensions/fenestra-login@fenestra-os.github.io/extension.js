import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import {createClockFace, createNativeBackground, watchBackground} from './face.js';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {LoginDialog} from 'resource:///org/gnome/shell/gdm/loginDialog.js';
import {installLoginRaceGuard} from './login-race.js';

export default class SingleUser extends Extension {
    enable() {
        if (!Main.sessionMode.isGreeter) return;
        this._injections=new InjectionManager();
        this._attachRaceGuard=installLoginRaceGuard(this._injections,LoginDialog);
        let attempts=0;
        this._timer=GLib.timeout_add(GLib.PRIORITY_DEFAULT,100,()=>{
            const dialog=Main.screenShield?._dialog;
            if(++attempts>300) {this._timer=0;return GLib.SOURCE_REMOVE;}
            if(!dialog?._userListLoaded || !dialog._userSelectionBox?.mapped) return GLib.SOURCE_CONTINUE;
            this._timer=0;
            this._showCurtain(dialog);
            return GLib.SOURCE_REMOVE;
        });
    }
    _showCurtain(dialog) {
        this._attachRaceGuard(dialog);
        this._dismissing=false;
        this._dialog=dialog;
        this._listOpacity=dialog._userSelectionBox.opacity;
        dialog._userSelectionBox.opacity=0;
        const sharedBackground=!!dialog._windowsDimmer;
        this._curtain=new St.Widget({reactive:true,can_focus:true,style:sharedBackground?'background-color: transparent;':'background-color: black;'});
        this._curtain.add_constraint(new Clutter.BindConstraint({source:Main.layoutManager.screenShieldGroup,coordinate:Clutter.BindCoordinate.ALL}));
        Main.layoutManager.screenShieldGroup.add_child(this._curtain);
        this._backgrounds=sharedBackground?[]:Main.layoutManager.monitors.map((_m,i)=>createNativeBackground(this._curtain,i));
        this._face=createClockFace(this._curtain);
        this._unwatch=watchBackground(()=>this._backgrounds?.forEach(actor=>actor._windowsReload()));
        this._curtain.connect('key-press-event',(_actor,event)=>{
            if([Clutter.KEY_Return,Clutter.KEY_KP_Enter,Clutter.KEY_space].includes(event.get_key_symbol())) this._dismiss(dialog);
            return Clutter.EVENT_STOP;
        });
        this._curtain.connect('button-release-event',()=>{this._dismiss(dialog);return Clutter.EVENT_STOP;});
        this._grab=Main.pushModal(this._curtain,{actionMode:Shell.ActionMode.LOGIN_SCREEN});
        this._curtain.grab_key_focus();
        console.log('GDM clock: waiting for user interaction');
    }
    _dismiss(dialog) {
        if(this._dismissing)return;
        this._dismissing=true;
        // Swap identical backgrounds in one frame; never crossfade two photos.
        this._curtain.set_style('background-color: transparent;');
        this._backgrounds?.forEach(actor=>actor.hide());
        const oldListOpacity=this._listOpacity;
        dialog._userSelectionBox.opacity=0;
        dialog._windowsDimmer?.ease({opacity:82,duration:300,mode:Clutter.AnimationMode.EASE_OUT_CUBIC});
        this._face.actor.ease({opacity:0,translation_y:-Math.round(Main.layoutManager.primaryMonitor.height*0.12),duration:300,mode:Clutter.AnimationMode.EASE_OUT_CUBIC,onComplete:()=>{
            this._cleanup();
            dialog._userSelectionBox.opacity=oldListOpacity;
            const items=[...dialog._userList._items.values()];
            if(items.length===1 && items[0].user.is_loaded && !items[0].user.locked) {
                // The clock has replaced the user list; do not clone/fade that
                // hidden list back over the profile when starting verification.
                dialog._userSelectionBox.hide();
                dialog._user=items[0].user;
                dialog._updateCancelButton();
                dialog._conflictingSessionNotification?.destroy();
                dialog._beginVerificationForItem(items[0]);
                dialog._showPrompt();
            }
            else dialog._userList.grab_key_focus();
        }});
    }

    _cleanup() {
        if(this._grab) {Main.popModal(this._grab);this._grab=null;}
        this._unwatch?.();this._unwatch=null;
        this._face?.destroy();this._face=null;
        this._curtain?.destroy();this._curtain=null;this._backgrounds=null;
    }
    disable() {
        if(this._timer) GLib.source_remove(this._timer);
        this._timer=0;
        this._injections?.clear();
        if(this._dialog && this._curtain)this._dialog._userSelectionBox.opacity=this._listOpacity;
        this._cleanup();
    }
}

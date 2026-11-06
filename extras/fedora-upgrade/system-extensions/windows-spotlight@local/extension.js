import {installLockControls} from './lockControls.js';
import {installLockStatus} from './lockStatus.js';
import {installStartupCover} from './startup.js';
import {installTransitions} from './transitions.js';
import {installPanelGuard} from './panelGuard.js';
import {installHelloFeedback} from './hello.js';
import Clutter from 'gi://Clutter';
import {backgroundStyle, watchBackground, createNativeBackground} from './face.js';
import GLib from 'gi://GLib';
import St from 'gi://St';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {UnlockDialog} from 'resource:///org/gnome/shell/ui/unlockDialog.js';
import {LoginDialog} from 'resource:///org/gnome/shell/gdm/loginDialog.js';

export default class WindowsSpotlight extends Extension {
    enable() {
        this._injections = new InjectionManager();
        this._stopLockControls=installLockControls();
        this._stopTransitions=installTransitions(this._injections);
        this._stopStartup=installStartupCover();
        this._stopHello=installHelloFeedback(this._injections,this.path);
        this._stopPanelGuard=installPanelGuard({Main,GLib,St,shellGlobal:global});
        try{this._stopLockStatus=installLockStatus(this.path);}catch(e){logError(e,'Fenestra lock status');this._stopLockStatus=null;}
        // GDM's gear chooses a desktop session; it is not Windows settings.
        this._injections.overrideMethod(LoginDialog.prototype, '_shouldShowSessionMenuButton', () => function() {return false;});
        const ext = this;
        this._readImage();
        this._injections.overrideMethod(UnlockDialog.prototype, '_createBackground', original => function(index) {
            if (!ext._image) return original.call(this, index);
            createNativeBackground(this._backgroundGroup,index);
        });
        if (Main.sessionMode.isGreeter) {
            this._injections.overrideMethod(LoginDialog.prototype, '_init', original => function(...args) {
                original.apply(this,args);
                ext._applyGreeter(this);
            });
        }
        this._refresh();
        this._unwatch=watchBackground(()=>{this._readImage();this._refresh();});
        this._injections.overrideMethod(Main.screenShield,'_resetLockScreen',original=>function(...args){
            const result=original.apply(this,args);
            ext._readImage();ext._refresh();return result;
        });
    }
    _readImage() {
        try {
            const [,bytes]=GLib.file_get_contents('/var/lib/windows-spotlight/current.json');
            const path=JSON.parse(new TextDecoder().decode(bytes)).image;
            if (/^\/var\/lib\/windows-spotlight\/images\/[a-f0-9]{64}\.jpg$/.test(path)) this._image=path;
        } catch(e) { console.warn(`Windows Spotlight: ${e.message}`); }
    }
    _style() {return backgroundStyle();}
    _applyGreeter(dialog) {
        dialog._sessionMenuButton?.hide();
        if (!this._image) return;
        if (this._greeter !== dialog) {
            this._greeter=dialog; this._oldStyle=dialog.get_style();
            dialog.connectObject('destroy',()=>{this._gdmBackdrop=null;this._greeter=null;},this);
        }
        if(!this._gdmBackdrop) {
            this._gdmBackdrop=new St.Widget({reactive:false});
            this._gdmBackdrop.add_constraint(new Clutter.BindConstraint({source:Main.layoutManager.screenShieldGroup,coordinate:Clutter.BindCoordinate.SIZE}));
            dialog.get_parent().insert_child_below(this._gdmBackdrop,dialog);
            for(let i=0;i<Main.layoutManager.monitors.length;i++)createNativeBackground(this._gdmBackdrop,i);
            const shade=new St.Widget({reactive:false,opacity:0,style:'background-color: black;'});
            shade.add_constraint(new Clutter.BindConstraint({source:this._gdmBackdrop,coordinate:Clutter.BindCoordinate.SIZE}));
            this._gdmBackdrop.add_child(shade);dialog._windowsDimmer=shade;
        }
        this._gdmBackdrop.set_style('background-color: black;');
        for(const child of this._gdmBackdrop.get_children())child._windowsReload?.();
        dialog.set_style('background-image: none; background-color: transparent;');
    }
    _refresh() {
        const dialog=Main.screenShield?._dialog;
        if (!dialog) return;
        if (Main.sessionMode.isGreeter) this._applyGreeter(dialog);
        else if (dialog._updateBackgrounds) {
            const children=dialog._backgroundGroup.get_children();
            if(children.length && children.every(child=>child._windowsReload))
                children.forEach(child=>child._windowsReload());
            else dialog._updateBackgrounds();
        }
    }
    disable() {
        this._stopLockControls?.();this._stopLockControls=null;
        this._stopLockStatus?.();this._stopLockStatus=null;
        this._stopStartup?.();this._stopStartup=null;
        this._stopTransitions?.();this._stopTransitions=null;
        this._stopHello?.();this._stopHello=null;
        this._stopPanelGuard?.();this._stopPanelGuard=null;
        if(this._timeout) GLib.source_remove(this._timeout);
        this._timeout=0;
        this._unwatch?.();this._unwatch=null;
        this._injections?.clear();
        this._gdmBackdrop?.destroy();this._gdmBackdrop=null;
        if(this._greeter) {
            delete this._greeter._windowsDimmer;
            this._greeter.set_style(this._oldStyle);
            this._greeter.disconnectObject(this);
            this._greeter=null;
        }
        if(!Main.sessionMode.isGreeter) Main.screenShield?._dialog?._updateBackgrounds?.();
    }
}

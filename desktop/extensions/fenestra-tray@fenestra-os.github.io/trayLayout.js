import Clutter from 'gi://Clutter';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

// Windows 11 tray metrics (logical px), measured against a Windows screenshot.
export const TRAY={overflowPad:10,kbPad:7,quickPad:3,iconGap:4,datePad:10,kbFont:12,clockFont:12,clockSpacing:-0.4,dy:{overflow:1,kb:1,wifi:1,vol:1,clock:0}};
export function installTrayLayout(injections) {
    const saved=new Map();let bluetooth=null,bluetoothId=0;let closed=false;
    const style=(actor,value)=>{if(!actor)return;if(!saved.has(actor))saved.set(actor,actor.get_style());actor.set_style(value);};
    const overflow=new PanelMenu.Button(0.5,'Mostrar iconos ocultos');
    overflow.add_child(new St.Icon({icon_name:'pan-up-symbolic',icon_size:12,style:'icon-size: 12px;'}));
    style(overflow,`-natural-hpadding: ${TRAY.overflowPad}px; -minimum-hpadding: ${TRAY.overflowPad}px; min-width: 16px; border-radius: 4px;`);
    overflow.get_first_child().translation_y=TRAY.dy.overflow;
    const bt=new PopupMenu.PopupImageMenuItem('Bluetooth','bluetooth-active-symbolic');
    bt.connect('activate',()=>Gio.Subprocess.new(['fenestra-settings','--page','bluetooth'],Gio.SubprocessFlags.NONE));overflow.menu.addMenuItem(bt);
    Main.panel.addToStatusArea('windowsOverflow',overflow,0,'right');
    const keyboard=Main.panel.statusArea.keyboard;
    const formatKeyboard=()=>{
        if(closed||!keyboard)return;
        const source=keyboard._inputSourceManager?.currentSource;
        if(!source)return;
        const locale=GLib.get_language_names()[0].split(/[_.@-]/)[0];
        const language={C:'ENG',en:'ENG',es:'ESP',fr:'FRA',de:'DEU',it:'ITA',pt:'POR'}[locale]??locale.toUpperCase();
        const layout=(source.id.split('+')[0]||source.shortName).toUpperCase();
        for(const [key,label] of Object.entries(keyboard._indicatorLabels)){
            label.visible=Number(key)===source.index;
            if(label.visible){label.text=`${language}\n${layout}`;style(label,`font-family: "Fenestra Taskbar Text"; font-size: ${TRAY.kbFont}px; font-weight: 400; text-align: center; `);label.translation_y=TRAY.dy.kb;}
        }
        keyboard.show();style(keyboard,`-natural-hpadding: ${TRAY.kbPad}px; -minimum-hpadding: ${TRAY.kbPad}px; min-width: 24px; border-radius: 4px;`);
    };
    if(keyboard)injections.overrideMethod(keyboard,'_currentSourceChanged',original=>function(...args){original.apply(this,args);formatKeyboard();});
    function sync() {
        if(closed)return;
        const q=Main.panel.statusArea.quickSettings;
        if(q){
            style(q,`-natural-hpadding: ${TRAY.quickPad}px; -minimum-hpadding: ${TRAY.quickPad}px; border-radius: 4px;`);
            if(q._network?._primaryIndicator)q._network._primaryIndicator.translation_y=TRAY.dy.wifi;
            if(q._volumeOutput?._indicator)q._volumeOutput._indicator.translation_y=TRAY.dy.vol;
            style(q._indicators,`spacing: ${TRAY.iconGap}px;`);
            for(const indicator of [q._network,q._volumeOutput,q._system]){
                if(indicator)style(indicator,'spacing: 0px; padding: 0px;');
            }
            style(q._network?._primaryIndicator,'icon-size: 16px; min-width: 16px; min-height: 16px;');
            style(q._volumeOutput?._indicator,'icon-size: 16px; min-width: 16px; min-height: 16px;');
            if(q._system?._percentageLabel)q._system._percentageLabel.hide();
            if(q._bluetooth&&bluetooth!==q._bluetooth){
                if(bluetoothId)bluetooth.disconnect(bluetoothId);
                bluetooth=q._bluetooth;bluetoothId=bluetooth.connect('notify::visible',()=>{if(!closed&&bluetooth.visible)bluetooth.hide();});bluetooth.hide();
            }
        }
        formatKeyboard();
        const date=Main.panel.statusArea.dateMenu;
        style(date,`-natural-hpadding: ${TRAY.datePad}px; -minimum-hpadding: ${TRAY.datePad}px; border-radius: 4px;`);
        if(date?._clockDisplay){date._clockDisplay.translation_y=TRAY.dy.clock;date._clockDisplay.set_style(`font-family: "Fenestra Taskbar Text"; font-size: ${TRAY.clockFont}px; font-weight: 400; text-align: right; letter-spacing: ${TRAY.clockSpacing}px; padding: 0; margin: 0;`);}
        style(date?._clockDisplay?.get_parent(),'spacing: 0; padding: 0; margin: 0;');
        // All standard right-side indicators share the right box; keep native
        // menus and action handlers, only reorder their existing containers.
        const parent=keyboard?.container?.get_parent();
        if(parent&&overflow.container.get_parent()===parent){
            const children=parent.get_children();
            const target=Math.max(0,children.indexOf(keyboard.container)-1);
            // set_child_at_index() always re-inserts and relayouts the whole panel.
            if(children.indexOf(overflow.container)!==target)parent.set_child_at_index(overflow.container,target);
        }
    }
    // Event-driven: re-apply when the right box / quick settings indicators change
    // (coalesced to one idle pass). A slow safety net replaces the old 2 s poll.
    let idleId=0;const watched=[];
    const queueSync=()=>{if(idleId||closed)return;idleId=GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE,()=>{idleId=0;sync();return GLib.SOURCE_REMOVE;});};
    const watch=(obj,...signals)=>{if(obj)for(const s of signals)watched.push([obj,obj.connect(s,queueSync)]);};
    watch(Main.panel._rightBox,'child-added','child-removed');
    watch(Main.panel.statusArea.quickSettings?._indicators,'child-added');
    watch(Main.sessionMode,'updated');
    sync();let ticks=0;
    const timer=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,2,()=>{
        // Quick Settings builds its indicators asynchronously right after login:
        // settle every 2 s for the first 20 s, then every 30 s.
        sync();
        if(++ticks===10){timers.slow=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,30,()=>{sync();return GLib.SOURCE_CONTINUE;});timers.fast=0;return GLib.SOURCE_REMOVE;}
        return GLib.SOURCE_CONTINUE;
    });
    const timers={fast:timer,slow:0};
    return ()=>{closed=true;if(timers.fast)GLib.source_remove(timers.fast);if(timers.slow)GLib.source_remove(timers.slow);if(idleId)GLib.source_remove(idleId);for(const [o,id] of watched){try{o.disconnect(id);}catch{}}if(bluetoothId)bluetooth.disconnect(bluetoothId);for(const [actor,old]of saved){try{actor.set_style(old);}catch{}}saved.clear();overflow.destroy();keyboard?._currentSourceChanged(keyboard._inputSourceManager,null);bluetooth?._sync?.();};
}

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {createNativeBackground} from './face.js';

// Keep the login photo visible while the new user's desktop builds behind it.
// A bounded timeout and explicit teardown prevent a stuck startup cover.
export function installStartupCover() {
    const layout = Main.layoutManager;
    if (!layout._startingUp || Main.sessionMode.isGreeter) return () => {};
    let cover = new St.Widget({reactive:true,style:'background-color:#202020;',
        width:global.screen_width,height:global.screen_height});
    let timer=0,signal=0;
    const cleanup=()=>{
        if(timer)GLib.source_remove(timer);timer=0;
        if(signal)layout.disconnect(signal);signal=0;
        const old=cover;cover=null;old?.destroy();
    };
    try {
        for(let i=0;i<layout.monitors.length;i++)createNativeBackground(cover,i);
        layout.addTopChrome(cover,{trackFullscreen:true});
    } catch(e) {cleanup();console.warn(`Startup cover: ${e.message}`);return ()=>{};}
    const reveal=()=>{
        if(!cover)return;
        if(timer)GLib.source_remove(timer);timer=0;
        cover.ease({opacity:0,duration:160,mode:Clutter.AnimationMode.EASE_OUT_QUAD,onStopped:cleanup});
    };
    const ready=()=>{
        if(signal)layout.disconnect(signal);signal=0;
        reveal();
    };
    signal=layout.connect('startup-complete',ready);
    timer=GLib.timeout_add(GLib.PRIORITY_DEFAULT,750,()=>{timer=0;reveal();return GLib.SOURCE_REMOVE;});
    return cleanup;
}

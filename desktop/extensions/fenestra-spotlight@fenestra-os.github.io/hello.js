import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import {AuthPrompt} from 'resource:///org/gnome/shell/gdm/authPrompt.js';
// GNOME 51 moved the verifier to gdm/userVerifier.js; 49/50 have it in gdm/util.js.
let ShellUserVerifier, MessageType;
// (Checked first, so GNOME 49 doesn't log a failed import every start.)
const hasResource = path => { try { Gio.resources_get_info(path, 0); return true; } catch { return false; } };
if (hasResource('/org/gnome/shell/gdm/userVerifier.js')) {
    ({ShellUserVerifier, MessageType} = await import('resource:///org/gnome/shell/gdm/userVerifier.js'));
} else {
    ({ShellUserVerifier, MessageType} = await import('resource:///org/gnome/shell/gdm/util.js'));
}
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const fenestraAsset=rel=>{for(const base of [GLib.build_filenamev([GLib.get_user_data_dir(),'fenestra','assets']),'/usr/share/fenestra/assets']){const p=GLib.build_filenamev([base,rel]);if(GLib.file_test(p,GLib.FileTest.EXISTS))return p;}return GLib.build_filenamev(['/usr/share/fenestra/assets',rel]);};

export function faceMessage(service, message) {
    if(service !== 'gdm-password' || typeof message !== 'string')return null;
    if(/Attempting facial authentication|Intentando (?:la )?autenticaci[oó]n facial/i.test(message))return 'searching';
    if(/Identified face as|(?:Rostro|Cara) identificad[oa] como/i.test(message))return 'authentication';
    return null;
}
export const SUCCESS_ANIMATION_MS=260;
export const SUCCESS_MESSAGE_MS=260;

export function frameAt(sequence, time) {
    let lo=0,hi=sequence.frames.length-1;
    while(lo<hi){const mid=(lo+hi)>>1;if(time<sequence.ends[mid])hi=mid;else lo=mid+1;}
    return sequence.frames[lo].file;
}
export function compileSequence(frames) {
    let duration=0;const ends=frames.map(f=>duration+=f.duration);
    return {frames,ends,duration};
}

export function installHelloFeedback(injections, path) {
    const [,raw]=GLib.file_get_contents(`${fenestraAsset('hello')}/frames.json`);
    const sequences=Object.fromEntries(Object.entries(JSON.parse(new TextDecoder().decode(raw))).map(([name,seq])=>[name,compileSequence(seq)]));
    const cache=St.TextureCache.get_default();
    const scale=St.ThemeContext.get_for_stage(global.stage).scale_factor;
    const icons=new Map(),warm=[];
    for(const seq of Object.values(sequences))for(const frame of seq.frames){
        if(!icons.has(frame.file))icons.set(frame.file,new Gio.FileIcon({file:Gio.File.new_for_path(`${fenestraAsset('hello')}/${frame.file}`)}));
    }
    const pending=[...icons.values()];let warmId=0;
    // Decode off the authentication path, in small nonblocking batches, but only
    // when a lock/login screen is about to need the frames: warming at session
    // start competed with the desktop's own startup for nothing.
    const warmUp=()=>{
        if(warmId||!pending.length)return;
        warmId=GLib.idle_add(GLib.PRIORITY_LOW,()=>{
            for(let n=0;n<6&&pending.length;n++){
                const actor=cache.load_gicon(null,pending.shift(),64,scale,1);
                if(actor)warm.push(actor);
            }
            if(pending.length)return GLib.SOURCE_CONTINUE;
            warmId=0;return GLib.SOURCE_REMOVE;
        });
    };
    let shieldId=0;
    if(Main.sessionMode.isGreeter||Main.screenShield?.active)warmUp();
    else if(Main.screenShield)shieldId=Main.screenShield.connect('active-changed',()=>{if(Main.screenShield.active)warmUp();});
    // Preserve native queues and completion callbacks, shortening only the two
    // informational Howdy notices. Password, fingerprint and errors are intact.
    injections.overrideMethod(ShellUserVerifier.prototype,'_queueMessage',original=>function(...args){
        const obj=args.length===1&&args[0]&&typeof args[0]==='object';
        const [service,message,type]=obj?[args[0].serviceName,args[0].message,args[0].messageType]:args;
        const mode=faceMessage(service,message);
        if(!mode || type!==MessageType.INFO)return original.apply(this,args);
        this._messageQueue.push({serviceName:service,text:message,type,wiggle:obj?args[0].wiggle:undefined,interval:mode==='searching'?0:SUCCESS_MESSAGE_MS});
        this._queueMessageTimeout();
    });
    const prompts=new Map();
    function attach(prompt){
        if(prompts.has(prompt))return;
        const box=new St.Widget({width:64,height:64,opacity:0,reactive:false,
            x_align:Clutter.ActorAlign.CENTER,layout_manager:new Clutter.BinLayout(),style:'margin: 8px 0; padding: 0;'});
        prompt.insert_child_at_index(box,1);
        const frames=new Map();
        for(const [file,gicon] of icons){
            const actor=cache.load_gicon(null,gicon,64,scale,1);
            if(actor){actor.set_size(64,64);actor.hide();box.add_child(actor);frames.set(file,actor);}
        }
        const state={box,frames,timeline:null,signals:[],verifier:prompt._userVerifier,mode:null,current:null};
        prompts.set(prompt,state);
        function select(file){
            if(file===state.current)return;
            frames.get(state.current)?.hide();frames.get(file)?.show();state.current=file;
        }
        function stop(hide=true){
            state.timeline?.stop();state.timeline=null;state.mode=null;
            if(hide)box.opacity=0;
        }
        function play(mode){
            if(state.mode===mode)return;
            stop(false);state.mode=mode;box.opacity=255;
            const sequence=sequences[mode];
            const duration=mode==='authentication'?SUCCESS_ANIMATION_MS:sequence.duration;
            const timeline=new Clutter.Timeline({actor:box,duration,repeat_count:mode==='searching'?-1:0});
            timeline.connect('new-frame',(_t,elapsed)=>select(frameAt(sequence,Math.min(sequence.duration-1,elapsed*sequence.duration/duration))));
            timeline.connect('completed',()=>{
                if(mode==='authentication')select(sequence.frames.at(-1).file);
            });
            state.timeline=timeline;select(sequence.frames[0].file);timeline.start();
        }
        const connect=(signal,callback)=>state.signals.push(state.verifier.connect(signal,callback));
        connect('show-message',(_v,service,message)=>{const mode=faceMessage(service,message);if(mode)play(mode);});
        connect('ask-question',(_v,service)=>{if(service==='gdm-password')stop();});
        connect('verification-failed',()=>stop());
        connect('reset',()=>stop());
        connect('verification-complete',()=>{if(state.mode!=='authentication')stop();});
        state.destroyId=prompt.connect('destroy',()=>{
            stop();state.signals.forEach(id=>{try{state.verifier.disconnect(id);}catch{}});prompts.delete(prompt);
        });
        state.stop=stop;
    }
    injections.overrideMethod(AuthPrompt.prototype,'_init',original=>function(...args){original.apply(this,args);attach(this);});
    const existing=Main.screenShield?._dialog?._authPrompt;if(existing)attach(existing);
    return ()=>{
        if(warmId)GLib.source_remove(warmId);
        if(shieldId)Main.screenShield.disconnect(shieldId);
        for(const [prompt,state] of prompts){
            state.stop();state.signals.forEach(id=>{try{state.verifier.disconnect(id);}catch{}});
            prompt.disconnect(state.destroyId);state.box.destroy();
        }
        warm.forEach(actor=>actor.destroy());prompts.clear();icons.clear();
    };
}

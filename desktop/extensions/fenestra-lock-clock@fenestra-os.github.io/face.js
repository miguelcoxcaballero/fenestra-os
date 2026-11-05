import Meta from 'gi://Meta';
import GDesktopEnums from 'gi://GDesktopEnums';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GnomeDesktop from 'gi://GnomeDesktop';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export function backgroundStyle() {
    let style='background-color: #202020;';
    try {
        const [,bytes]=GLib.file_get_contents('/var/lib/fenestra-spotlight/current.json');
        const path=JSON.parse(new TextDecoder().decode(bytes)).image;
        if(/^\/(var\/lib\/fenestra-spotlight\/images\/[a-f0-9]{64}|usr\/share\/backgrounds\/fenestra\/[A-Za-z0-9._-]+)\.jpg$/.test(path))
            style+=`background-image: url("${path}"); background-size: cover;`;
    } catch(e) { console.warn(`Fenestra background: ${e.message}`); }
    return style;
}
export function watchBackground(update) {
    const monitor=Gio.File.new_for_path('/var/lib/fenestra-spotlight').monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES,null);
    let pending=0;
    monitor.connect('changed',(_monitor,file,other)=>{
        if(file?.get_basename()!=='current.json' && other?.get_basename()!=='current.json') return;
        if(pending) GLib.source_remove(pending);
        pending=GLib.timeout_add(GLib.PRIORITY_DEFAULT,150,()=>{
            pending=0;update();return GLib.SOURCE_REMOVE;
        });
    });
    return ()=>{if(pending) GLib.source_remove(pending);monitor.cancel();};
}
// BCP 47 tag for the system locale (/etc/locale.conf), e.g. "en-US" or "es-ES".
function systemLocale() {
    let lang='';
    try {
        const [,bytes]=GLib.file_get_contents('/etc/locale.conf');
        const text=new TextDecoder().decode(bytes);
        lang=(text.match(/^LC_TIME="?([^"\n]+)"?/m)??text.match(/^LANG="?([^"\n]+)"?/m)??[])[1]??'';
    } catch(e) {}
    lang=lang||GLib.get_language_names()[0]||'';
    const tag=lang.split('.')[0].split('@')[0].replace('_','-');
    try { return Intl.DateTimeFormat.supportedLocalesOf([tag]).length?tag:undefined; } catch(e) { return undefined; }
}
export function createClockFace(parent) {
    const box=new St.BoxLayout({orientation:Clutter.Orientation.VERTICAL,reactive:false,style:'spacing: 0; padding: 0; margin: 0;'});
    const time=new St.Label({x_align:Clutter.ActorAlign.CENTER,style:'font-family: "Segoe UI Variable"; font-size: 96px; font-weight: 600; color: white; margin: 0; padding: 0;'});
    const date=new St.Label({x_align:Clutter.ActorAlign.CENTER,style:'font-family: "Segoe UI Variable"; font-size: 18px; font-weight: 400; color: white; margin: 0; padding: 0;'});
    box.add_child(time);box.add_child(date);parent.add_child(box);
    const clock=new GnomeDesktop.WallClock({time_only:true});
    const locale=systemLocale();
    const update=()=>{
        // Same locale (the system one chosen in setup) in the user session and GDM.
        const now=new Date();
        time.text=new Intl.DateTimeFormat(locale,{hour:'numeric',minute:'2-digit'}).format(now).replace(/\s*[AaPp]\.?\s?[Mm]\.?$/,'');
        date.text=new Intl.DateTimeFormat(locale,{weekday:'long',day:'numeric',month:'long'}).format(now);
    };
    clock.connect('notify::clock',update);update();
    const place=()=>{
        const m=Main.layoutManager.primaryMonitor;
        if(m) {box.set_position(m.x,m.y+m.height*0.13);box.set_width(m.width);}
    };
    const allocation=parent.connect('notify::allocation',place);
    const monitors=Main.layoutManager.connect('monitors-changed',place);place();
    let destroyed=false;
    const dispose=()=>{
        if(destroyed)return;destroyed=true;
        Main.layoutManager.disconnect(monitors);parent.disconnect(allocation);
        clock.run_dispose();
    };
    box.connect('destroy',dispose);
    return {actor:box,destroy:()=>{dispose();box.destroy();}};
}

export function createNativeBackground(container,monitorIndex) {
    const m=Main.layoutManager.monitors[monitorIndex];
    const actor=new Meta.BackgroundActor({meta_display:global.display,monitor:monitorIndex,request_mode:Clutter.RequestMode.CONTENT_SIZE});
    actor.set_position(m.x,m.y);actor.set_size(m.width,m.height);
    const background=new Meta.Background({meta_display:global.display});
    const [,bytes]=GLib.file_get_contents('/var/lib/fenestra-spotlight/current.json');
    const path=JSON.parse(new TextDecoder().decode(bytes)).image;
    if(!/^\/(var\/lib\/fenestra-spotlight\/images\/[a-f0-9]{64}|usr\/share\/backgrounds\/fenestra\/[A-Za-z0-9._-]+)\.jpg$/.test(path))throw Error('Invalid background path');
    background.set_file(Gio.File.new_for_path(path),GDesktopEnums.BackgroundStyle.ZOOM);
    let loadedPath=path;
    actor._windowsReload=()=>{
        const [,updated]=GLib.file_get_contents('/var/lib/fenestra-spotlight/current.json');
        const current=JSON.parse(new TextDecoder().decode(updated)).image;
        if(current!==loadedPath && /^\/(var\/lib\/fenestra-spotlight\/images\/[a-f0-9]{64}|usr\/share\/backgrounds\/fenestra\/[A-Za-z0-9._-]+)\.jpg$/.test(current)) {
            background.set_file(Gio.File.new_for_path(current),GDesktopEnums.BackgroundStyle.ZOOM);
            loadedPath=current;
        }
    };
    actor.content.background=background;
    container.add_child(actor);
    return actor;
}

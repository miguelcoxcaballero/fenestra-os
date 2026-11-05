import Cairo from 'cairo';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {hexRgb} from './appearance.js';

export function installTaskbarStyle(injections, appearance=null) {
    let stopped=false;
    // Running-app dash: accent fill of the current mode (Windows draws it in the accent).
    const dash=()=>{const p=appearance?.palette;return p?[...hexRgb(p.fill).map(v=>v/255),1]:[100/255,124/255,100/255,1];};
    const repaint=()=>{for(const panel of global.dashToPanel?.panels??[])for(const item of panel.taskbar?._getTaskbarIcons?.()??[])item.child?._delegate?._focusedDots?.queue_repaint();};
    const listener=appearance?.connect(()=>repaint());
    const extension=Main.extensionManager.lookup('dash-to-panel@jderose9.github.com');
    if(!extension)return ()=>{stopped=true;};
    const path=GLib.build_filenamev([extension.path,'appIcons.js']);
    import(Gio.File.new_for_path(path).get_uri()).then(({TaskbarAppIcon})=>{
        if(stopped)return;
        injections.overrideMethod(TaskbarAppIcon.prototype,'_drawRunningIndicator',original=>function(area,type,focused){
            if(type!=='DASHES' || this.dtpPanel.geom.vertical || !this._getRunningIndicatorCount())
                return original.call(this,area,type,focused);
            const [w,h]=area.get_surface_size();
            const thickness=this._getRunningIndicatorSize();
            const scale=thickness/3;
            const length=Math.min(w-4*scale,16*scale);
            const y=h-thickness/2-2*scale;
            const cr=area.get_context();
            cr.setSourceRGBA(...dash());
            cr.setLineWidth(thickness);
            cr.setLineCap(Cairo.LineCap.ROUND);
            cr.moveTo((w-length+thickness)/2,y);
            cr.lineTo((w+length-thickness)/2,y);
            cr.stroke();cr.$dispose();
        });
        for(const panel of global.dashToPanel?.panels??[]) {
            for(const item of panel.taskbar?._getTaskbarIcons?.()??[]) {
                const icon=item.child?._delegate;
                icon?._focusedDots?.queue_repaint();
            }
        }
    }).catch(error=>console.warn(`Windows taskbar styling: ${error.message}`));
    return ()=>{stopped=true;if(listener)appearance.disconnect(listener);};
}

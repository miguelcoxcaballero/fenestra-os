import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import NM from 'gi://NM';
import UPower from 'gi://UPowerGlib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const fenestraAsset=rel=>{for(const base of [GLib.build_filenamev([GLib.get_user_data_dir(),'fenestra','assets']),'/usr/share/fenestra/assets']){const p=GLib.build_filenamev([base,rel]);if(GLib.file_test(p,GLib.FileTest.EXISTS))return p;}return GLib.build_filenamev(['/usr/share/fenestra/assets',rel]);};

// Independent of the hidden top panel, including in the GDM session.
export function installLockStatus(path) {
    const box = new St.BoxLayout({reactive:false, style:'spacing: 18px; color: white;'});
    const wifi = new St.Icon({icon_size:18});
    const battery = new St.Icon({icon_size:22});
    box.add_child(wifi);box.add_child(battery);
    Main.layoutManager.screenShieldGroup.add_child(box);
    const network=NM.Client.new(null);
    const power=UPower.Client.new().get_display_device();
    const connections=[];
    const watch=(object,signal)=>connections.push([object,object.connect(signal,refresh)]);
    function fileIcon(icon,name) {
        const file=Gio.File.new_for_path(fenestraAsset(`status/${name}.svg`));
        if(file.query_exists(null))icon.gicon=new Gio.FileIcon({file});
    }
    function refresh() {
        box.visible=Main.sessionMode.isGreeter || Main.screenShield.locked;
        if(!box.visible)return;
        const monitor=Main.layoutManager.primaryMonitor;
        if(monitor)box.set_position(monitor.x+monitor.width-100,monitor.y+monitor.height-44);
        Main.layoutManager.screenShieldGroup.set_child_above_sibling(box,null);
        const device=network.get_devices().find(d=>d instanceof NM.DeviceWifi);
        const ap=device?.get_active_access_point();
        const level=ap?(ap.strength>=75?'excellent':ap.strength>=50?'good':ap.strength>=25?'ok':'weak'):'offline';
        fileIcon(wifi,ap?`network-wireless-signal-${level}-symbolic`:'network-wireless-offline-symbolic');
        const percentage=Math.max(0,Math.min(10,Math.round((power?.percentage??0)/10)));
        const charging=power?.state===UPower.DeviceState.CHARGING;
        battery.visible=power?.is_present??false;
        fileIcon(battery,`${charging?'charging':'normal'}-0-${percentage}`);
    }
    watch(Main.screenShield,'locked-changed');
    watch(Main.sessionMode,'updated');
    watch(Main.layoutManager,'monitors-changed');
    watch(network,'notify');
    if(power)watch(power,'notify');
    // AP strength notifications belong to replaceable AP objects. A visible-only
    // refresh also follows replacement after roaming, without retaining old APs.
    const timer=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,5,()=>{if(box.visible)refresh();return GLib.SOURCE_CONTINUE;});
    refresh();
    return ()=>{GLib.source_remove(timer);for(const [o,id] of connections)o.disconnect(id);box.destroy();};
}

import Gio from 'gi://Gio';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as MW from '../menuWidgets.js';
import * as Constants from '../constants.js';
import {pick, tintIcon, onSchemeChanged} from '../fenestraTheme.js';
import GLib from 'gi://GLib';
const fenestraAsset=rel=>{for(const base of [GLib.build_filenamev([GLib.get_user_data_dir(),'fenestra','assets']),'/usr/share/fenestra/assets']){const p=GLib.build_filenamev([base,rel]);if(GLib.file_test(p,GLib.FileTest.EXISTS))return p;}return GLib.build_filenamev(['/usr/share/fenestra/assets',rel]);};

function populate(menu,layout,items) {
    menu.removeAll();
    menu.actor.add_style_class_name('windows-start-power');
    menu.box.set_style(`min-width: 124px; padding: 4px; border-radius: 8px; background-color: ${pick('rgba(44,44,44,0.96)', 'rgba(249,249,249,0.96)')}; border: 1px solid ${pick('rgba(255,255,255,0.14)', 'rgba(0,0,0,0.10)')}; font-family: Segoe UI; font-size: 14px;`);
    const section=new PopupMenu.PopupMenuSection();menu.addMenuItem(section);
    for(const [type,title] of items) {
        const item=new MW.PowerMenuItem(layout,type);
        item.label.text=title;
        item.set_style('min-height: 30px; padding: 0px 10px; spacing: 12px; border-radius: 4px; margin: 1px 0px;');
        item.label.set_style('font-family: Segoe UI; font-size: 13px; font-weight: normal;');
        item._iconBin.set_child(new St.Icon({icon_size:16,gicon:new Gio.FileIcon({file:Gio.File.new_for_path(tintIcon(fenestraAsset(`power/${type}.svg`)))})}));
        item.connect('activate',()=>menu.close());section.actor.add_child(item);
    }
}
export function createWindowsPower(layout,avatar) {
    const P=Constants.PowerType;
    const power=new MW.LeaveButton(layout);
    power.leaveMenu._boxPointer.setPosition(power,1.0);
    const powerItems=[[P.LOCK,'Lock'],[P.SUSPEND,'Sleep'],[P.POWER_OFF,'Shut down'],[P.RESTART,'Restart']];
    populate(power.leaveMenu,layout,powerItems);
    const account=new PopupMenu.PopupMenu(avatar._avatarMenuIcon,0.0,St.Side.BOTTOM);
    account.actor.add_style_class_name('popup-menu arcmenu-menu');
    populate(account,layout,[[P.LOGOUT,'Sign out'],[P.SWITCH_USER,'Switch user']]);
    layout.subMenuManager.addMenu(account);Main.uiGroup.add_child(account.actor);account.actor.hide();
    avatar.activate=()=>account.toggle();
    onSchemeChanged(power,()=>{populate(power.leaveMenu,layout,powerItems);populate(account,layout,[[P.LOGOUT,'Sign out'],[P.SWITCH_USER,'Switch user']]);});
    avatar.connect('destroy',()=>account.destroy());
    return power;
}

import {installScreenshotToast} from './screenshotToast.js';
import {installPreviewStyle} from './previewStyle.js';
import {installOverviewBlock} from './overviewBlock.js';
import {installPressAnimation} from './pressAnimation.js';
import {installCalendarPanel} from './calendarPanel.js';
import {installMediaPanel} from './mediaPanel.js';
import {installQuickPanel} from './quickPanel.js';
import {installTrayLayout} from './trayLayout.js';
import {watchExternalPower} from './powerSource.js';
import {BaseIcon} from 'resource:///org/gnome/shell/ui/iconGrid.js';
import {installTaskbarStyle} from './taskbarStyle.js';
import {installAccentStyle} from './accentStyle.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
import UPower from 'gi://UPowerGlib';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {DateMenuButton} from 'resource:///org/gnome/shell/ui/dateMenu.js';
import {Indicator as PowerIndicator} from 'resource:///org/gnome/shell/ui/status/system.js';
const fenestraAsset=rel=>{for(const base of [GLib.build_filenamev([GLib.get_user_data_dir(),'fenestra','assets']),'/usr/share/fenestra/assets']){const p=GLib.build_filenamev([base,rel]);if(GLib.file_test(p,GLib.FileTest.EXISTS))return p;}return GLib.build_filenamev(['/usr/share/fenestra/assets',rel]);};

export default class WindowsTrayTypography extends Extension {
    enable() {
        this._injections=new InjectionManager();this._dates=new Map();this._powers=new Map();
        this._stopTaskbar=installTaskbarStyle(this._injections);
        this._injections.overrideMethod(BaseIcon.prototype,'animateZoomOut',()=>function(){});
        this._injections.overrideMethod(BaseIcon.prototype,'animateZoomOutAtPos',()=>function(){});
        this._upower=UPower.Client.new();
        this._powerSource=watchExternalPower(()=>this._power(Main.panel.statusArea.quickSettings?._system));
        this._acId=this._upower.connect('notify::on-battery',()=>this._power(Main.panel.statusArea.quickSettings?._system));
        const ext=this;
        this._injections.overrideMethod(DateMenuButton.prototype,'_init',original=>function(...args){original.apply(this,args);ext._date(this);});
        this._injections.overrideMethod(PowerIndicator.prototype,'_sync',original=>function(...args){original.apply(this,args);ext._power(this);});
        this._date(Main.panel.statusArea.dateMenu);
        this._stopTrayLayout=installTrayLayout(this._injections);
        this._stopPress=installPressAnimation();
        this._stopOverview=installOverviewBlock(this._injections);
        this._stopPreview=installPreviewStyle();
        this._stopShot=installScreenshotToast(this._injections);
        this._stopQuickPanel=installQuickPanel();
        this._stopCalendar=installCalendarPanel();
        this._stopMedia=installMediaPanel();
        this._stopAccent=installAccentStyle();
        this._power(Main.panel.statusArea.quickSettings?._system);
        this._timer=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,15,()=>{
            this._date(Main.panel.statusArea.dateMenu);
            this._power(Main.panel.statusArea.quickSettings?._system);
            for(const menu of this._dates.keys())this._updateDate(menu);
            return GLib.SOURCE_CONTINUE;
        });
    }
    _date(menu) {
        if(!menu?._clockDisplay || this._dates.has(menu))return;
        const label=menu._clockDisplay;
        const state={style:label.get_style(),align:label.clutter_text.get_line_alignment()};
        state.id=menu._clock.connect('notify::clock',()=>this._updateDate(menu));
        state.destroy=menu.connect('destroy',()=>this._dates.delete(menu));
        this._dates.set(menu,state);
        label.set_style('font-family: "Fenestra Taskbar Text"; font-size: 12px; font-weight: 400; text-align: right; padding: 0; margin: 1px 0 0 0;');
        label.clutter_text.set_line_alignment(Pango.Alignment.RIGHT);
        this._updateDate(menu);
    }
    _updateDate(menu) {
        const now=new Date();
        const time=new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(now);
        const date=new Intl.DateTimeFormat(undefined,{day:'2-digit',month:'2-digit',year:'numeric'}).format(now);
        // Windows renders the 12px clock with slightly tighter advances than Pango.
        menu._clockDisplay.clutter_text.set_markup(`<span letter_spacing="-500">${time}\n${date}</span>`);
    }
    _power(indicator) {
        if(!indicator?._indicator || !indicator._percentageLabel)return;
        const proxy=indicator._systemItem?.powerToggle?._proxy;
        if(!proxy?.IsPresent)return;
        if(!this._powers.has(indicator)) {
            const state={style:indicator._indicator.get_style(),labelStyle:indicator._percentageLabel.get_style()};
            state.destroy=indicator.connect('destroy',()=>this._powers.delete(indicator));
            this._powers.set(indicator,state);
        }
        const onAC=this._powerSource?.online ?? (this._upower ? !this._upower.get_on_battery() : null);
        const complete=proxy.Percentage>=98;
        indicator._percentageLabel.text=`${complete?100:Math.round(proxy.Percentage)}%`;
        indicator._percentageLabel.hide();
        indicator._systemItem.powerToggle.title=indicator._percentageLabel.text;
        const level=Math.max(0,Math.min(10,Math.round(proxy.Percentage/10)));
        const charging=onAC ?? proxy.State===UPower.DeviceState.CHARGING;
        const saver=Main.panel.statusArea.quickSettings?._powerProfiles?.quickSettingsItems?.[0]?._proxy?.ActiveProfile==='power-saver';
        const active=proxy.State===UPower.DeviceState.CHARGING||proxy.State===UPower.DeviceState.FULLY_CHARGED||proxy.Percentage>=98;
        const state=charging?(active?'charging':'plugged'):proxy.Percentage<=10?'low':saver?'saver':'normal';
        indicator._indicator.gicon=new Gio.FileIcon({file:Gio.File.new_for_path(fenestraAsset(`battery/${state}-${charging?1:0}-${level}.svg`))});
        const footer=indicator._systemItem.powerToggle;
        if(footer._icon){footer._icon.gicon=indicator._indicator.gicon;footer._icon.set_style('-st-icon-style: regular; icon-size:20px;');}
        if(footer._title)footer._title.set_style('font-family: "Segoe UI"; font-size:12px; font-weight:400;');
        indicator._indicator.set_style('-st-icon-style: regular; icon-size: 20px; min-width: 20px; min-height: 20px;');
        indicator._percentageLabel.set_style('font-family: "Fenestra Taskbar Text"; font-size: 12px; font-weight: 400; min-width: 36px; text-align: right;');
    }
    disable() {
        this._stopShot?.();this._stopShot=null;
        this._stopPreview?.();this._stopPreview=null;
        this._stopOverview?.();this._stopOverview=null;
        this._stopPress?.();this._stopPress=null;
        this._stopMedia?.();this._stopMedia=null;this._stopAccent?.();this._stopAccent=null;
        this._stopCalendar?.();this._stopCalendar=null;
        this._stopQuickPanel?.();this._stopQuickPanel=null;
        this._stopTrayLayout?.();this._stopTrayLayout=null;
        this._powerSource?.destroy();this._powerSource=null;
        this._stopTaskbar?.();this._stopTaskbar=null;
        if(this._acId)this._upower.disconnect(this._acId);
        this._acId=0;this._upower=null;
        if(this._timer)GLib.source_remove(this._timer);this._timer=0;
        this._injections?.clear();
        for(const [menu,state] of this._dates){
            menu._clock.disconnect(state.id);menu.disconnect(state.destroy);
            menu._clockDisplay.set_style(state.style);menu._clockDisplay.clutter_text.set_line_alignment(state.align);
            menu._clockDisplay.text=menu._clock.clock;
        }
        for(const [indicator,state] of this._powers){
            indicator.disconnect(state.destroy);indicator._indicator.set_style(state.style);
            indicator._percentageLabel.set_style(state.labelStyle);indicator._sync();
        }
        this._dates.clear();this._powers.clear();
    }
}

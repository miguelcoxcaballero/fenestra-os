import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Shell from 'gi://Shell';
import GLib from 'gi://GLib';
import * as Constants from '../constants.js';

const label = (text, style = '') => new St.Label({text, y_align: Clutter.ActorAlign.CENTER, style: 'font-family: Segoe UI; font-weight: normal; ' + style});
const button = (text, action) => {
    // Windows: plain text link with a chevron, subtle hover only.
    const [txt, chev] = text.split(/\s{2}/);
    const b = new St.Button({can_focus: true, style_class: 'popup-menu-item arcmenu-menu-item', style: 'padding: 2px 8px; border-radius: 4px; background-color: transparent; min-height: 0px;'});
    const box = new St.BoxLayout({style: 'spacing: 8px;'});
    box.add_child(new St.Label({text: txt, y_align: Clutter.ActorAlign.CENTER, style: 'font-family: Segoe UI; font-size: 13px; font-weight: normal;'}));
    if (chev) box.add_child(new St.Icon({icon_name: chev === '›' ? 'pan-end-symbolic' : chev === '⌃' ? 'pan-up-symbolic' : 'pan-down-symbolic', icon_size: 12, y_align: Clutter.ActorAlign.CENTER}));
    b.set_child(box);
    b.connect('clicked', action); return b;
};
function heading(title, control, top = 22, bottom = 12) {
    const row = new St.BoxLayout({x_expand:true, style:`margin: ${top}px 68px ${bottom}px 57px;`});
    const l=label(title,'font-weight: 600; font-size: 14px;'); l.x_expand=true;
    row.add_child(l); if(control)row.add_child(control); return row;
}
function watch(layout) {
    if (layout._homeWatch) return;
    const dirty = () => { layout._homeDirty = true; scheduleRebuild(layout); };
    const appSys = Shell.AppSystem.get_default();
    const ids = [[appSys, appSys.connect('installed-changed', dirty)]];
    const file = Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_data_dir(), 'recently-used.xbel']));
    let monitor = null;
    try { monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, null); ids.push([monitor, monitor.connect('changed', dirty)]); } catch (e) {}
    ids.push([layout.arcMenu, layout.arcMenu.connect('open-state-changed', (m, open) => { if (!open) scheduleRebuild(layout); })]);
    layout._homeWatch = {ids, monitor};
    layout.connect('destroy', () => {
        for (const [obj, id] of ids) { try { obj.disconnect(id); } catch (e) {} }
        monitor?.cancel();
        if (layout._homeIdle) GLib.source_remove(layout._homeIdle);
        layout._homeIdle = 0;
    });
}
// Rebuild while the menu is hidden so opening never has to build anything.
function scheduleRebuild(layout) {
    if (layout._homeIdle) return;
    layout._homeIdle = GLib.timeout_add(GLib.PRIORITY_LOW, 400, () => {
        layout._homeIdle = 0;
        if (layout.arcMenu.isOpen) return GLib.SOURCE_REMOVE;
        const stale = Date.now() - (layout._homeBuiltAt ?? 0) > 5 * 60 * 1000;
        if (layout._homeDirty || stale) { layout._homeDirty = true; layout.setDefaultMenuView(); }
        return GLib.SOURCE_REMOVE;
    });
}
export function populateHome(layout) {
    watch(layout);
    const key = `${layout._pinsExpanded ? 1 : 0}|${layout._allView ?? 0}|${layout._pinnedAppsGrid.get_n_children()}`;
    const owned = layout._startOwned ?? [];
    if (!layout._homeDirty && layout._homeKey === key && owned.length && owned.every(a => !a._homeGone)) {
        layout._hideNavigationButtons();
        layout.applicationsBox.insert_child_at_index(owned[0], 0);
        for (const a of owned.slice(1)) layout.applicationsBox.add_child(a);
        return;
    }
    buildHome(layout);
    layout._homeDirty = false;
    layout._homeKey = key;
    layout._homeBuiltAt = Date.now();
    for (const a of layout._startOwned) a.connect('destroy', () => { a._homeGone = true; });
}
function buildHome(layout) {
    layout._startGeneration=(layout._startGeneration??0)+1;
    const generation=layout._startGeneration;
    for(const actor of layout._startOwned??[])actor.destroy();
    layout._startOwned=[];
    const add=actor=>{layout._startOwned.push(actor);layout.applicationsBox.add_child(actor);return actor;};
    layout._hideNavigationButtons();
    layout.applicationsBox.style='padding: 0px 0px 18px; spacing: 0px;';
    layout.applicationsScrollBox.vscrollbar_policy=St.PolicyType.EXTERNAL;
    layout.searchEntry.style='margin: 0px; padding: 0px 14px; spacing: 11px; font-size: 13px; height: 32px; min-height: 0px; border-radius: 16px; background-color: rgba(28,28,28,0.75); border: 1px solid rgba(255,255,255,0.06);';
    layout.searchEntry.x_expand=true;
    if(layout.searchEntry.primary_icon)layout.searchEntry.primary_icon.style='padding-right: 5px;';
    layout.searchEntry.hint_text='Search for apps, settings, and documents';
    const pinHeader=heading('Pinned',button(layout._pinsExpanded?'Show less  ⌃':'Show all  ⌄',()=>{layout._pinsExpanded=!layout._pinsExpanded;layout.setDefaultMenuView();}),28,12);
    layout._startOwned.push(pinHeader);layout.applicationsBox.insert_child_at_index(pinHeader,0);
    layout._pinnedAppsGrid.layout_manager.forceColumns=8;layout._pinnedAppsGrid.setColumns(8);
    layout._pinnedAppsGrid.style='margin: 11px 42px 0px 22px;';
    layout._pinnedAppsGrid.get_children().forEach((item,i)=>{
        item.visible=layout._pinsExpanded||i<16;
        item.style='width: 80px; min-height: 69px; padding: 4px; margin: 0px 4px 8px; border-radius: 4px; font-size: 12px; spacing: 5px;';
        if(item.label){item.label.set_style('font-family: Segoe UI; font-size: 12px; font-weight: normal;');item.label.y_expand=false;item.label.y_align=Clutter.ActorAlign.START;}
        const icon=item._iconBin?.get_child();if(icon instanceof St.Icon)icon.icon_size=32;
    });
    add(heading('Recommended',button('Show all  ›',()=>{layout._hideNavigationButtons();layout.backButton.show();layout._loadRecentFiles();layout.displayRecentFiles();}),28,12));
    const recents=add(new St.Widget({layout_manager:new Clutter.GridLayout(),x_expand:true,style:'margin: 9px 24px 8px 50px;'}));
    const empty=label('The more you use your device, the more your recent files and new apps will show up here.','font-size: 12px; color: #bcbcbc; padding: 12px 0px;');
    recents.layout_manager.attach(empty,0,0,3,1);
    layout._loadRecentFiles();
    const uris=layout.recentFilesManager.getRecentFiles().slice(0,18);
    Promise.all(uris.map(uri=>layout.recentFilesManager.queryInfoAsync(uri).then(r=>({...r,uri})))).then(results=>{
        if(layout._startGeneration!==generation||!recents.get_parent())return;
        const files=results.filter(r=>!r.error).slice(0,6);if(!files.length)return;
        empty.destroy();
        files.forEach(({recentFile,uri},i)=>{
            const mime=layout.recentFilesManager.getMimeType(uri);
            const b=new St.Button({can_focus:true,style_class:'button',style:'width: 224px; min-height: 40px; padding: 4px 8px; margin: 0px 16px 8px 0px; border-radius: 4px; background-color: transparent;'});
            const row=new St.BoxLayout({style:'spacing: 12px;',x_expand:true,x_align:Clutter.ActorAlign.START});
            row.add_child(new St.Icon({gicon:Gio.content_type_get_icon(mime||'application/octet-stream'),icon_size:32}));
            const text=new St.BoxLayout({vertical:true,x_expand:true});
            const name=label(recentFile.get_basename(),'font-size: 12px; font-weight: normal;');name.clutter_text.ellipsize=3;
            const modified=layout.recentFilesManager._bookmarksFile.get_modified(uri);
            const days=Math.max(0,Math.floor((Date.now()/1000-modified)/86400));
            const time=new Date(modified*1000).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
            const age=days===0?`Today at ${time}`:days===1?`Yesterday at ${time}`:`${days} days ago`;
            text.add_child(name);text.add_child(label(age,'font-size: 12px; font-weight: normal; color: #c8c8c8;'));row.add_child(text);b.set_child(row);b.x_align=Clutter.ActorAlign.START;
            b.connect('clicked',()=>{Gio.AppInfo.launch_default_for_uri_async(uri,global.create_app_launch_context(0,-1),null,null);layout.arcMenu.close();});
            recents.layout_manager.attach(b,i%3,Math.floor(i/3),1,1);
        });
    }).catch(logError);
    add(heading('All',button('View: '+(['Category','Grid','List'][layout._allView??0])+'  ⌄',()=>{layout._allView=((layout._allView??0)+1)%3;layout.setDefaultMenuView();}),24,12));
    const groups=[['Productivity',/Office|Finance/],['Social',/Network|Chat|Email/],['Creativity',/Graphics|AudioVideo/],['Utilities & Tools',/Settings|System|Utility/],['Games',/Game/],['Other',/.*/]];
    const buckets=groups.map(([name])=>({name,apps:[]}));
    const apps=Shell.AppSystem.get_default().get_installed().filter(a=>a.should_show()).map(a=>Shell.AppSystem.get_default().lookup_app(a.get_id())).filter(Boolean);
    apps.sort((a,b)=>a.get_name().localeCompare(b.get_name()));
    for(const app of apps){const cats=app.get_app_info().get_categories()??'';const index=groups.findIndex(([,rx])=>rx.test(cats));buckets[index].apps.push(app);}
    if (layout._allView) {
        const grid=add(new St.Widget({layout_manager:new Clutter.GridLayout(),x_expand:true,style:'margin: 0px 24px;'}));
        const cols=layout._allView===1?8:2;
        apps.forEach((app,i)=>{
            const b=new St.Button({can_focus:true,style_class:'popup-menu-item arcmenu-menu-item',style:layout._allView===1?'width: 66px; min-height: 76px; padding: 6px; border-radius: 4px;':'width: 306px; min-height: 32px; padding: 6px; border-radius: 4px;'});
            const row=new St.BoxLayout({vertical:layout._allView===1,style:'spacing: 6px;'});row.add_child(app.create_icon_texture(layout._allView===1?32:24));
            const name=label(app.get_name(),'font-size: 12px;');name.clutter_text.ellipsize=3;row.add_child(name);b.set_child(row);
            b.connect('clicked',()=>{app.activate();layout.arcMenu.close();});grid.layout_manager.attach(b,i%cols,Math.floor(i/cols),1,1);
        });
        return;
    }
    const cards=add(new St.Widget({layout_manager:new Clutter.GridLayout(),x_expand:true,style:'margin: 5px 59px 0px 45px; min-height: 320px;'}));
    buckets.filter(g=>g.apps.length).forEach((group,i)=>{
        const column=new St.BoxLayout({vertical:true,style:'width: 154px; margin: 0px 14px 18px 15px; spacing: 11px;'});
        const b=new St.Button({can_focus:true,style_class:'button',style:'width: 154px; height: 154px; min-height: 154px; padding: 0px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); background-color: rgba(255,255,255,0.04);'});
        const icons=new St.Widget({layout_manager:new Clutter.GridLayout()});
        group.apps.slice(0,4).forEach((app,n)=>{const icon=app.create_icon_texture(32);icon.set_style?.('margin: 26px 18px 18px 18px;');icons.layout_manager.attach(icon,n%2,Math.floor(n/2),1,1);});
        b.set_child(icons);b.connect('clicked',()=>{layout.setGridLayout(Constants.DisplayType.LIST,5);layout.displayCategoryAppList(group.apps,Constants.CategoryType.ALL_PROGRAMS);});
        column.add_child(b);const name=label(group.name,'font-size: 12px; color: #ffffff;');name.clutter_text.ellipsize=3;name.x_align=Clutter.ActorAlign.CENTER;column.add_child(name);
        cards.layout_manager.attach(column,i%4,Math.floor(i/4),1,1);
    });
}

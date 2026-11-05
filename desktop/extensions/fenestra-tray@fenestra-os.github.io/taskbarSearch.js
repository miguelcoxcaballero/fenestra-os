import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';

// Settings › Personalization › Taskbar › Search, like the reference:
//   'hide'       no search entry on the taskbar
//   'icon'       the pinned Search icon (Dash to Panel's own app icon)
//   'icon-label' search glyph + "Search"
//   'box'        a search box with a "Search" placeholder
// For 'icon-label' and 'box' the pinned icon is hidden and a Fenestra button
// takes its place in the same taskbar box (Dash to Panel ignores children that
// are not its own app icons). Clicking opens the Search flyout.

// windows-search.desktop: the id used by installs from before the rename.
const SEARCH_IDS = ['fenestra-search.desktop', 'windows-search.desktop'];
const ES = (GLib.get_language_names()[0] || '').startsWith('es');
const LABEL = ES ? 'Buscar' : 'Search';

function searchItems(panel) {
    return (panel.taskbar?._getTaskbarIcons?.() ?? [])
        .filter(item => SEARCH_IDS.includes(item.child?._delegate?.app?.get_id?.()));
}

function makeButton(mode, gicon, activate) {
    const button = new St.Button({
        style_class: `fenestra-taskbar-search fenestra-taskbar-search-${mode}`,
        reactive: true, can_focus: true, track_hover: true,
        accessible_name: LABEL,
        y_align: Clutter.ActorAlign.CENTER,
    });
    const row = new St.BoxLayout({style_class: 'fenestra-taskbar-search-row', y_align: Clutter.ActorAlign.CENTER,
        x_align: Clutter.ActorAlign.START, x_expand: true});
    row.add_child(new St.Icon({gicon, icon_size: mode === 'box' ? 18 : 20, style_class: 'fenestra-taskbar-search-icon',
        y_align: Clutter.ActorAlign.CENTER}));
    row.add_child(new St.Label({text: LABEL, style_class: 'fenestra-taskbar-search-label', y_align: Clutter.ActorAlign.CENTER}));
    button.set_child(row);
    button.connect('clicked', activate);
    return button;
}

export function installTaskbarSearch(settings) {
    const appSystem = Shell.AppSystem.get_default();
    const buttons = new Map(); // dash-to-panel panel -> {button, mode}
    let pending = 0;

    const searchApp = () => SEARCH_IDS.map(id => appSystem.lookup_app(id)).find(Boolean);
    const activate = () => searchApp()?.activate();
    const gicon = () => searchApp()?.get_icon() ??
        new Gio.ThemedIcon({name: 'system-search-symbolic'});

    const apply = () => {
        pending = 0;
        const mode = settings.get_string('taskbar-search');
        const panels = new Set(global.dashToPanel?.panels ?? []);
        for (const [panel, entry] of buttons) {
            if (!panels.has(panel) || entry.mode !== mode || !entry.button.get_parent()) {
                entry.button.destroy();
                buttons.delete(panel);
            }
        }
        for (const panel of panels) {
            const items = searchItems(panel);
            const custom = mode === 'icon-label' || mode === 'box';
            const vertical = !!panel.geom?.vertical;
            for (const item of items)
                item.visible = mode === 'icon' || (custom && vertical);
            if (!custom || vertical || !items.length)
                continue;
            const item = items[0];
            const parent = item.get_parent();
            let entry = buttons.get(panel);
            if (!entry) {
                entry = {button: makeButton(mode, gicon(), activate), mode};
                buttons.set(panel, entry);
            }
            if (entry.button.get_parent() !== parent) {
                entry.button.get_parent()?.remove_child(entry.button);
                parent.insert_child_below(entry.button, item);
            } else if (entry.button.get_next_sibling() !== item) {
                parent.set_child_below_sibling(entry.button, item);
            }
        }
        return GLib.SOURCE_REMOVE;
    };
    const queue = () => {
        if (!pending)
            pending = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, apply);
    };

    const settingsId = settings.connect('changed::taskbar-search', queue);
    // Dash to Panel rebuilds its app icons (favourites, running apps, settings
    // changes); re-apply when its taskbar boxes change.
    const watched = new Map();
    const watch = () => {
        for (const panel of global.dashToPanel?.panels ?? []) {
            const box = searchItems(panel)[0]?.get_parent() ?? panel.taskbar?._box;
            if (box && !watched.has(box)) {
                const ids = [box.connect('child-added', queue), box.connect('child-removed', queue)];
                box.connectObject?.('destroy', () => watched.delete(box), box);
                watched.set(box, ids);
            }
        }
        apply();
        return GLib.SOURCE_CONTINUE;
    };
    const timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 10, watch);
    GLib.idle_add(GLib.PRIORITY_DEFAULT, () => (watch(), GLib.SOURCE_REMOVE));

    return () => {
        if (pending)
            GLib.source_remove(pending);
        GLib.source_remove(timer);
        settings.disconnect(settingsId);
        for (const [box, ids] of watched)
            for (const id of ids)
                box.disconnect(id);
        watched.clear();
        for (const {button} of buttons.values())
            button.destroy();
        buttons.clear();
        for (const panel of global.dashToPanel?.panels ?? [])
            for (const item of searchItems(panel))
                item.visible = true;
    };
}

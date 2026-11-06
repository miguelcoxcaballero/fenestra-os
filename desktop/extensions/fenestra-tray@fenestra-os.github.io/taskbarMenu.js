import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

// Right-click on an empty part of the taskbar, like the reference: a small
// menu with "Task Manager" and "Taskbar settings". Dash to Panel shows the
// (hidden) Show Apps button's context menu there; that call is replaced per
// panel, so nothing else about Dash to Panel changes.

const ES = (GLib.get_language_names()[0] || '').startsWith('es');
const T = {
    'Task Manager': ES ? 'Administrador de tareas' : 'Task Manager',
    'Taskbar settings': ES ? 'Configuración de la barra de tareas' : 'Taskbar settings',
};

function spawn(argv) {
    try {
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    } catch (e) {
        console.warn(`Fenestra taskbar menu: ${e.message}`);
    }
}

function icon(names) {
    return new Gio.ThemedIcon({names});
}

export function installTaskbarMenu() {
    const manager = new PopupMenu.PopupMenuManager(Main.layoutManager.dummyCursor);
    const menu = new PopupMenu.PopupMenu(Main.layoutManager.dummyCursor, 0.5, St.Side.BOTTOM);
    menu.actor.add_style_class_name('fenestra-taskbar-menu');
    menu.actor.hide();
    Main.uiGroup.add_child(menu.actor);
    manager.addMenu(menu);
    const item = (label, gicon, argv) => {
        const it = new PopupMenu.PopupImageMenuItem(label, gicon);
        it.connect('activate', () => spawn(argv));
        menu.addMenuItem(it);
    };
    item(T['Task Manager'], icon(['org.fenestra.TaskManager', 'fenestra-taskmgr', 'utilities-system-monitor-symbolic']),
        ['fenestra-taskmgr']);
    item(T['Taskbar settings'], icon(['fenestra-settings', 'preferences-system-symbolic']),
        ['fenestra-settings', '--page', 'taskbar']);

    const patched = new Map(); // showAppsIconWrapper -> original popupMenu
    const patch = () => {
        for (const panel of global.dashToPanel?.panels ?? []) {
            const w = panel.showAppsIconWrapper;
            if (!w || patched.has(w))
                continue;
            patched.set(w, w.popupMenu);
            w.popupMenu = function (sourceActor) {
                // Only Dash to Panel's "empty taskbar" path uses the dummy cursor.
                if (sourceActor === Main.layoutManager.dummyCursor) {
                    menu.toggle();
                    return true;
                }
                return patched.get(w).call(this, sourceActor);
            };
        }
        return GLib.SOURCE_CONTINUE;
    };
    patch();
    // Panels are rebuilt when Dash to Panel's settings change.
    const timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, patch);

    return () => {
        GLib.source_remove(timer);
        for (const [w, original] of patched)
            w.popupMenu = original;
        patched.clear();
        menu.destroy();
    };
}

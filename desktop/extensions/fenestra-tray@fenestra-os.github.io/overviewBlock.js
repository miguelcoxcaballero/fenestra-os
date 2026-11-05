import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Windows has no GNOME Activities overview or app grid: block every entry point
// (touchpad swipes, keybindings, hot corner, other extensions calling show()).
export function installOverviewBlock(injections) {
    const overview = Main.overview;
    for (const name of ['show', 'showApps', 'toggle'])
        injections.overrideMethod(overview, name, () => function () {});
    const trackers = [overview._swipeTracker, Main.wm?._workspaceAnimation?._swipeTracker].filter(Boolean);
    const ids = trackers.map(t => {
        t.enabled = false;
        return [t, t.connect('notify::enabled', () => { if (t.enabled) t.enabled = false; })];
    });
    if (overview.visible) overview.hide();
    return () => {
        for (const [t, id] of ids) { t.disconnect(id); t.enabled = true; }
    };
}

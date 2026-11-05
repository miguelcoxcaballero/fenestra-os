import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

// Exact accent colour chosen in Fenestra Settings: it writes
// ~/.config/fenestra/accent-shell.css; load it over the default blue and
// reload it whenever it changes.
export function installAccentStyle() {
    const dir = Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_config_dir(), 'fenestra']));
    const file = dir.get_child('accent-shell.css');
    const theme = () => St.ThemeContext.get_for_stage(global.stage).get_theme();
    let loaded = null, pending = 0;
    const load = () => {
        const t = theme();
        if (loaded) { t.unload_stylesheet(loaded); loaded = null; }
        if (!file.query_exists(null)) return;
        // A fresh GFile per load: St caches stylesheets by file.
        const fresh = Gio.File.new_for_path(file.get_path());
        try { t.load_stylesheet(fresh); loaded = fresh; } catch (e) { console.warn(`Fenestra accent: ${e.message}`); }
    };
    let monitor = null;
    try {
        GLib.mkdir_with_parents(dir.get_path(), 0o755);
        monitor = dir.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, null);
        monitor.connect('changed', (_m, f, other) => {
            if (f?.get_basename() !== 'accent-shell.css' && other?.get_basename() !== 'accent-shell.css') return;
            if (pending) GLib.source_remove(pending);
            pending = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => { pending = 0; load(); return GLib.SOURCE_REMOVE; });
        });
    } catch (e) { console.warn(`Fenestra accent: ${e.message}`); }
    load();
    return () => {
        if (pending) GLib.source_remove(pending);
        monitor?.cancel();
        if (loaded) theme().unload_stylesheet(loaded);
    };
}

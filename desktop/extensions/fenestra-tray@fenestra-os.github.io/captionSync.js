import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

// Keep ~/.config/gtk-{3,4}.0/fenestra-caption-buttons.css equal to the system
// copy in /usr/share/fenestra (Windows 11 caption buttons). The user's gtk.css
// imports the per-user copy because Flatpak apps can read ~/.config/gtk-*
// (system override in the kickstart) but not /usr/share/fenestra; refreshing it
// at login means system updates reach every app.
export function syncCaptionButtons() {
    for (const ver of ['gtk-3.0', 'gtk-4.0']) {
        try {
            const src = Gio.File.new_for_path(`/usr/share/fenestra/${ver}/caption-buttons.css`);
            if (!src.query_exists(null))
                continue;
            const dir = Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_config_dir(), ver]));
            const dst = dir.get_child('fenestra-caption-buttons.css');
            const [, want] = src.load_contents(null);
            let have = null;
            try {
                [, have] = dst.load_contents(null);
            } catch {}
            if (have && GLib.Bytes.new(have).equal(GLib.Bytes.new(want)))
                continue;
            GLib.mkdir_with_parents(dir.get_path(), 0o755);
            dst.replace_contents(want, null, false, Gio.FileCreateFlags.REPLACE_DESTINATION, null);
        } catch (e) {
            console.warn(`Fenestra caption buttons (${ver}): ${e.message}`);
        }
    }
}

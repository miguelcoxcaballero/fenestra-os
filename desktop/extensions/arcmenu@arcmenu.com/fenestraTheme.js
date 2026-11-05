import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

/*
 * Windows 11 light/dark for Fenestra's Start/Search layouts.
 * Light = org.gnome.desktop.interface color-scheme != 'prefer-dark'.
 * (fenestra-tray's appearance.js sets the ArcMenu colour keys and the
 * '#uiGroup.fenestra-light' class used by windows-search.css.)
 */
let iface = null;
const settings = () => (iface ??= new Gio.Settings({schema_id: 'org.gnome.desktop.interface'}));

export const isLight = () => settings().get_string('color-scheme') !== 'prefer-dark';

// Pick the dark or light variant of a colour/style.
export const pick = (dark, light) => isLight() ? light : dark;

// Call fn whenever the mode changes, for as long as actor lives.
export function onSchemeChanged(actor, fn) {
    const id = settings().connect('changed::color-scheme', () => fn(isLight()));
    actor.connect('destroy', () => settings().disconnect(id));
    return id;
}

// Our white glyph SVGs (power menu) recoloured for light mode.
export function tintIcon(path) {
    if (!isLight()) return path;
    try {
        const [ok, bytes] = GLib.file_get_contents(path);
        if (!ok) return path;
        const src = new TextDecoder().decode(bytes);
        const out = src.replace(/#ffffff|#eeeeee/gi, '#1a1a1a');
        if (out === src) return path;
        const dest = GLib.build_filenamev([GLib.get_user_cache_dir(), 'fenestra', 'tint', 'arcmenu-light',
            `${GLib.compute_checksum_for_string(GLib.ChecksumType.MD5, path, -1).slice(0, 12)}-${GLib.path_get_basename(path)}`]);
        if (!GLib.file_test(dest, GLib.FileTest.EXISTS)) {
            GLib.mkdir_with_parents(GLib.path_get_dirname(dest), 0o755);
            GLib.file_set_contents(dest, out);
        }
        return dest;
    } catch (e) {
        return path;
    }
}

// Windows acrylic luminosity mapping (windowsAcrylic.js): [base, gain, chroma].
export const acrylicMap = () => isLight() ? [0.84, 0.13, 0.45] : [0.128, 0.265, 0.65];

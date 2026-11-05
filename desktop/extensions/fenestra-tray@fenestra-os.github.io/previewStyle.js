import GLib from 'gi://GLib';
import Shell from 'gi://Shell';

// Windows 11 taskbar thumbnails: acrylic (blurred) card, small gap above the taskbar.
const GAP = 3, BLUR = 30;
export function installPreviewStyle() {
    const done = new Set();
    const apply = () => {
        for (const panel of global.dashToPanel?.panels ?? []) {
            const menu = panel.taskbar?.previewMenu?.menu;
            if (!menu || done.has(menu)) continue;
            done.add(menu);
            menu.add_effect_with_name('windows-acrylic',
                new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, radius: BLUR, brightness: 1.0}));
            menu.margin_bottom = GAP;
            menu.connect('destroy', () => done.delete(menu));
        }
        return GLib.SOURCE_CONTINUE;
    };
    apply();
    // Dash to Panel builds (and rebuilds) its panels asynchronously.
    const timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, apply);
    return () => {
        GLib.source_remove(timer);
        for (const menu of done) { menu.remove_effect_by_name('windows-acrylic'); menu.margin_bottom = 0; }
        done.clear();
    };
}

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
    // Dash to Panel builds (and rebuilds) its panels asynchronously and emits
    // 'panels-created'; hook that signal (re-hooking if Dash to Panel itself is
    // re-enabled) instead of polling every 2 s.
    let emitter = null, emitterId = 0;
    const hook = () => {
        const dtp = global.dashToPanel ?? null;
        if (dtp !== emitter) {
            try { if (emitter && emitterId) emitter.disconnect(emitterId); } catch {}
            emitter = dtp;
            emitterId = dtp?.connect?.('panels-created', () => GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => { apply(); return GLib.SOURCE_REMOVE; })) ?? 0;
        }
        apply();
        return GLib.SOURCE_CONTINUE;
    };
    hook();
    const timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 30, hook);
    return () => {
        GLib.source_remove(timer);
        try { if (emitter && emitterId) emitter.disconnect(emitterId); } catch {}
        for (const menu of done) { menu.remove_effect_by_name('windows-acrylic'); menu.margin_bottom = 0; }
        done.clear();
    };
}

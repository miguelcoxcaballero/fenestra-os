// Windows 11 privacy glyphs in the tray: while an app uses the microphone, camera or
// location, Windows shows a small foreground-coloured glyph (white in dark mode, dark in
// light mode) next to Wi-Fi/volume, with a tooltip such as "Firefox is using your
// microphone".  GNOME shows the same indicators as orange symbolic icons; we keep GNOME's
// logic (visibility, menus) and only restyle them.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const ES = (GLib.get_language_names()[0] || '').startsWith('es');
const T = ES ? {
    mic1: '%s está usando el micrófono', micN: '%d aplicaciones están usando el micrófono',
    micAny: 'Una aplicación está usando el micrófono',
    camera: 'Una aplicación está usando la cámara', location: 'Una aplicación está usando tu ubicación',
} : {
    mic1: '%s is using your microphone', micN: '%d apps are using your microphone',
    micAny: 'An app is using your microphone',
    camera: 'An app is using your camera', location: 'An app is using your location',
};
// Streams GNOME itself ignores when deciding whether the microphone is "in use".
const IGNORED_APPS = new Set(['org.gnome.VolumeControl', 'org.PulseAudio.pavucontrol', 'org.gnome.Settings']);

export function installPrivacyIcons(asset, appearance) {
    let closed = false;
    const done = new Map();            // indicator icon -> {kind, ids, oldStyle}
    let tip = null;

    const glyph = kind => {
        const path = asset(`privacy/${kind}.svg`);
        return new Gio.FileIcon({file: Gio.File.new_for_path(appearance?.tint(path) ?? path)});
    };

    const micText = q => {
        try {
            const control = q._volumeInput?._control;
            const names = [];
            for (const out of control?.get_source_outputs?.() ?? []) {
                const id = out.get_application_id?.();
                if (id && IGNORED_APPS.has(id)) continue;
                const n = out.get_name?.() || out.get_description?.();
                if (n && !names.includes(n)) names.push(n);
            }
            if (names.length === 1) return T.mic1.replace('%s', names[0]);
            if (names.length > 1) return T.micN.replace('%d', String(names.length));
        } catch (e) {
            logError(e, 'Fenestra privacy tooltip');
        }
        return T.micAny;
    };

    const showTip = (icon, text) => {
        hideTip();
        tip = new St.Label({text, style_class: 'dash-label fenestra-privacy-tip'});
        Main.layoutManager.addTopChrome(tip);
        const [x, y] = icon.get_transformed_position();
        const [w] = icon.get_transformed_size();
        const [, tw] = tip.get_preferred_width(-1);
        const [, th] = tip.get_preferred_height(-1);
        const mon = Main.layoutManager.findMonitorForActor(icon) ?? Main.layoutManager.primaryMonitor;
        let tx = Math.round(x + w / 2 - tw / 2);
        tx = Math.max(mon.x + 4, Math.min(tx, mon.x + mon.width - tw - 4));
        // bottom taskbar: tooltip above the icon; top panel: below it
        const ty = y > mon.y + mon.height / 2 ? Math.round(y - th - 10) : Math.round(y + 32);
        tip.set_position(tx, ty);
    };
    const hideTip = () => {
        tip?.destroy();
        tip = null;
    };

    const apply = (icon, kind, q) => {
        if (!icon) return;
        let st = done.get(icon);
        if (!st) {
            st = {kind, oldStyle: icon.get_style(), ids: [], hadClass: icon.has_style_class_name('privacy-indicator'),
                oldReactive: icon.reactive, oldHover: icon.track_hover};
            done.set(icon, st);
            // GNOME keeps updating icon_name (e.g. microphone volume level): put ours back.
            st.ids.push(icon.connect('notify::gicon', () => {
                if (!closed && !st.applying) GLib.idle_add(GLib.PRIORITY_DEFAULT, () => { if (!closed) apply(icon, kind, q); return GLib.SOURCE_REMOVE; });
            }));
            icon.reactive = true;
            icon.track_hover = true;
            st.ids.push(icon.connect('enter-event', () => {
                if (!closed) {
                    const text = kind === 'mic' ? micText(q) : kind === 'camera' ? T.camera : T.location;
                    showTip(icon, text);
                }
                return Clutter.EVENT_PROPAGATE;
            }));
            st.ids.push(icon.connect('leave-event', () => {
                hideTip();
                return Clutter.EVENT_PROPAGATE;
            }));
            st.ids.push(icon.connect('notify::visible', () => { if (!icon.visible) hideTip(); }));
            st.ids.push(icon.connect('destroy', () => done.delete(icon)));
        }
        st.applying = true;
        icon.remove_style_class_name('privacy-indicator');
        icon.gicon = glyph(kind);
        icon.set_style('icon-size: 16px; min-width: 16px; min-height: 16px; -st-icon-style: regular;');
        st.applying = false;
    };

    const sync = () => {
        if (closed) return;
        const q = Main.panel.statusArea.quickSettings;
        if (!q) return;
        apply(q._volumeInput?._indicator, 'mic', q);
        apply(q._camera?._indicator, 'camera', q);
        apply(q._location?._indicator, 'location', q);
    };

    // Quick Settings creates its indicators asynchronously after login.
    let tries = 0;
    const timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
        sync();
        return ++tries < 15 && !closed ? GLib.SOURCE_CONTINUE : GLib.SOURCE_REMOVE;
    });
    const themeId = appearance?.connect?.(() => { for (const [icon, st] of done) apply(icon, st.kind, Main.panel.statusArea.quickSettings); });
    sync();

    return () => {
        closed = true;
        GLib.source_remove(timer);
        hideTip();
        if (themeId && appearance?.disconnect) appearance.disconnect(themeId);
        const q = Main.panel.statusArea.quickSettings;
        for (const [icon, st] of done) {
            for (const id of st.ids) {
                try { icon.disconnect(id); } catch {}
            }
            try {
                icon.set_style(st.oldStyle);
                if (st.hadClass) icon.add_style_class_name('privacy-indicator');
                icon.reactive = st.oldReactive;
                icon.track_hover = st.oldHover;
                if (st.kind === 'mic') icon.icon_name = q?._volumeInput?._input?.getIcon?.() ?? 'audio-input-microphone-symbolic';
                else if (st.kind === 'camera') icon.icon_name = 'camera-web-symbolic';
                else icon.icon_name = 'location-services-active-symbolic';
            } catch {}
        }
        done.clear();
    };
}

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {OsdWindowManager} from 'resource:///org/gnome/shell/ui/osdWindow.js';

// Windows 11 volume/brightness flyout: a 192x48 acrylic pill centred 24px above
// the taskbar with glyph, accent slider and the 0-100 value. Level OSDs
// (volume, brightness, keyboard backlight, microphone) use it; anything else
// (caps lock, display switch, ...) keeps GNOME's OsdWindow, restyled in CSS.
const HIDE_TIMEOUT = 1500, FADE_TIME = 150, SLIDE = 8, GAP = 24;
// Light accent variants Windows uses for controls on dark surfaces.
const ACCENTS = {blue: '#4cc2ff', teal: '#4fd6cb', green: '#6ccb5f', yellow: '#ffd75e', orange: '#ff9a5c',
    red: '#ff99a4', pink: '#f7a2cf', purple: '#d6a4f2', slate: '#a8bccf'};
const LANG = (GLib.getenv('LANGUAGE') || GLib.getenv('LC_MESSAGES') || GLib.getenv('LANG') || 'en').split(':')[0].slice(0, 2);
const _t = (en, es) => LANG === 'es' ? es : en;

function rgba(hex, a = 1) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255, a];
}

function iconName(gicon) {
    const names = gicon?.get_names?.() ?? [gicon?.to_string?.() ?? ''];
    return names.join(' ');
}

// Map GNOME's OSD icon to a Windows glyph; null = not a level flyout.
function glyphFor(name, level) {
    if (/audio-volume|audio-speakers|audio-headphones|audio-output/.test(name)) {
        if (/muted/.test(name)) return 'osd/speaker-mute.svg';
        const v = Math.round((level ?? 0) * 100);
        return `osd/speaker-${v <= 0 ? 0 : v < 34 ? 1 : v < 67 ? 2 : 3}.svg`;
    }
    if (/display-brightness/.test(name)) return 'osd/brightness.svg';
    if (/keyboard-brightness/.test(name)) return 'osd/keyboard.svg';
    if (/microphone|audio-input/.test(name)) return /muted/.test(name) ? 'osd/mic-off.svg' : 'osd/mic.svg';
    return null;
}

class Flyout {
    constructor(monitorIndex, asset) {
        this._monitorIndex = monitorIndex;
        this._asset = asset;
        this._gicons = new Map();
        this._value = 0;
        this._fraction = 0;
        this._hideId = 0;
        this.actor = new St.BoxLayout({style_class: 'fenestra-osd', visible: false, reactive: false,
            can_focus: false, y_align: Clutter.ActorAlign.CENTER});
        this._icon = new St.Icon({style_class: 'fenestra-osd-icon', icon_size: 16, y_align: Clutter.ActorAlign.CENTER});
        this._slider = new St.DrawingArea({style_class: 'fenestra-osd-slider', x_expand: true, y_expand: true});
        this._slider.connect('repaint', area => this._paint(area));
        this._label = new St.Label({style_class: 'fenestra-osd-value', y_align: Clutter.ActorAlign.CENTER});
        this.actor.add_child(this._icon);
        this.actor.add_child(this._slider);
        this.actor.add_child(this._label);
        Main.layoutManager.uiGroup.add_child(this.actor);
    }

    _gicon(rel) {
        const path = this.appearance?.tint(this._asset(rel)) ?? this._asset(rel);
        if (!this._gicons.has(path))
            this._gicons.set(path, new Gio.FileIcon({file: Gio.File.new_for_path(path)}));
        return this._gicons.get(path);
    }

    _paint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        const r = 9, x0 = r, x1 = w - r, cy = h / 2, tx = x0 + (x1 - x0) * this._fraction;
        const accent = rgba(this.accent);
        const light = this.appearance && !this.appearance.palette.dark;
        cr.setLineCap(1); // ROUND
        cr.setLineWidth(4);
        if (light) cr.setSourceRGBA(0, 0, 0, 0.45);
        else cr.setSourceRGBA(1, 1, 1, 0.54);
        cr.moveTo(x0, cy); cr.lineTo(x1, cy); cr.stroke();
        if (this._fraction > 0) {
            cr.setSourceRGBA(...accent);
            cr.moveTo(x0, cy); cr.lineTo(tx, cy); cr.stroke();
        }
        // Thumb: dark (light mode: white) disc with a hairline ring and an accent centre.
        cr.arc(tx, cy, r, 0, 2 * Math.PI);
        if (light) cr.setSourceRGBA(1, 1, 1, 1);
        else cr.setSourceRGBA(0.27, 0.27, 0.27, 1);
        cr.fillPreserve();
        cr.setLineWidth(1);
        if (light) cr.setSourceRGBA(0, 0, 0, 0.08);
        else cr.setSourceRGBA(1, 1, 1, 0.09);
        cr.stroke();
        cr.arc(tx, cy, 5, 0, 2 * Math.PI);
        cr.setSourceRGBA(...accent);
        cr.fill();
        cr.$dispose();
    }

    _place() {
        const monitor = Main.layoutManager.monitors[this._monitorIndex];
        if (!monitor) return;
        const work = Main.layoutManager.getWorkAreaForMonitor(this._monitorIndex);
        const [, natW] = this.actor.get_preferred_width(-1);
        const [, natH] = this.actor.get_preferred_height(natW);
        const bottom = (work && work.height > 0 ? work.y + work.height : monitor.y + monitor.height - 48) - GAP;
        this.actor.set_position(Math.round(monitor.x + (monitor.width - natW) / 2), Math.round(bottom - natH));
    }

    show(glyph, level, maxLevel, label) {
        this._icon.gicon = this._gicon(glyph);
        const levelMode = level !== null && level !== undefined;
        this._slider.visible = levelMode;
        this.actor.remove_style_class_name(levelMode ? 'fenestra-osd-text' : 'fenestra-osd-level');
        this.actor.add_style_class_name(levelMode ? 'fenestra-osd-level' : 'fenestra-osd-text');
        if (levelMode) {
            const max = maxLevel > 0 ? maxLevel : 1;
            this._fraction = Math.max(0, Math.min(1, level / max));
            this._label.text = `${Math.round(Math.max(0, level) * 100)}`;
            this._slider.queue_repaint();
        } else {
            this._label.text = label ?? '';
        }
        this._place();
        if (!this.actor.visible || this._hiding) {
            this._hiding = false;
            this.actor.remove_all_transitions();
            if (!this.actor.visible) {
                global.compositor.disable_unredirect();
                this.actor.opacity = 0;
                this.actor.translation_y = SLIDE;
                this.actor.show();
            }
            Main.layoutManager.uiGroup.set_child_above_sibling(this.actor, null);
            this.actor.ease({opacity: 255, translation_y: 0, duration: FADE_TIME,
                mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
        }
        if (this._hideId) GLib.source_remove(this._hideId);
        this._hideId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, HIDE_TIMEOUT, () => {
            this._hideId = 0;
            this.hide();
            return GLib.SOURCE_REMOVE;
        });
    }

    hide(now = false) {
        if (this._hideId) GLib.source_remove(this._hideId);
        this._hideId = 0;
        if (!this.actor.visible) return;
        const done = () => {
            this._hiding = false;
            this.actor.hide();
            global.compositor.enable_unredirect();
        };
        if (now) { this.actor.remove_all_transitions(); done(); return; }
        this._hiding = true;
        this.actor.ease({opacity: 0, translation_y: SLIDE / 2, duration: FADE_TIME,
            mode: Clutter.AnimationMode.EASE_IN_QUAD, onComplete: () => { if (this._hiding) done(); }});
    }

    destroy() {
        this.hide(true);
        this.actor.destroy();
    }
}

export function installOsdStyle(injections, asset, appearance = null) {
    const iface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
    const flyouts = [];
    // Windows: the slider fill is the accent tint of the current mode (appearance.js).
    const accent = () => appearance?.palette?.text ?? ACCENTS[iface.get_string('accent-color')] ?? ACCENTS.blue;
    let color = accent();
    const refresh = () => {
        color = accent();
        for (const f of flyouts) if (f) { f.accent = color; f._slider.queue_repaint(); }
    };
    const accentId = iface.connect('changed::accent-color', refresh);
    const listener = appearance?.connect(refresh);
    const flyout = i => {
        if (!flyouts[i]) { flyouts[i] = new Flyout(i, asset); flyouts[i].accent = color; flyouts[i].appearance = appearance; }
        return flyouts[i];
    };
    const sync = () => {
        for (let i = Main.layoutManager.monitors.length; i < flyouts.length; i++) flyouts[i]?.destroy();
        flyouts.length = Math.min(flyouts.length, Main.layoutManager.monitors.length);
    };
    const monitorsId = Main.layoutManager.connect('monitors-changed', sync);

    injections.overrideMethod(OsdWindowManager.prototype, '_showOsdWindow', original => function (monitorIndex, icon, label, level, maxLevel) {
        const name = iconName(icon);
        const hasLevel = level !== null && level !== undefined;
        const glyph = glyphFor(name, level);
        // Microphone mute toggles come without a level: Windows shows glyph + text.
        if (glyph && (hasLevel || /microphone|audio-input/.test(name))) {
            this._osdWindows[monitorIndex]?.cancel();
            const text = label ?? (/muted/.test(name) ? _t('Microphone muted', 'Micrófono silenciado') : _t('Microphone on', 'Micrófono activado'));
            flyout(monitorIndex).show(glyph, hasLevel ? level : null, maxLevel, text);
            return;
        }
        flyouts[monitorIndex]?.hide(true);
        original.call(this, monitorIndex, icon, label, level, maxLevel);
    });
    injections.overrideMethod(OsdWindowManager.prototype, 'show', original => function (icon, label, levels) {
        for (let i = 0; i < flyouts.length; i++) if (!levels[i]) flyouts[i]?.hide();
        original.call(this, icon, label, levels);
    });
    injections.overrideMethod(OsdWindowManager.prototype, 'hideAll', original => function () {
        for (const f of flyouts) f?.hide(true);
        original.call(this);
    });

    return () => {
        Main.layoutManager.disconnect(monitorsId);
        iface.disconnect(accentId);
        if (listener) appearance.disconnect(listener);
        for (const f of flyouts) f?.destroy();
        flyouts.length = 0;
    };
}

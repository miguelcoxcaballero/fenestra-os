import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GdkPixbuf from 'gi://GdkPixbuf';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

/*
 * Windows 11 "Choose your mode" + "Accent color" for the whole desktop.
 *
 * Inputs:  org.gnome.desktop.interface color-scheme / accent-color
 *          org.fenestra.desktop accent-color-custom / accent-from-wallpaper
 * Outputs (all live):
 *  - Main.uiGroup gets 'fenestra-themed' and, in light mode, 'fenestra-light';
 *    light.css restyles every Fenestra shell surface under '#uiGroup.fenestra-light'.
 *  - a generated accent stylesheet (all accent fills/rings/sliders, Windows
 *    contrast-aware text on fills) is (re)loaded into the St theme.
 *  - GTK 3/4: gtk-theme switches between <family>-Light/-Dark through a tiny
 *    user wrapper theme that imports the base theme and defines the accent;
 *    the wrapper name alternates A/B so running apps reload it.
 *    ~/.config/gtk-4.0/fenestra-accent.css carries the accent for libadwaita.
 *  - Dash to Panel (taskbar tint, hover, running dots) and ArcMenu colours.
 *  - tint(): recoloured copies of our white SVG glyphs (battery, OSD, power).
 */

const IFACE = 'org.gnome.desktop.interface';
const FENESTRA = 'org.fenestra.desktop';
// GNOME accent enum -> Windows accent: [base, fill on dark (Light2), fill on light (Dark1)].
const ENUM = {
    blue: ['#0078d4', '#4cc2ff', '#005fb8'], teal: ['#038387', '#4fd6cb', '#00777b'],
    green: ['#107c10', '#6ccb5f', '#0f7b0f'], yellow: ['#ffb900', '#ffd75e', '#9d5d00'],
    orange: ['#ca5010', '#ff9a5c', '#bc4b09'], red: ['#e81123', '#ff99a4', '#c42b1c'],
    pink: ['#e3008c', '#f7a2cf', '#bf0077'], purple: ['#744da9', '#d6a4f2', '#8764b8'],
    slate: ['#68768a', '#a8bccf', '#515c6b'],
};

// ---- colour maths ---------------------------------------------------------
export const hexRgb = h => {
    h = h.replace('#', '');
    if (h.length === 3) h = [...h].map(c => c + c).join('');
    const n = parseInt(h.slice(0, 6), 16);
    return [n >> 16 & 255, n >> 8 & 255, n & 255];
};
const rgbHex = c => `#${c.map(v => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('')}`;
export const rgba = (hex, a) => `rgba(${hexRgb(hex).join(',')},${a})`;
const mix = (a, b, t) => { const x = hexRgb(a), y = hexRgb(b); return rgbHex(x.map((v, i) => v + (y[i] - v) * t)); };
const lum = hex => {
    const c = hexRgb(hex).map(v => v / 255).map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
function toHsl(hex) {
    const [r, g, b] = hexRgb(hex).map(v => v / 255);
    const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
    if (max === min) return [0, 0, l];
    const d = max - min, s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [h / 6, s, l];
}
function fromHsl(h, s, l) {
    const f = (p, q, t) => {
        t = (t + 1) % 1;
        if (t < 1 / 6) return p + (q - p) * 6 * t;
        if (t < 1 / 2) return q;
        if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
        return p;
    };
    if (!s) return rgbHex([l * 255, l * 255, l * 255]);
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    return rgbHex([f(p, q, h + 1 / 3), f(p, q, h), f(p, q, h - 1 / 3)].map(v => v * 255));
}
// Same derivation as tools/build-gtk-themes.py light_fill().
function darker(hex) {
    const [h, s, l0] = toHsl(hex);
    let l = l0 - 0.08, out = fromHsl(h, s, l);
    while (l > 0.05 && contrast(out, '#ffffff') < 4.5) { l -= 0.01; out = fromHsl(h, s, l); }
    return out;
}
function lighter(hex, target = 0.72) {
    const [h, s, l] = toHsl(hex);
    return l >= target ? hex : fromHsl(h, Math.min(1, s * 1.5), target);
}
// Text/glyph colour on an accent fill (Windows: black on light accents).
const onFill = fill => lum(fill) > 0.25 ? '#000000' : '#ffffff';

export function palette(accent, dark) {
    let base, darkFill, lightFill;
    if (ENUM[accent]) [base, darkFill, lightFill] = ENUM[accent];
    else {
        base = darkFill = accent;
        while (contrast(darkFill, '#202020') < 3) darkFill = mix(darkFill, '#ffffff', 0.1);
        lightFill = darker(base);
    }
    const fill = dark ? darkFill : lightFill;
    const p = {
        dark, base, fill, darkFill, lightFill,
        on: onFill(fill),
        // accent used as text / thin marks on the current surface
        text: dark ? lighter(darkFill) : lightFill,
        hover: dark ? mix(fill, '#ffffff', 0.15) : mix(fill, '#ffffff', 0.1),
        press: dark ? mix(fill, '#000000', 0.14) : mix(fill, '#ffffff', 0.2),
    };
    p.textOn = onFill(p.text);
    return p;
}

// ---- helpers ---------------------------------------------------------------
function schemaSettings(id, dir = null) {
    const def = Gio.SettingsSchemaSource.get_default();
    let schema = def?.lookup(id, true);
    if (!schema && dir && GLib.file_test(dir, GLib.FileTest.IS_DIR)) {
        try { schema = Gio.SettingsSchemaSource.new_from_directory(dir, def, false).lookup(id, false); } catch (e) {}
    }
    return schema ? new Gio.Settings({settings_schema: schema}) : null;
}
function extSettings(uuid, id) {
    const ext = Main.extensionManager.lookup(uuid);
    if (!ext?.path) return null;
    return schemaSettings(ext.metadata?.['settings-schema'] ?? id, GLib.build_filenamev([ext.path, 'schemas']));
}
function setIf(settings, key, value) {
    if (!settings || !settings.settings_schema.has_key(key)) return;
    const type = settings.settings_schema.get_key(key).get_value_type().dup_string();
    const v = new GLib.Variant(type, value);
    if (!settings.get_value(key).equal(v)) settings.set_value(key, v);
}
const readText = path => { try { const [ok, b] = GLib.file_get_contents(path); return ok ? new TextDecoder().decode(b) : null; } catch (e) { return null; } };
function writeText(path, text) {
    if (readText(path) === text) return false;
    GLib.mkdir_with_parents(GLib.path_get_dirname(path), 0o755);
    GLib.file_set_contents(path, text);
    return true;
}
function themeDir(name) {
    for (const base of [GLib.get_user_data_dir(), ...GLib.get_system_data_dirs()]) {
        const d = GLib.build_filenamev([base, 'themes', name]);
        if (GLib.file_test(GLib.build_filenamev([d, 'gtk-4.0', 'gtk.css']), GLib.FileTest.EXISTS)) return d;
    }
    return null;
}
// Average colour of the wallpaper, pushed to a usable accent.
function wallpaperAccent(uri) {
    try {
        const path = Gio.File.new_for_uri(uri).get_path();
        const pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 32, 32, false);
        const px = pb.get_pixels(), n = pb.get_n_channels(), stride = pb.get_rowstride();
        let best = null, score = -1;
        for (let y = 0; y < pb.get_height(); y += 2) for (let x = 0; x < pb.get_width(); x += 2) {
            const i = y * stride + x * n, hex = rgbHex([px[i], px[i + 1], px[i + 2]]);
            const [, s, l] = toHsl(hex), sc = s * (1 - Math.abs(l - 0.5) * 2);
            if (sc > score) { score = sc; best = hex; }
        }
        if (!best) return null;
        const [h, s] = toHsl(best);
        return fromHsl(h, Math.max(0.25, Math.min(0.75, s)), 0.42);
    } catch (e) { return null; }
}

// ---- generated accent stylesheet ------------------------------------------
function accentCss(p) {
    const P = '#uiGroup.fenestra-themed';
    const sel = list => list.split(',').map(s => `${P} ${s.trim()}`).join(',\n');
    const fillRule = `background-color:${p.fill} !important; color:${p.on} !important; border-color:${p.fill};`;
    return `/* generated by fenestra-tray appearance.js: accent ${p.base} (${p.dark ? 'dark' : 'light'}) */
${sel('.quick-toggle:checked, .quick-toggle-has-menu:checked .quick-toggle, .quick-toggle-has-menu:checked .quick-toggle-menu-button, .button.default, .modal-dialog-button.default, .calendar .calendar-day.calendar-today, .windows-calendar-card .calendar-day.calendar-today, .windows-calendar-card .calendar-day.calendar-today:selected, .windows-panel-small-button:checked, .windows-panel-icon-button:checked')} { ${fillRule} }
${sel('.quick-toggle:checked StIcon, .quick-toggle:checked StLabel, .quick-toggle-has-menu:checked .quick-toggle-menu-button StIcon, .windows-quick-panel .quick-toggle:checked StIcon, .windows-quick-panel .quick-toggle:checked StLabel, .windows-quick-panel .quick-toggle-has-menu:checked .quick-toggle-menu-button StIcon')} { color:${p.on} !important; }
${sel('.windows-calendar-card .calendar-day.calendar-today, .windows-calendar-card .calendar-day.calendar-today:selected')} { box-shadow:none !important; }
${sel('.quick-toggle:checked:hover, .quick-toggle-has-menu:checked .quick-toggle:hover, .quick-toggle-has-menu:checked .quick-toggle-menu-button:hover, .windows-quick-panel .quick-toggle:checked:hover, .windows-quick-panel .quick-toggle:checked:focus, .windows-quick-panel .quick-toggle-has-menu:checked .quick-toggle:hover, .windows-quick-panel .quick-toggle-has-menu:checked .quick-toggle-menu-button:hover, .button.default:hover, .modal-dialog-button.default:hover, .windows-calendar-card .calendar-day.calendar-today:hover, .windows-panel-small-button:checked:hover, .windows-panel-icon-button:checked:hover')} { background-color:${p.hover} !important; color:${p.on} !important; }
${sel('.quick-toggle:checked:active, .windows-quick-panel .quick-toggle:checked:active, .button.default:active, .modal-dialog-button.default:active')} { background-color:${p.press} !important; }
${sel('.windows-quick-panel .quick-toggle-has-menu:checked .quick-toggle-menu-button')} { border-left:1px solid ${rgba(p.on, 0.12)}; }
${sel('.toggle-switch:checked, .toggle-switch:checked:hover')} { background-color:${p.fill}; border-color:${p.fill}; }
${sel('.toggle-switch:checked:hover')} { background-color:${p.hover}; border-color:${p.hover}; }
${sel('.toggle-switch:checked .handle')} { background-color:${p.on}; }
${sel('.check-box:checked StIcon, .check-box:checked:hover StIcon')} { background-color:${p.fill}; border-color:${p.fill}; color:${p.on}; }
${sel('.slider')} { -barlevel-active-background-color:${p.fill}; color:${p.text}; }
${sel('.osd-window .level')} { -barlevel-active-background-color:${p.text}; }
${sel('StEntry:focus')} { border-color:${p.fill}; box-shadow:inset 0 -2px ${p.text}; }
${sel('.button:focus, .quick-toggle:focus, .icon-button:focus, .check-box:focus StBin')} { box-shadow:inset 0 0 0 2px ${rgba(p.text, 0.7)} !important; }
${sel('.popup-menu-item:active, .popup-menu-item:checked')} { background-color:${rgba(p.fill, p.dark ? 0.45 : 0.25)}; }
${sel('.windows-calendar-card .calendar-day:selected')} { box-shadow:inset 0 0 0 1px ${p.text}; }
${sel('.windows-shot-toast .notification-button:first-child')} { background-color:${p.fill}; color:${p.on}; border-color:${p.fill}; }
${sel('.windows-consent-dialog .modal-dialog-button:focus')} { background-color:${p.fill}; color:${p.on}; border-color:${p.dark ? '#ffffff' : p.fill}; }
${sel('.windows-consent-details')} { color:${p.text}; }
${sel('.arcmenu-menu .windows-search-layout .win-search-filter:checked')} { background-color:${p.text} !important; color:${p.textOn}; border:1px solid ${p.text} !important; }
${sel('.arcmenu-menu .windows-search-layout .win-search-filter:checked StLabel')} { color:${p.textOn}; }
${sel('.arcmenu-menu .windows-search-layout .win-result:selected .win-result-indicator')} { background-color:${p.text}; }
${sel('.arcmenu-menu .windows-search-layout .win-preview-button:first-child')} { background-color:${p.fill}; color:${p.on}; }
${sel('.arcmenu-menu .windows-search-layout .win-preview-button:first-child:hover')} { background-color:${p.hover}; }
`;
}

// GTK wrapper theme: base theme + live accent (named colours used by Fenestra-Light/Dark).
function gtkWrapperCss(baseDir, ver, file, p) {
    return `/* generated by fenestra-tray appearance.js */
@import url("file://${baseDir}/${ver}/${file}");
@define-color accent_bg_color ${p.fill};
@define-color accent_fg_color ${p.on};
@define-color accent_color ${p.text};
@define-color theme_selected_bg_color ${p.fill};
@define-color theme_selected_fg_color ${p.on};
`;
}

export class Appearance {
    constructor(extensionPath) {
        this._path = extensionPath;
        this._listeners = new Set();
        this._iface = new Gio.Settings({schema_id: IFACE});
        this._bg = new Gio.Settings({schema_id: 'org.gnome.desktop.background'});
        this._fenestra = schemaSettings(FENESTRA, GLib.build_filenamev([extensionPath, 'schemas']));
        this._theme = St.ThemeContext.get_for_stage(global.stage).get_theme();
        this._light = Gio.File.new_for_path(GLib.build_filenamev([extensionPath, 'light.css']));
        this._theme.load_stylesheet(this._light);
        this._cssDir = GLib.build_filenamev([GLib.get_user_cache_dir(), 'fenestra']);
        this._gen = 0;
        this._ids = [
            [this._iface, this._iface.connect('changed::color-scheme', () => this._queue())],
            [this._iface, this._iface.connect('changed::accent-color', () => this._queue())],
            [this._bg, this._bg.connect('changed', () => { if (this._fenestra?.get_boolean('accent-from-wallpaper')) this._queue(); })],
        ];
        if (this._fenestra)
            this._ids.push([this._fenestra, this._fenestra.connect('changed', () => this._queue())]);
        this._sync();
        // Extensions enabled after us (Dash to Panel / ArcMenu) get their colours too.
        this._extId = Main.extensionManager.connect('extension-state-changed', (_m, ext) => {
            if (ext.uuid === 'dash-to-panel@jderose9.github.com' || ext.uuid === 'arcmenu@arcmenu.com') this._queue();
        });
    }

    get dark() { return this._iface.get_string('color-scheme') === 'prefer-dark'; }

    get accent() {
        const custom = this._fenestra?.get_string('accent-color-custom') ?? '';
        if (this._fenestra?.get_boolean('accent-from-wallpaper')) {
            const uri = this._bg.get_string(this.dark ? 'picture-uri-dark' : 'picture-uri');
            if (uri !== this._wpUri) { this._wpUri = uri; this._wpAccent = wallpaperAccent(uri); }
            if (this._wpAccent) return this._wpAccent;
        }
        if (/^#[0-9a-fA-F]{6}$/.test(custom)) return custom.toLowerCase();
        const name = this._iface.get_string('accent-color');
        return ENUM[name] ? name : 'blue';
    }

    get palette() { return this._palette; }

    connect(fn) { this._listeners.add(fn); return fn; }
    disconnect(fn) { this._listeners.delete(fn); }

    _queue() {
        if (this._idle) return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT, () => { this._idle = 0; this._sync(); return GLib.SOURCE_REMOVE; });
    }

    _sync() {
        const p = this._palette = palette(this.accent, this.dark);
        const key = `${p.base}|${p.dark}`;
        Main.uiGroup.add_style_class_name('fenestra-themed');
        if (p.dark) Main.uiGroup.remove_style_class_name('fenestra-light');
        else Main.uiGroup.add_style_class_name('fenestra-light');
        if (key !== this._key) {
            this._key = key;
            this._loadAccentCss(p);
            for (const fn of this._listeners) { try { fn(p); } catch (e) { logError(e, 'Fenestra appearance listener'); } }
        }
        for (const step of [() => this._gtk(p), () => this._dashToPanel(p), () => this._arcMenu(p)])
            try { step(); } catch (e) { logError(e, 'Fenestra appearance'); }
    }

    _loadAccentCss(p) {
        // Alternate file names: St caches a stylesheet per GFile.
        const file = Gio.File.new_for_path(GLib.build_filenamev([this._cssDir, `shell-accent-${this._gen++ % 2}.css`]));
        writeText(file.get_path(), accentCss(p));
        if (this._accentFile) this._theme.unload_stylesheet(this._accentFile);
        this._theme.load_stylesheet(file);
        this._accentFile = file;
    }

    _gtk(p) {
        // GTK 4 user CSS (desktop/skel/.config/gtk-4.0/gtk.css) imports gtk-auto.css, which
        // switches with prefers-color-scheme and takes the accent from these names;
        // libadwaita apps (they ignore gtk-theme) also read the CSS variables.
        const d = palette(this.accent, true), l = palette(this.accent, false);
        const vars = q => `--accent-bg-color: ${q.fill}; --accent-fg-color: ${q.on}; --accent-color: ${q.text};`;
        writeText(GLib.build_filenamev([GLib.get_user_config_dir(), 'gtk-4.0', 'fenestra-accent.css']),
            `/* generated by fenestra-tray appearance.js */\n@define-color fenestra_accent_dark ${d.fill};\n@define-color fenestra_accent_light ${l.fill};\n` +
            `@define-color fenestra_accent_dark_fg ${d.on};\n@define-color fenestra_accent_light_fg ${l.on};\n` +
            `:root { ${vars(d)} }\n@media (prefers-color-scheme: light) { :root { ${vars(l)} } }\n`);
        const current = this._iface.get_string('gtk-theme');
        const m = current.match(/^(.*)-(Dark|Light)(?:-Accent[AB])?$/);
        if (!m) return;
        const mode = p.dark ? 'Dark' : 'Light';
        let family = m[1], baseDir = themeDir(`${family}-${mode}`);
        if (!baseDir) { family = 'Fenestra'; baseDir = themeDir(`Fenestra-${mode}`); }
        if (!baseDir) return;
        // Wrapper theme (GTK 3 and plain GTK 4): base theme + live accent. In light mode
        // gtk-dark.css stays light too, so a stale gtk-application-prefer-dark-theme can't
        // keep apps dark.
        const files = {};
        for (const ver of ['gtk-3.0', 'gtk-4.0'])
            for (const f of ['gtk.css', 'gtk-dark.css']) {
                const src = p.dark ? f : 'gtk.css';
                if (GLib.file_test(GLib.build_filenamev([baseDir, ver, src]), GLib.FileTest.EXISTS))
                    files[`${ver}/${f}`] = gtkWrapperCss(baseDir, ver, src, p);
            }
        const themes = GLib.build_filenamev([GLib.get_user_data_dir(), 'themes']);
        const wrapper = l => GLib.build_filenamev([themes, `${family}-${mode}-Accent${l}`]);
        const same = l => Object.entries(files).every(([f, css]) => readText(GLib.build_filenamev([wrapper(l), f])) === css);
        const now = current.match(/-Accent([AB])$/)?.[1];
        if (now && current.startsWith(`${family}-${mode}-`) && same(now)) return;
        const next = now === 'A' ? 'B' : 'A';
        for (const [f, css] of Object.entries(files)) writeText(GLib.build_filenamev([wrapper(next), f]), css);
        writeText(GLib.build_filenamev([wrapper(next), 'index.theme']),
            `[Desktop Entry]\nType=X-GNOME-Metatheme\nName=${family}-${mode}\nComment=${family}-${mode} with the Fenestra accent (generated)\n[X-GNOME-Metatheme]\nGtkTheme=${family}-${mode}-Accent${next}\n`);
        this._iface.set_string('gtk-theme', `${family}-${mode}-Accent${next}`);
    }

    _dashToPanel(p) {
        const s = extSettings('dash-to-panel@jderose9.github.com', 'org.gnome.shell.extensions.dash-to-panel');
        if (!s) return;
        const L = !p.dark;
        setIf(s, 'trans-use-custom-bg', true);
        setIf(s, 'trans-use-custom-opacity', true);
        setIf(s, 'trans-bg-color', L ? '#f3f3f3' : '#000402');
        setIf(s, 'trans-panel-opacity', L ? 0.85 : 0.63);
        setIf(s, 'trans-border-custom-color', L ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.10)');
        setIf(s, 'highlight-appicon-hover-background-color', L ? 'rgba(255,255,255,0.70)' : 'rgba(255,255,255,0.08)');
        setIf(s, 'highlight-appicon-pressed-background-color', L ? 'rgba(255,255,255,0.50)' : 'rgba(255,255,255,0.12)');
        setIf(s, 'window-preview-title-font-color', L ? '#1a1a1a' : '#ffffff');
        setIf(s, 'focus-highlight-color', L ? '#000000' : '#ffffff');
        for (const i of [1, 2, 3, 4]) {
            setIf(s, `dot-color-${i}`, p.fill);
            setIf(s, `dot-color-unfocused-${i}`, L ? '#868686' : '#a0a0a0');
        }
    }

    _arcMenu(p) {
        const s = extSettings('arcmenu@arcmenu.com', 'org.gnome.shell.extensions.arcmenu');
        if (!s) return;
        const L = !p.dark;
        setIf(s, 'menu-foreground-color', L ? 'rgb(26,26,26)' : 'rgb(245,245,245)');
        setIf(s, 'menu-border-color', L ? 'rgba(0,0,0,0.10)' : 'rgba(255,255,255,0.14)');
        setIf(s, 'menu-separator-color', L ? 'rgb(229,229,229)' : 'rgb(63,62,64)');
        setIf(s, 'menu-item-hover-bg-color', L ? 'rgba(0,0,0,0.04)' : 'rgba(238,238,236,0.08)');
        setIf(s, 'menu-item-hover-fg-color', L ? 'rgb(26,26,26)' : 'rgb(255,255,255)');
        setIf(s, 'menu-item-active-bg-color', rgba(p.fill, L ? 0.25 : 0.35));
        setIf(s, 'menu-item-active-fg-color', L ? 'rgb(26,26,26)' : 'rgb(255,255,255)');
        setIf(s, 'menu-button-hover-bg-color', [true, L ? 'rgba(255,255,255,0.70)' : 'rgba(255,255,255,0.08)']);
        setIf(s, 'menu-button-active-bg-color', [true, L ? 'rgba(255,255,255,0.50)' : 'rgba(255,255,255,0.12)']);
    }

    // Recoloured copy of one of our white glyph SVGs for the current mode/accent.
    tint(path) {
        const p = this._palette;
        if (!path) return path;
        const key = `${p.dark ? 'd' : 'l'}${p.text}|${path}`;
        this._tintCache ??= new Map();
        const hit = this._tintCache.get(key);
        if (hit) return hit;
        const result = this._tint(path, p);
        if (this._tintCache.size > 256) this._tintCache.clear();
        this._tintCache.set(key, result);
        return result;
    }

    _tint(path, p) {
        const src = readText(path);
        if (src === null) return path;
        const fg = p.dark ? '#ffffff' : '#1a1a1a';
        let out = src.replace(/#ffffff|#eeeeee/gi, fg)
            .replace(/#9fd89f/gi, p.text); // charging fill
        if (!p.dark)
            out = out.replace(/#ff99a4|#e5484d/gi, '#c42b1c').replace(/#fce100|#e5a900/gi, '#9d5d00');
        if (out === src) return path;
        const name = `${GLib.compute_checksum_for_string(GLib.ChecksumType.MD5, path, -1).slice(0, 12)}-${GLib.path_get_basename(path)}`;
        const dest = GLib.build_filenamev([this._cssDir, 'tint', `${p.dark ? 'd' : 'l'}${p.text.slice(1)}`, name]);
        try {
            if (!GLib.file_test(dest, GLib.FileTest.EXISTS)) writeText(dest, out);
        } catch (e) {
            logError(e, 'Fenestra appearance: tint');
            return path;
        }
        return dest;
    }

    destroy() {
        if (this._idle) GLib.source_remove(this._idle);
        for (const [obj, id] of this._ids) obj.disconnect(id);
        Main.extensionManager.disconnect(this._extId);
        if (this._accentFile) this._theme.unload_stylesheet(this._accentFile);
        this._theme.unload_stylesheet(this._light);
        Main.uiGroup.remove_style_class_name('fenestra-themed');
        Main.uiGroup.remove_style_class_name('fenestra-light');
        this._listeners.clear();
    }
}

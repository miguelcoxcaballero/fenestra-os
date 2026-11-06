import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import GWeather from 'gi://GWeather';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {WeatherClient} from 'resource:///org/gnome/shell/misc/weather.js';

// Windows 11 taskbar weather (the default "Widgets" entry at the left end of a
// centred taskbar): condition icon, temperature and a short description.
// Data comes from GNOME Shell's own WeatherClient (GWeather; the location is
// the one chosen in GNOME Weather, or the automatic location when Location is
// on). Clicking opens Weather. Hidden while there is nothing to show, while
// the taskbar is left-aligned or vertical, and when turned off in Settings.

const ES = (GLib.get_language_names()[0] || '').startsWith('es');
const T = {'Weather': ES ? 'El tiempo' : 'Weather'};
let iconTheme = null;

function shortText(info) {
    // "18°C" like the reference, not GWeather's "18 °C".
    const temp = (info.get_temp_summary() || '').replace(/\s+/g, '');
    // Only real data: GWeather returns the text "Unknown" (localised) when it
    // has no sky or phenomenon value.
    let cond = '';
    const [okCond] = info.get_value_conditions?.() ?? [false];
    const [okSky] = info.get_value_sky?.() ?? [false];
    if (okCond)
        cond = info.get_conditions();
    if ((!cond || cond === '-') && okSky)
        cond = info.get_sky();
    if (!cond || cond === '-')
        cond = '';
    cond = cond.charAt(0).toUpperCase() + cond.slice(1);
    return [temp, cond];
}

class WeatherButton {
    constructor(client) {
        this._client = client;
        this.actor = new St.Button({
            style_class: 'fenestra-weather',
            reactive: true, can_focus: true, track_hover: true,
            accessible_name: T['Weather'],
            y_align: Clutter.ActorAlign.FILL,
        });
        const row = new St.BoxLayout({style_class: 'fenestra-weather-row', y_align: Clutter.ActorAlign.CENTER});
        this._icon = new St.Icon({style_class: 'fenestra-weather-icon', icon_size: 28, y_align: Clutter.ActorAlign.CENTER});
        const text = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL, y_align: Clutter.ActorAlign.CENTER});
        this._temp = new St.Label({style_class: 'fenestra-weather-temp'});
        this._cond = new St.Label({style_class: 'fenestra-weather-cond'});
        text.add_child(this._temp);
        text.add_child(this._cond);
        row.add_child(this._icon);
        row.add_child(text);
        this.actor.set_child(row);
        this.actor.connect('clicked', () => this._client.activateApp());
    }

    sync() {
        const c = this._client;
        const info = c.info;
        const ok = c.available && c.hasLocation && info?.is_valid();
        if (ok) {
            const [temp, cond] = shortText(info);
            // Coloured condition icons when the icon theme has them, else symbolic.
            const name = info.get_icon_name();
            // (Light mode: the theme's colour icons are drawn for dark surfaces.)
            iconTheme ??= new St.IconTheme();
            const light = Main.uiGroup.has_style_class_name('fenestra-light');
            this._icon.icon_name = !light && name && iconTheme.has_icon(name) ? name : info.get_symbolic_icon_name();
            this._temp.text = temp;
            this._cond.text = cond;
            this._cond.visible = cond !== '';
            this.actor.accessible_name = `${T['Weather']}: ${temp} ${cond}`;
        }
        return ok;
    }

    destroy() {
        this.actor.destroy();
    }
}

export function installWeatherWidget(settings) {
    let client = null;
    try {
        client = new WeatherClient();
    } catch (e) {
        console.warn(`Fenestra weather: ${e.message}`);
        return () => {};
    }
    const buttons = new Map(); // dash-to-panel panel -> WeatherButton
    let pending = 0;

    const panels = () => (global.dashToPanel?.panels ?? []).filter(p => p.panelBox && !p.geom?.vertical);

    const place = () => {
        pending = 0;
        const enabled = settings.get_boolean('taskbar-widgets');
        const live = new Set(panels());
        for (const [panel, button] of buttons) {
            if (!live.has(panel) || !enabled) {
                button.destroy();
                buttons.delete(panel);
            }
        }
        if (!enabled)
            return GLib.SOURCE_REMOVE;
        for (const panel of live) {
            let button = buttons.get(panel);
            if (!button) {
                button = new WeatherButton(client);
                // Follow taskbar alignment / size changes right away.
                for (const actor of [panel.panelBox, panel._leftBox].filter(Boolean))
                    actor.connectObject('notify::allocation', queue, button.actor);
                Main.layoutManager.addChrome(button.actor, {trackFullscreen: true});
                buttons.set(panel, button);
            }
            const box = panel.panelBox;
            const [x, y] = box.get_transformed_position();
            const [w, h] = box.get_transformed_size();
            // Only next to a centred taskbar: left-aligned icons start at the edge.
            const left = panel._leftBox;
            const [lx] = left?.get_transformed_position?.() ?? [x + w];
            const room = lx - x > 220;
            const shown = button.sync() && room && box.visible && w > 0;
            button.actor.visible = shown;
            if (shown) {
                button.actor.set_position(Math.round(x + 4), Math.round(y));
                button.actor.set_size(-1, Math.round(h));
            }
        }
        return GLib.SOURCE_REMOVE;
    };
    const queue = () => {
        if (!pending)
            pending = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, place);
    };

    const ids = [
        [client, client.connect('changed', queue)],
        [settings, settings.connect('changed::taskbar-widgets', queue)],
        [Main.layoutManager, Main.layoutManager.connect('monitors-changed', queue)],
        [Main.layoutManager, Main.layoutManager.connect('startup-complete', queue)],
    ];
    if (global.dashToPanel?.connect)
        ids.push([global.dashToPanel, global.dashToPanel.connect('panels-created', queue)]);
    // Panels are rebuilt when Dash to Panel settings change; check periodically,
    // and refresh the weather every 15 minutes (WeatherClient rate-limits itself).
    const timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 10, () => {
        place();
        return GLib.SOURCE_CONTINUE;
    });
    const refresh = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 15 * 60, () => {
        client.update();
        return GLib.SOURCE_CONTINUE;
    });
    client.update();
    queue();

    return () => {
        if (pending)
            GLib.source_remove(pending);
        GLib.source_remove(timer);
        GLib.source_remove(refresh);
        for (const [obj, id] of ids)
            obj.disconnect(id);
        for (const button of buttons.values())
            button.destroy();
        buttons.clear();
        client = null;
    };
}

// GWeather is imported so the typelib is required up front (clear error if missing).
void GWeather;

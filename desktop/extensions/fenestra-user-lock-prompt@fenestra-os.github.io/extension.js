import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import St from 'gi://St';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';

export default class UserLockPrompt extends Extension {
    enable() {
        this._injections = new InjectionManager();
        this._clocks = new Map();
        const extension = this;
        this._injections.overrideMethod(Main.screenShield, '_resetLockScreen',
            original => function (...args) {
                const result = original.apply(this, args);
                if (!this._isGreeter && this._dialog?._clock)
                    extension._decorate(this._dialog._clock);
                return result;
            });
    }

    _decorate(clock) {
        if (this._clocks.has(clock))
            return;
        const label = new St.Label({
            text: GLib.get_real_name() || GLib.get_user_name(),
            style_class: 'unlock-dialog-clock-date',
            x_align: Clutter.ActorAlign.CENTER,
        });
        const timeVisible = clock._time.visible;
        const dateVisible = clock._date.visible;
        clock._time.hide();
        clock._date.hide();
        clock.insert_child_at_index(label, 0);
        const destroyId = clock.connect('destroy', () => this._clocks.delete(clock));
        this._clocks.set(clock, {label, timeVisible, dateVisible, destroyId});
    }

    disable() {
        this._injections?.clear();
        for (const [clock, state] of this._clocks) {
            clock.disconnect(state.destroyId);
            state.label.destroy();
            clock._time.visible = state.timeVisible;
            clock._date.visible = state.dateVisible;
        }
        this._clocks.clear();
        this._injections = null;
    }
}

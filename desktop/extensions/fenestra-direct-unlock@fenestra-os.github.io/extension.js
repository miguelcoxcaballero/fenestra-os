import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export default class DirectUnlock extends Extension {
    enable() {
        this._injections = new InjectionManager();
        this._injections.overrideMethod(Main.screenShield, '_resetLockScreen',
            original => function (...args) {
                const result = original.apply(this, args);
                if (!this._isGreeter && this._dialog)
                    this._dialog.activate();
                return result;
            });
    }

    disable() {
        this._injections?.clear();
        this._injections = null;
    }
}

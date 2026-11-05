// TEST ONLY: lets tests/shell/shell.sh drive a headless gnome-shell through
// org.gnome.Shell.Eval / org.gnome.Shell.Screenshot. Never ship this.
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class UnsafeMode extends Extension {
    enable() {
        global.context.unsafe_mode = true;
    }

    disable() {
        global.context.unsafe_mode = false;
    }
}

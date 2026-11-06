// SPDX-License-Identifier: GPL-3.0-or-later
// Test only: for every file /tmp/shotreq/NAME, save the stage to /out/NAME.png.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
Gio._promisify(Shell.Screenshot.prototype, 'screenshot_stage_to_content');
Gio._promisify(Shell.Screenshot, 'composite_to_stream');
export default class ShotQA extends Extension {
    enable() {
        GLib.mkdir_with_parents('/tmp/shotreq', 0o777);
        print('SHOTQA ready');
        this._id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => { this.poll(); return GLib.SOURCE_CONTINUE; });
    }
    disable() { GLib.source_remove(this._id); }
    async poll() {
        if (this._busy) return;
        const dir = Gio.File.new_for_path('/tmp/shotreq');
        const en = dir.enumerate_children('standard::name', 0, null);
        let info;
        while ((info = en.next_file(null))) {
            const n = info.get_name();
            dir.get_child(n).delete(null);
            this._busy = true;
            try {
                const [c] = await new Shell.Screenshot().screenshot_stage_to_content();
                const st = Gio.MemoryOutputStream.new_resizable();
                await Shell.Screenshot.composite_to_stream(c.get_texture(), 0, 0, -1, -1, 1, null, 0, 0, 1, st);
                st.close(null);
                GLib.file_set_contents(`/out/${n}.png`, st.steal_as_bytes().toArray());
                print(`SHOTQA saved ${n}`);
            } catch (e) { print(`SHOTQA fail ${e}`); }
            this._busy = false;
        }
    }
}

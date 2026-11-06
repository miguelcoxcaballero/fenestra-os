// Greeter test probe: reports extension states and the login dialog's visible state,
// takes screenshots, and dismisses the Fenestra curtain like a key press would.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
Gio._promisify(Shell.Screenshot.prototype, 'screenshot_stage_to_content');
Gio._promisify(Shell.Screenshot, 'composite_to_stream');
const wait = ms => new Promise(r => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => { r(); return GLib.SOURCE_REMOVE; }));
const OUT = GLib.getenv('QA_OUT') || '/out';
export default class QA extends Extension {
    enable() { GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => { this.run().catch(e => print(`QA_FAIL ${e}\n${e.stack}`)); return GLib.SOURCE_REMOVE; }); }
    async cap(n) {
        try {
            const [c] = await new Shell.Screenshot().screenshot_stage_to_content();
            const st = Gio.MemoryOutputStream.new_resizable();
            await Shell.Screenshot.composite_to_stream(c.get_texture(), 0, 0, -1, -1, 1, null, 0, 0, 1, st);
            st.close(null);
            GLib.file_set_contents(`${OUT}/${n}.png`, st.steal_as_bytes().toArray());
        } catch (e) { print(`QA_FAIL cap ${e}`); }
    }
    state(tag) {
        const d = Main.screenShield?._dialog;
        const box = d?._userSelectionBox;
        const curtain = Main.layoutManager.screenShieldGroup.get_children().filter(a => a.constructor.name === 'St_Widget' && a.reactive);
        print(`QA_STATE ${tag} ` + JSON.stringify({
            mode: Main.sessionMode.currentMode, dialog: d?.constructor?.name ?? null, listLoaded: !!d?._userListLoaded,
            listOpacity: box?.opacity, listVisible: box?.visible, listMapped: box?.mapped,
            promptVisible: !!d?._authPrompt?.visible && d?._authPrompt?.opacity > 0, curtains: curtain.length,
        }));
    }
    async run() {
        for (let i = 0; i < 40 && !Main.screenShield?._dialog?._userListLoaded; i++) await wait(500);
        await wait(4000);
        for (const [uuid, e] of Main.extensionManager._extensions)
            print(`QA_EXT ${uuid} state=${e.state}${e.error ? ` ERROR=${e.error}` : ''}`);
        this.state('initial');
        await this.cap('greeter-1');
        const ext = Main.extensionManager.lookup(GLib.getenv('QA_LOGIN_EXT') || 'single-user-gdm@local');
        if (ext?.stateObj?._curtain) {
            ext.stateObj._dismiss(Main.screenShield._dialog);
            await wait(1500);
            this.state('after-dismiss');
            await this.cap('greeter-2');
        } else {
            print('QA_NOTE no curtain to dismiss');
        }
        print('QA_DONE');
    }
    disable() {}
}

// Greeter test probe: reports extension states and the login dialog's state, takes
// screenshots, dismisses the Fenestra curtain like a key press would, and prints a verdict:
//   QA_RESULT PASS  the standard or Fenestra login form ends up visible and usable
//   QA_RESULT FAIL  the form stays hidden (opacity 0 / unmapped) or a dead curtain covers it
// In the user session (QA_MODE=user) it locks the screen and checks the unlock dialog.
import Clutter from 'gi://Clutter';
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
    enable() {
        if (this._started)
            return;   // re-enabled after a session-mode change (user -> unlock-dialog)
        this._started = true;
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
            this.run().catch(e => print(`QA_FAIL ${e}\n${e.stack}`));
            return GLib.SOURCE_REMOVE;
        });
    }
    async cap(n) {
        try {
            const [c] = await new Shell.Screenshot().screenshot_stage_to_content();
            const st = Gio.MemoryOutputStream.new_resizable();
            await Shell.Screenshot.composite_to_stream(c.get_texture(), 0, 0, -1, -1, 1, null, 0, 0, 1, st);
            st.close(null);
            GLib.file_set_contents(`${OUT}/${n}.png`, st.steal_as_bytes().toArray());
        } catch (e) { print(`QA_FAIL cap ${e}`); }
    }
    curtains() {
        // Fenestra's curtain: a reactive, full-screen St.Widget in screenShieldGroup that the
        // extension styled with a background colour (black, or transparent over a shared
        // background). GNOME's own unstyled widgets there are part of the normal greeter.
        const m = Main.layoutManager.primaryMonitor;
        return Main.layoutManager.screenShieldGroup.get_children().filter(a =>
            a.constructor.name === 'St_Widget' && a.reactive && a.visible && a.mapped &&
            a.width >= m.width && a.height >= m.height && /background-color/.test(a.get_style?.() ?? '')).length;
    }
    loginState(tag) {
        const d = Main.screenShield?._dialog;
        const box = d?._userSelectionBox;
        const prompt = d?._authPrompt;
        const s = {
            mode: Main.sessionMode.currentMode, dialog: d?.constructor?.name ?? null,
            listLoaded: !!d?._userListLoaded, users: d?._userList?._items?.size ?? 0,
            listOpacity: box?.opacity, listVisible: !!box?.visible, listMapped: !!box?.mapped,
            promptVisible: !!prompt?.visible && prompt?.mapped && prompt?.opacity > 0, curtains: this.curtains(),
        };
        print(`QA_STATE ${tag} ${JSON.stringify(s)}`);
        return s;
    }
    usable(s) {
        if (s.curtains > 0)
            return false;   // a curtain left on screen = the black screen of the bug
        return (s.listVisible && s.listMapped && s.listOpacity > 0) || s.promptVisible;
    }
    async runGreeter() {
        for (let i = 0; i < 40 && !Main.screenShield?._dialog?._userListLoaded; i++)
            await wait(500);
        await wait(4000);
        let s = this.loginState('initial');
        await this.cap('greeter-1');
        const ext = Main.extensionManager.lookup(GLib.getenv('QA_LOGIN_EXT') || 'single-user-gdm@local');
        if (ext?.stateObj?._curtain) {
            print('QA_NOTE curtain shown; dismissing it like a key press');
            try {
                ext.stateObj._dismiss(Main.screenShield._dialog);
            } catch (e) {
                print(`QA_NOTE dismissing the curtain threw: ${e}`);   // a key press would hit the same error
            }
            await wait(2000);
            s = this.loginState('after-dismiss');
            await this.cap('greeter-2');
        } else if (s.curtains > 0) {
            // A curtain the extension no longer tracks (it threw half-way): a key press
            // cannot dismiss it either.
            print('QA_NOTE orphan curtain on screen');
        } else {
            print('QA_NOTE no curtain (standard login)');
        }
        if (!s.listLoaded || s.users === 0)
            print('QA_NOTE no users loaded (AccountsService)');
        print(`QA_RESULT ${this.usable(s) && s.listLoaded && this.extensionsOk() ? 'PASS' : 'FAIL'}`);
    }
    async runUser() {
        await wait(5000);
        if (!Main.screenShield) {
            print('QA_RESULT FAIL no screen shield (logind/GDM stubs?)');
            return;
        }
        try {
            Main.screenShield.lock(false);
        } catch (e) {
            print(`QA_NOTE locking threw: ${e}`);
        }
        await wait(5000);
        // The shield starts blanked; a pointer motion wakes it, as on a real machine.
        try {
            const seat = global.stage.context.get_backend().get_default_seat();
            const ptr = seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
            const t = global.get_current_time() * 1000;
            ptr.notify_absolute_motion(t, 400, 400);
            ptr.notify_absolute_motion(t + 20000, 900, 600);
        } catch (e) {
            print(`QA_NOTE wake: ${e}`);
        }
        await wait(3000);
        const d = Main.screenShield._dialog;
        print(`QA_STATE locked ${JSON.stringify({locked: Main.screenShield._isLocked, mode: Main.sessionMode.currentMode,
            dialog: d?.constructor?.name ?? null, backgrounds: d?._backgroundGroup?.get_n_children?.() ?? 0})}`);
        await this.cap('unlock-1');
        const bgs = d?._backgroundGroup?.get_n_children?.() ?? 0;
        print(`QA_RESULT ${Main.screenShield._isLocked && d && bgs > 0 && this.extensionsOk() ? 'PASS' : 'FAIL'}`);
    }
    // Extensions under test (QA_TESTED, space separated) must not be in the ERROR state.
    extensionsOk() {
        const bad = (GLib.getenv('QA_TESTED') || '').split(/\s+/).filter(Boolean).filter(u => {
            const e = Main.extensionManager.lookup(u);
            return !e || e.state === 3 || e.error;
        });
        if (bad.length)
            print(`QA_NOTE extensions failed or missing: ${bad.join(' ')}`);
        return bad.length === 0;
    }
    async run() {
        for (const [uuid, e] of Main.extensionManager._extensions)
            print(`QA_EXT ${uuid} state=${e.state}${e.error ? ` ERROR=${e.error}` : ''}`);
        if (Main.sessionMode.isGreeter)
            await this.runGreeter();
        else
            await this.runUser();
        print('QA_DONE');
    }
    disable() {}
}

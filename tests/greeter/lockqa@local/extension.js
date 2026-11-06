// Lock-screen probe: lock, report the unlock dialog and extension states, screenshot, unlock.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
Gio._promisify(Shell.Screenshot.prototype, 'screenshot_stage_to_content');
Gio._promisify(Shell.Screenshot, 'composite_to_stream');
const wait = ms => new Promise(r => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => { r(); return GLib.SOURCE_REMOVE; }));
let started = false;
export default class QA extends Extension {
    enable() { if (started) return; started = true; GLib.timeout_add(GLib.PRIORITY_DEFAULT, 6000, () => { this.run().catch(e => print(`QA_FAIL ${e}\n${e.stack}`)); return GLib.SOURCE_REMOVE; }); }
    disable() {}
    async cap(n) {
        try {
            const [c] = await new Shell.Screenshot().screenshot_stage_to_content();
            const st = Gio.MemoryOutputStream.new_resizable();
            await Shell.Screenshot.composite_to_stream(c.get_texture(), 0, 0, -1, -1, 1, null, 0, 0, 1, st);
            st.close(null);
            GLib.file_set_contents(`/out/${n}.png`, st.steal_as_bytes().toArray());
        } catch (e) { print(`QA_FAIL cap ${e}`); }
    }
    // Windows Hello feedback: feed Howdy's two notices through the real verifier queue and
    // check that the face animation shows and plays (GNOME 51 'show-message' is one object).
    async hello() {
        const prompt = Main.screenShield?._dialog?._authPrompt;
        const verifier = prompt?._userVerifier;
        if (!verifier) { print('QA_HELLO no-verifier'); return; }
        let MessageType;
        try { ({MessageType} = await import('resource:///org/gnome/shell/gdm/userVerifier.js')); }
        catch { ({MessageType} = await import('resource:///org/gnome/shell/gdm/util.js')); }
        const box = prompt.get_children().find(c => c.width === 64 && c.height === 64 && c.get_n_children() > 4);
        if (!box) { print('QA_HELLO no-box'); return; }
        const shown = () => box.get_children().filter(c => c.visible).map(c => box.get_children().indexOf(c));
        const send = text => verifier._queueMessage.length === 1 || verifier._queueMessage.length === 0
            ? verifier._queueMessage({serviceName: 'gdm-password', message: text, messageType: MessageType.INFO, wiggle: false})
            : verifier._queueMessage('gdm-password', text, MessageType.INFO);
        send('Attempting facial authentication');
        await wait(700); const a = shown(); await wait(400); const b = shown();
        print(`QA_HELLO searching opacity=${box.opacity} frames=${JSON.stringify(a)}->${JSON.stringify(b)}`);
        await this.cap('hello-searching');
        send('Identified face as gdmtest');
        await wait(700);
        print(`QA_HELLO authenticated opacity=${box.opacity} frame=${JSON.stringify(shown())}`);
        await this.cap('hello-ok');
        const ok = box.opacity === 255 && a.length === 1 && b.length === 1 && a[0] !== b[0];
        print(`QA_HELLO_RESULT ${ok ? 'PASS' : 'FAIL'}`);
    }
    exts(tag) { for (const [u, e] of Main.extensionManager._extensions) print(`QA_EXT ${tag} ${u} state=${e.state}${e.error ? ` ERROR=${e.error}` : ''}`); }
    async run() {
        this.exts('desktop');
        await this.cap('desktop');
        const c = Main.extensionManager.lookup('arcmenu@arcmenu.com')?.stateObj?.menuControllers?.[0];
        if (c) {
            for (let i = 0; i < 2; i++) {
                c._menuButton.toggleMenu(); await wait(700);
                print(`QA_START open=${c._menuButton.arcMenu.isOpen}`);
                await this.cap(`start-${i}`);
                c._menuButton.arcMenu.close(); await wait(500);
            }
        }
        print(`QA_SHIELD ${!!Main.screenShield}`);
        Main.screenShield?.lock(false);
        await wait(4000);
        print(`QA_LOCKED mode=${Main.sessionMode.currentMode} active=${Main.screenShield?.active} dialog=${Main.screenShield?._dialog?.constructor?.name}`);
        this.exts('locked');
        const labels = [], bgs = [];
        const walk = (a, depth) => {
            if (!a || depth > 40 || !a.visible) return;
            if (a.text && a.opacity > 0 && a.get_paint_opacity?.() > 0) labels.push(a.text.slice(0, 40));
            const st = a.get_style?.() ?? '';
            if (st.includes('background-image')) bgs.push(`${a.width}x${a.height}`);
            if (a.constructor?.name === 'Meta_BackgroundActor') bgs.push(`meta ${a.width}x${a.height}`);
            for (const c of a.get_children?.() ?? []) walk(c, depth + 1);
        };
        walk(Main.layoutManager.screenShieldGroup, 0);
        print('QA_LOCK_TEXT ' + JSON.stringify(labels));
        print('QA_LOCK_BG ' + JSON.stringify(bgs));
        await this.cap('locked');
        Main.screenShield?._dialog?._showPrompt?.();
        await wait(1500);
        await this.cap('locked-prompt');
        await this.hello();
        Main.screenShield?.deactivate(false);
        await wait(2500);
        print(`QA_UNLOCKED mode=${Main.sessionMode.currentMode} active=${Main.screenShield?.active}`);
        this.exts('unlocked');
        print('QA_DONE');
    }
}

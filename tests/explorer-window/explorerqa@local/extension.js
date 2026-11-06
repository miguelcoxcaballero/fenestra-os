// SPDX-License-Identifier: GPL-3.0-or-later
// Test only. Every file /tmp/shotreq/JOB is a script, one command per line:
//   win X Y W H        move/resize the newest normal window (frame rect = visible box)
//   move X Y | click X Y [BUTTON] | down X Y | up [BUTTON] | scroll X Y DY
//   key [ctrl+][shift+][alt+]KEYNAME   (Clutter key names: Return, F2, 6, Escape, ...)
//   type TEXT | wait MS | shot NAME (stage saved to /out/NAME.png)
//   tree NAME          widget tree of the Nautilus windows to /out/NAME.tree.txt (fenestra_treedump.py)
// When a script ends, /out/JOB.done is written.
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
Gio._promisify(Shell.Screenshot.prototype, 'screenshot_stage_to_content');
Gio._promisify(Shell.Screenshot, 'composite_to_stream');
const sleep = ms => new Promise(r => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => { r(); return GLib.SOURCE_REMOVE; }));
const now = () => GLib.get_monotonic_time();
const MODS = {ctrl: Clutter.KEY_Control_L, shift: Clutter.KEY_Shift_L, alt: Clutter.KEY_Alt_L, super: Clutter.KEY_Super_L};
export default class ExplorerQA extends Extension {
    enable() {
        GLib.mkdir_with_parents('/tmp/shotreq', 0o777);
        const seat = global.stage.context.get_backend().get_default_seat();
        this._ptr = seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
        this._kbd = seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        print('SHOTQA ready');
        this._id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, () => { this.poll(); return GLib.SOURCE_CONTINUE; });
    }
    disable() { GLib.source_remove(this._id); }
    async shot(name) {
        const [c] = await new Shell.Screenshot().screenshot_stage_to_content();
        const st = Gio.MemoryOutputStream.new_resizable();
        await Shell.Screenshot.composite_to_stream(c.get_texture(), 0, 0, -1, -1, 1, null, 0, 0, 1, st);
        st.close(null);
        GLib.file_set_contents(`/out/${name}.png`, st.steal_as_bytes().toArray());
        print(`SHOTQA saved ${name}`);
    }
    key(spec) {
        const parts = spec.split('+');
        const name = parts.pop();
        let sym = Clutter[`KEY_${name}`];
        if (sym === undefined) sym = Clutter.unicode_to_keysym(name.codePointAt(0));
        const mods = parts.map(m => MODS[m]);
        for (const m of mods) this._kbd.notify_keyval(now(), m, Clutter.KeyState.PRESSED);
        this._kbd.notify_keyval(now(), sym, Clutter.KeyState.PRESSED);
        this._kbd.notify_keyval(now(), sym, Clutter.KeyState.RELEASED);
        for (const m of mods.reverse()) this._kbd.notify_keyval(now(), m, Clutter.KeyState.RELEASED);
    }
    async run(lines) {
        for (const line of lines) {
            const [cmd, ...a] = line.trim().split(/\s+/);
            const n = a.map(Number);
            if (cmd === 'win') {
                Main.overview.hide(); Main.layoutManager.panelBox.hide();
                const wins = global.get_window_actors().map(x => x.meta_window).filter(w => w.get_window_type() === Meta.WindowType.NORMAL);
                const w = wins[wins.length - 1];
                if (w) { if (w.get_maximized && w.get_maximized()) w.unmaximize(Meta.MaximizeFlags.BOTH); w.move_resize_frame(false, n[0], n[1], n[2], n[3]); w.activate(global.get_current_time()); }
                await sleep(300); const r = w && w.get_frame_rect(); print(`SHOTQA win ${w ? w.get_wm_class() : 'none'} ${r ? [r.x, r.y, r.width, r.height].join(' ') : ''}`);
            } else if (cmd === 'move') this._ptr.notify_absolute_motion(now(), n[0], n[1]);
            else if (cmd === 'down' || cmd === 'click') {
                this._ptr.notify_absolute_motion(now(), n[0], n[1]);
                await sleep(60);
                this._ptr.notify_button(now(), n[2] || 1, Clutter.ButtonState.PRESSED);
                if (cmd === 'click') { await sleep(40); this._ptr.notify_button(now(), n[2] || 1, Clutter.ButtonState.RELEASED); }
            } else if (cmd === 'up') this._ptr.notify_button(now(), n[0] || 1, Clutter.ButtonState.RELEASED);
            else if (cmd === 'scroll') { this._ptr.notify_absolute_motion(now(), n[0], n[1]); this._ptr.notify_discrete_scroll(now(), n[2] > 0 ? Clutter.ScrollDirection.DOWN : Clutter.ScrollDirection.UP, Clutter.ScrollSource.WHEEL); }
            else if (cmd === 'key') this.key(a[0]);
            else if (cmd === 'type') for (const ch of a.join(' ')) { const s = Clutter.unicode_to_keysym(ch.codePointAt(0)); this._kbd.notify_keyval(now(), s, Clutter.KeyState.PRESSED); this._kbd.notify_keyval(now(), s, Clutter.KeyState.RELEASED); await sleep(20); }
            else if (cmd === 'wait') await sleep(n[0]);
            else if (cmd === 'shot') await this.shot(a[0]);
            else if (cmd === 'tree') { GLib.mkdir_with_parents('/tmp/treedump', 0o777); GLib.file_set_contents(`/tmp/treedump/${a[0]}`, ''); await sleep(1200); }
            if (cmd !== 'wait') await sleep(80);
        }
    }
    async poll() {
        if (this._busy) return;
        const dir = Gio.File.new_for_path('/tmp/shotreq');
        const en = dir.enumerate_children('standard::name', 0, null);
        let info;
        while ((info = en.next_file(null))) {
            const n = info.get_name();
            if (n.endsWith('.tmp')) continue;
            const f = dir.get_child(n);
            const [, bytes] = f.load_contents(null);
            f.delete(null);
            this._busy = true;
            try { await this.run(new TextDecoder().decode(bytes).split('\n').filter(l => l.trim())); }
            catch (e) { print(`SHOTQA fail ${e}`); }
            GLib.file_set_contents(`/out/${n}.done`, 'ok');
            this._busy = false;
        }
    }
}

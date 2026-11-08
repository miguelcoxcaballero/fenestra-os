// SPDX-License-Identifier: GPL-3.0-or-later
// Test only. Every file /tmp/shotreq/JOB is a script, one command per line:
//   win X Y [W H]      move/resize the newest normal window (frame rect = visible box)
//   move X Y | click X Y [BUTTON] | down X Y | up [BUTTON] | scroll X Y DY
//   key [ctrl+][shift+][alt+]KEYNAME   (Clutter key names: Return, F2, 6, Escape, ...)
//   type TEXT | wait MS | shot NAME (stage saved to /out/NAME.png)
//   tree NAME          widget tree of the Nautilus windows to /out/NAME.tree.txt (fenestra_treedump.py)
//   burst NAME MS      stage frames as fast as they come for MS ms: NAME-NNN.png + NAME.times.json
//                      (ms since the burst started, taken right after the previous command)
// When a script ends, /out/JOB.done is written. SHOTQA_REQ / SHOTQA_OUT replace /tmp/shotreq and
// /out (host benches, tests/explorer-dialogs/host.sh).
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
const REQ = GLib.getenv('SHOTQA_REQ') || '/tmp/shotreq';
const OUT = GLib.getenv('SHOTQA_OUT') || '/out';
const MODS = {ctrl: Clutter.KEY_Control_L, shift: Clutter.KEY_Shift_L, alt: Clutter.KEY_Alt_L, super: Clutter.KEY_Super_L};
export default class ExplorerQA extends Extension {
    enable() {
        GLib.mkdir_with_parents(REQ, 0o777);
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
        GLib.file_set_contents(`${OUT}/${name}.png`, st.steal_as_bytes().toArray());
        print(`SHOTQA saved ${name}`);
    }
    async burst(name, ms) {
        // Every painted frame: wait for the stage's after-paint, then read it back (PNG encoding
        // happens after the burst so it does not slow the capture down).
        const t0 = now(), frames = [];
        while ((now() - t0) / 1000 < ms) {
            await new Promise(r => { const id = global.stage.connect('after-paint', () => { global.stage.disconnect(id); r(); }); global.stage.queue_redraw(); });
            const t = (now() - t0) / 1000;
            const [c] = await new Shell.Screenshot().screenshot_stage_to_content();
            frames.push([t, c.get_texture()]);
        }
        const times = [];
        for (const [i, [t, tex]] of frames.entries()) {
            const st = Gio.MemoryOutputStream.new_resizable();
            await Shell.Screenshot.composite_to_stream(tex, 0, 0, -1, -1, 1, null, 0, 0, 1, st);
            st.close(null);
            const n = `${name}-${String(i).padStart(3, '0')}`;
            GLib.file_set_contents(`${OUT}/${n}.png`, st.steal_as_bytes().toArray());
            times.push([n, Math.round(t * 10) / 10]);
        }
        GLib.file_set_contents(`${OUT}/${name}.times.json`, JSON.stringify(times));
        print(`SHOTQA burst ${name} ${frames.length}`);
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
                const normal = () => global.get_window_actors().map(x => x.meta_window).filter(w => w.get_window_type() === Meta.WindowType.NORMAL && w.get_frame_rect().width > 0);
                // Nautilus may map its window well after the job starts (cold caches) and settle its
                // size later still: wait up to 15 s for it and re-apply the box until it sticks.
                let w = null, r = null;
                for (let i = 0; i < 60; i++) {
                    w = normal().at(-1);
                    if (w) {
                        if (w.get_maximized && w.get_maximized()) w.unmaximize(Meta.MaximizeFlags.BOTH);
                        // "win X Y" keeps the window's own size (e.g. a dialog's default size).
                        const r0 = w.get_frame_rect(), ww = n[2] || r0.width, hh = n[3] || r0.height;
                        w.move_resize_frame(false, n[0], n[1], ww, hh); w.activate(global.get_current_time());
                        await sleep(300); r = w.get_frame_rect();
                        if (r.x === n[0] && r.y === n[1] && r.width === ww && r.height === hh) break;
                    } else await sleep(250);
                }
                print(`SHOTQA win ${w ? w.get_wm_class() : 'none'} ${r ? [r.x, r.y, r.width, r.height].join(' ') : ''}`);
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
            else if (cmd === 'burst') await this.burst(a[0], n[1] || 500);
            else if (cmd === 'tree') { GLib.mkdir_with_parents(GLib.getenv('TREEDUMP_REQ') || '/tmp/treedump', 0o777); GLib.file_set_contents(`${GLib.getenv('TREEDUMP_REQ') || '/tmp/treedump'}/${a[0]}`, ''); await sleep(1200); }
            if (cmd !== 'wait') await sleep(80);
        }
    }
    async poll() {
        if (this._busy) return;
        const dir = Gio.File.new_for_path(REQ);
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
            GLib.file_set_contents(`${OUT}/${n}.done`, 'ok');
            this._busy = false;
        }
    }
}

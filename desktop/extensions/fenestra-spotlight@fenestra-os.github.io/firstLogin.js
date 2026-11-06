import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// First login after setup (like the reference): the desktop is never seen
// half-built. A black curtain covers the screen from the moment the shell
// starts until the Fenestra setup window (privacy pages … "Hi" …) has drawn
// its first frame. When that window closes, the curtain is back at once (it
// continues the black finale) and only fades away once the desktop is
// rendering smoothly, so the first thing the user sees is a ready desktop.
//
// Only active while ~/.config/gnome-initial-setup-done does not exist (the
// setup writes it when it finishes). A safety timeout always removes it.

const OOBE_ID = 'org.fenestra.Oobe';
const SAFETY_SECONDS = 90;
const SMOOTH_TICKS = 15;      // 15 x 100 ms on time = 1.5 s of smooth shell
const SETTLE_MAX_SECONDS = 15;

function isOobe(win) {
    return win?.get_gtk_application_id?.() === OOBE_ID || win?.get_wm_class?.() === OOBE_ID;
}

export function installFirstLoginCurtain() {
    if (Main.sessionMode.isGreeter || Main.sessionMode.currentMode !== 'user')
        return () => {};
    const done = GLib.build_filenamev([GLib.get_user_config_dir(), 'gnome-initial-setup-done']);
    if (GLib.file_test(done, GLib.FileTest.EXISTS))
        return () => {};

    let curtain = new St.Widget({
        name: 'fenestraFirstLoginCurtain', reactive: true,
        style: 'background-color: #000000;',
        x: 0, y: 0, width: global.screen_width, height: global.screen_height,
    });
    Main.layoutManager.addTopChrome(curtain);
    const ids = [];
    const timers = new Set();
    let oobeSeen = false;

    const later = (ms, fn) => {
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            const again = fn();
            if (again !== GLib.SOURCE_CONTINUE)
                timers.delete(id);
            return again;
        });
        timers.add(id);
        return id;
    };
    const cleanup = () => {
        for (const id of timers)
            GLib.source_remove(id);
        timers.clear();
        for (const [obj, id] of ids)
            obj.disconnect(id);
        ids.length = 0;
        curtain?.destroy();
        curtain = null;
    };
    const fadeOut = () => {
        if (!curtain)
            return;
        curtain.remove_all_transitions();
        curtain.ease({
            opacity: 0, duration: 450, mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onStopped: cleanup,
        });
    };
    // The shell is "smooth" when 100 ms timers fire on time for 1.5 s.
    const settleThenReveal = () => {
        let last = GLib.get_monotonic_time(), good = 0;
        const start = last;
        later(100, () => {
            const now = GLib.get_monotonic_time();
            good = now - last < 130000 ? good + 1 : 0;
            last = now;
            if (good >= SMOOTH_TICKS || now - start > SETTLE_MAX_SECONDS * 1e6) {
                fadeOut();
                return GLib.SOURCE_REMOVE;
            }
            return GLib.SOURCE_CONTINUE;
        });
    };
    const watched = new Set();
    const watchOobe = win => {
        if (!win || watched.has(win))
            return;
        if (!isOobe(win)) {
            // Wayland clients set their app id after the window is created.
            const recheck = () => {
                if (isOobe(win))
                    watchOobe(win);
            };
            ids.push([win, win.connect('notify::wm-class', recheck)]);
            ids.push([win, win.connect('notify::gtk-application-id', recheck)]);
            return;
        }
        watched.add(win);
        oobeSeen = true;
        const actor = win.get_compositor_private();
        const reveal = () => {
            // The setup is full screen and covers the desktop itself.
            if (curtain) {
                curtain.remove_all_transitions();
                curtain.opacity = 0;
                curtain.hide();
            }
        };
        if (actor && !actor.get_texture?.()?.get_width?.())
            ids.push([actor, actor.connect('first-frame', reveal)]);
        else
            reveal();
        // Fallback: never wait more than 3 s once the window exists.
        later(3000, () => { reveal(); return GLib.SOURCE_REMOVE; });
        ids.push([win, win.connect('unmanaged', () => {
            // Setup finished: black again (continues the finale), then wait
            // until the desktop renders smoothly.
            if (!curtain)
                return;
            curtain.show();
            curtain.opacity = 255;
            Main.layoutManager.uiGroup.set_child_above_sibling(curtain, null);
            settleThenReveal();
        })]);
    };

    ids.push([global.display, global.display.connect('window-created', (_d, win) => watchOobe(win))]);
    for (const actor of global.get_window_actors())
        watchOobe(actor.meta_window);
    later(SAFETY_SECONDS * 1000, () => {
        if (!oobeSeen || curtain?.visible)
            fadeOut();
        return GLib.SOURCE_REMOVE;
    });
    return cleanup;
}

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export function desktopReady() {
    const panel = global.dashToPanel?.panels?.find(p => p.panel === Main.panel);
    if (panel) {
        const [, y] = Main.panel.get_transformed_position();
        if (!Main.panel.has_allocation() || Main.panel.opacity === 0 ||
            !panel.monitor || y < panel.monitor.y + panel.monitor.height / 2 ||
            panel.getPosition() !== St.Side.BOTTOM) return false;
    }
    const ding = Main.extensionManager.lookup('ding@rastersoft.com');
    if (ding?.state === 1 && !global.get_window_actors().some(a =>
        a.mapped && /(?:ding|desktop)/i.test(`${a.meta_window?.get_wm_class() ?? ''} ${a.meta_window?.get_title() ?? ''}`))) return false;
    return true;
}

// Only presentation is delayed, after GNOME's verifier has accepted login.
// Native modal, authentication and completeDeactivate callbacks remain intact.
export function installTransitions(injections) {
    const shield = Main.screenShield;
    if (!shield) return () => {};
    const group = shield._lockDialogGroup;
    let inside = false, timer = 0, pending = null;
    const cancel = () => {
        if (timer) GLib.source_remove(timer);
        timer = 0;
        pending = null;
        group.remove_all_transitions();
        group.opacity = 255;
        group.translation_y = 0;
    };
    injections.overrideMethod(shield, 'activate', original => function(animate) {
        cancel();
        // Native zero-duration blank: no clock flash before display power-off.
        return original.call(this, Main.sessionMode.isGreeter ? animate : false);
    });
    injections.overrideMethod(shield, '_hideLockScreen', original => function(animate) {
        if (!inside) return original.call(this, animate);
        this._hideLockScreenComplete();
        this._showPointer();
    });
    injections.overrideMethod(shield, '_continueDeactivate', original => function(animate) {
        inside = !this._isGreeter && animate;
        try { return original.call(this, animate); } finally { inside = false; }
    });
    injections.overrideMethod(group, 'ease', original => function(params) {
        if (!inside || params.translation_y === undefined) return original.call(this, params);
        cancel();
        pending = params.onComplete;
        // The desktop already exists on unlock. Do not wait for DING or
        // panel opacity: those can only settle after native deactivation.
        original.call(group, {opacity: 0, duration: 140,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                const done = pending; pending = null;
                done?.();
                group.opacity = 255;
                group.translation_y = 0;
            }});
    });
    return () => {
        const done = pending;
        cancel();
        // Do not strand an already authenticated session if disabled mid-fade.
        done?.();
    };
}

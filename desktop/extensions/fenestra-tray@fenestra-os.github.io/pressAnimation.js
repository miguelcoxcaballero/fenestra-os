import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Windows 11 taskbar press feedback: the glyph shrinks while held and springs back.
function glyphFor(actor) {
    let inTaskbar = false;
    for (let p = actor; p; p = p.get_parent())
        if (p.has_style_class_name?.('dashtopanelMainPanel') || p.has_style_class_name?.('dashtopanelPanel')) inTaskbar = true;
    if (!inTaskbar) return null;
    for (let a = actor; a; a = a.get_parent()) {
        const d = a._delegate;
        if (d?.icon?._iconBin) return d.icon._iconBin;            // Dash to Panel app icons
        if (a.menuButtonWidget?._icon) return a.menuButtonWidget._icon; // ArcMenu Start
    }
    return null;
}
export function installPressAnimation() {
    const ids = [];
    let pressed = null, poll = 0;
    const animate = (icon, scale, ms, mode) => {
        icon.set_pivot_point(0.5, 0.5);
        icon.ease({scale_x: scale, scale_y: scale, duration: St.Settings.get().enableAnimations ? ms : 0, mode});
    };
    const release = () => {
        if (poll) GLib.source_remove(poll);
        poll = 0;
        if (pressed) animate(pressed, 1, 180, Clutter.AnimationMode.EASE_OUT_BACK);
        pressed = null;
    };
    // Start (ArcMenu) opens on press and grabs input, so its release event never
    // reaches the stage; watch the real button state instead.
    const watchRelease = () => {
        poll = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 30, () => {
            const [, , mods] = global.get_pointer();
            const held = mods & (Clutter.ModifierType.BUTTON1_MASK | Clutter.ModifierType.BUTTON2_MASK | Clutter.ModifierType.BUTTON3_MASK);
            if (held && pressed) return GLib.SOURCE_CONTINUE;
            poll = 0; release(); return GLib.SOURCE_REMOVE;
        });
    };
    // Listen on the stage: Dash to Panel may create its panels after this
    // extension is enabled, and recreates them when settings change.
    ids.push([global.stage, global.stage.connect('captured-event', (_a, event) => {
        const type = event.type();
        if (type === Clutter.EventType.BUTTON_PRESS || type === Clutter.EventType.TOUCH_BEGIN) {
            release();
            const [ex, ey] = event.get_coords();
            pressed = glyphFor(global.stage.get_actor_at_pos(Clutter.PickMode.REACTIVE, ex, ey));
            if (pressed) { animate(pressed, 0.82, 90, Clutter.AnimationMode.EASE_OUT_QUAD); if (type === Clutter.EventType.BUTTON_PRESS) watchRelease(); }
        } else if (pressed && (type === Clutter.EventType.BUTTON_RELEASE || type === Clutter.EventType.TOUCH_END ||
                   type === Clutter.EventType.TOUCH_CANCEL)) {
            release();
        }
        return Clutter.EVENT_PROPAGATE;
    })]);
    return () => {
        release();
        for (const [a, id] of ids) a.disconnect(id);
    };
}

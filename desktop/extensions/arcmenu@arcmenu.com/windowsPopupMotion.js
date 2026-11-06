import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {WindowsAcrylicEffect} from './windowsAcrylic.js';
import {acrylicMap} from './fenestraTheme.js';

/*
 * Windows 11 Start/Search motion + acrylic.
 * - Acrylic: live background blur under the menu surface (Shell.BlurEffect);
 *   the tint comes from the ArcMenu background colour.
 * - Motion: slides up from behind the taskbar, clipped at the taskbar edge,
 *   no opacity fade (a fade forces an offscreen pass every frame and breaks
 *   the background blur), so it runs at display refresh.
 */
const BLUR_RADIUS = 60;
const OPEN_MS = 200;
const CLOSE_MS = 120;
const SLIDE = 96;
const GAP = 12;

function surfaceOf(actor) {
    // BoxPointer -> bin -> .popup-menu-content
    return actor.bin?.get_child?.() ?? actor.get_first_child?.()?.get_first_child?.() ?? null;
}

// BoxPointer input muting: booleans up to GNOME 50, Clutter actions with .enabled from 51.
function setMuted(actor, muted) {
    for (const key of ['_muteKeys', '_muteInput']) {
        const v = actor[key];
        if (v && typeof v === 'object' && 'enabled' in v)
            v.enabled = muted;
        else
            actor[key] = muted;
    }
}

export function installWindowsPopupMotion(actor) {
    const originalOpen = actor.open;
    const originalClose = actor.close;
    let clipId = 0;
    const scale = () => St.ThemeContext.get_for_stage(global.stage).scale_factor;

    const ensureBlur = () => {
        const surface = surfaceOf(actor);
        if (!surface || surface.get_effect('windows-acrylic'))
            return;
        const blur = new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, brightness: 1.0});
        blur.radius = BLUR_RADIUS * scale();
        surface.add_effect_with_name('windows-acrylic', blur);
        surface.add_effect_with_name('windows-acrylic-luminosity', new WindowsAcrylicEffect());
    };

    const stopClip = () => {
        if (clipId)
            actor.disconnect(clipId);
        clipId = 0;
        actor.remove_clip();
    };
    // Only the part above the taskbar edge is visible while sliding.
    const startClip = () => {
        stopClip();
        const gap = GAP * scale();
        const update = () => {
            const visible = Math.max(0, actor.height + gap - actor.translation_y);
            actor.set_clip(-200, -200, actor.width + 400, visible + 200);
        };
        clipId = actor.connect('notify::translation-y', update);
        update();
    };
    const reset = () => {
        stopClip();
        actor.translation_x = 0;
        actor.translation_y = 0;
        actor.scale_x = 1;
        actor.scale_y = 1;
        actor.opacity = 255;
    };
    const duration = (animate, ms) => animate && St.Settings.get().enableAnimations ? ms : 0;

    actor.open = function (animate, onComplete) {
        ensureBlur();
        // Light mode: high base luminance (Windows light acrylic), dark: low.
        surfaceOf(this)?.get_effect('windows-acrylic-luminosity')?.setMap(...acrylicMap());
        // The background blur/luminosity must read the real screen: no
        // offscreen redirect (BoxPointer forces one for fades we don't use).
        this.offscreen_redirect = 0;
        const dim = this.get_effect('dim');
        if (dim)
            dim.enabled = false;
        this.remove_all_transitions();
        reset();
        const ms = duration(animate, OPEN_MS);
        setMuted(this, false);
        if (ms) {
            this.translation_y = SLIDE * scale();
            startClip();
        }
        this.show();
        if (!ms) {
            onComplete?.();
            return;
        }
        this.ease({
            translation_y: 0,
            duration: ms,
            mode: Clutter.AnimationMode.EASE_OUT_QUINT,
            onComplete: () => {
                reset();
                onComplete?.();
            },
        });
    };

    actor.close = function (animate, onComplete) {
        if (!this.visible)
            return;
        this.remove_all_transitions();
        setMuted(this, true);
        const ms = duration(animate, CLOSE_MS);
        if (!ms) {
            this.hide();
            reset();
            onComplete?.();
            return;
        }
        startClip();
        this.ease({
            translation_y: SLIDE * scale(),
            duration: ms,
            mode: Clutter.AnimationMode.EASE_IN_QUAD,
            onComplete: () => {
                this.hide();
                reset();
                onComplete?.();
            },
        });
    };

    return () => {
        actor.remove_all_transitions();
        reset();
        surfaceOf(actor)?.remove_effect_by_name('windows-acrylic-luminosity');
        surfaceOf(actor)?.remove_effect_by_name('windows-acrylic');
        actor.open = originalOpen;
        actor.close = originalClose;
    };
}

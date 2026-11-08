/*
    SPDX-License-Identifier: GPL-3.0-or-later

    Fenestra window motion: the Windows 11 (24H2, build 26100) DWM window transitions.

    Values come from Windows itself (tests/window-motion/README.md): uDWM.dll maps each transition
    to a storyboard of the theme's animation map (aero.msstyles, resource AMAP) — open 100,
    close 101, minimize 94, restore from minimized 95, maximize / restore from maximized / snap 104 —
    and the storyboard holds the transforms (scale, translate, opacity), their delays, durations
    and cubic-Bézier timing functions. design/motion.json "window" lists them.

    Only app windows and dialogs move: Fenestra Shell's own surfaces (layer-shell, scope "dock" or
    "fenestra-*"), notifications, OSDs, menus and tooltips have their own Windows motion in the shell.

    KWin's scripted effects only know Qt's easing types, and Windows uses cubic Béziers. A curve is
    therefore played as a chain of short linear pieces (knots every ~8 ms, closer where the curve
    bends): Scale/Opacity pieces multiply and Translation pieces add (AnimationEffect), a piece
    waits at its source value until its delay is over (waitAtSource) and stays at its target once
    done (set()), so the product follows the Bézier through every knot. A plain animate() "end" mark
    of the same length removes the pieces on the frame the motion ends.
*/

"use strict";

// Durations and delays in ms, curves as CSS cubic-bezier(x1, y1, x2, y2) (AMAP timing functions).
const MOTION = {
    // Storyboard 100: scale 0.8 -> 1 about the centre in 250 ms on timing function 71 (0, 0, 0, 1),
    // opacity 0 -> 1 linear in the first 83 ms.
    open: {
        duration: 250,
        origin: [0.5, 0.5],
        scale: { from: 0.8, curve: [0, 0, 0, 1] },
        opacity: { from: 0, duration: 83, curve: [0, 0, 1, 1] },
    },
    // Storyboard 101: scale 1 -> 0.95 about the centre in 175 ms on timing function 72 (1, 1, 0, 1),
    // opacity 1 -> 0 linear from 25 to 175 ms.
    close: {
        duration: 175,
        origin: [0.5, 0.5],
        scale: { to: 0.95, curve: [1, 1, 0, 1] },
        opacity: { to: 0, delay: 25, duration: 150, curve: [0, 0, 1, 1] },
    },
    // Storyboard 94: scale 1 -> 0 about the top-left corner while that corner moves to the
    // taskbar button, 167 ms on timing function 73 (1, 0, 1, 1); no opacity change.
    minimize: { duration: 167, curve: [1, 0, 1, 1] },
    // Storyboard 95: the reverse, 175 ms on timing function 74 (0, 0, 0, 1).
    restore: { duration: 175, curve: [0, 0, 0, 1] },
    // Storyboard 104: scale and translate from the old frame to the new one, 300 ms on timing
    // function 85 (0.8, 0, 0, 1); no cross-fade.
    maximize: { duration: 300, curve: [0.8, 0, 0, 1] },
};

// kwinrc [Effect-fenestra-window-motion] Debug=true: one line per motion in KWin's log.
const DEBUG = effect.readConfig("Debug", false);

const STEP_MS = 8; // one knot per half frame at 60 Hz

function bezier(c) {
    const [x1, y1, x2, y2] = c;
    const bx = (s) => 3 * (1 - s) * (1 - s) * s * x1 + 3 * (1 - s) * s * s * x2 + s * s * s;
    const by = (s) => 3 * (1 - s) * (1 - s) * s * y1 + 3 * (1 - s) * s * s * y2 + s * s * s;
    const at = (p) => {
        if (p <= 0) return 0;
        if (p >= 1) return 1;
        let lo = 0, hi = 1;
        for (let i = 0; i < 30; ++i) {
            const s = (lo + hi) / 2;
            if (bx(s) < p) lo = s; else hi = s;
        }
        return by((lo + hi) / 2);
    };
    return { at, bx, by };
}

// Knot times (0..1) for a curve over `ms`: one every STEP_MS, then halved wherever the straight
// line between two knots strays from the curve by more than TOLERANCE of the full change (the
// Fluent curves are steep: timing function 73 covers its last 35 % in the last 6 % of the time),
// down to whole milliseconds (KWin's animation times are integers).
const TOLERANCE = 0.001;
function knots(curve, ms) {
    const b = bezier(curve);
    const n = Math.max(1, Math.round(ms / STEP_MS));
    const ts = [];
    for (let i = 0; i <= n; ++i) ts.push(Math.round((i / n) * ms));
    const out = [ts[0]];
    const split = (t0, t1) => {
        const tm = Math.round((t0 + t1) / 2);
        if (tm > t0 && tm < t1) {
            const mid = (b.at(t0 / ms) + b.at(t1 / ms)) / 2;
            if (Math.abs(b.at(tm / ms) - mid) > TOLERANCE) {
                split(t0, tm);
                split(tm, t1);
                return;
            }
        }
        out.push(t1);
    };
    for (let i = 0; i + 1 < ts.length; ++i) split(ts[i], ts[i + 1]);
    return out.map((t) => ({ t: t / ms, v: b.at(t / ms) }));
}

// Pieces for one attribute: value(p) = from + (to - from) * curve(p), multiplicative (Scale, Size,
// Opacity) or additive (Translation), all components share the curve.
function pieces(window, type, from, to, curve, ms, delay, multiplicative) {
    const ks = knots(curve, ms);
    const val = (k) => from.map((f, i) => f + (to[i] - f) * k.v);
    const ids = [];
    for (let i = 0; i + 1 < ks.length; ++i) {
        const a = val(ks[i]), b = val(ks[i + 1]);
        let pf, pt;
        if (multiplicative) {
            // First piece is absolute, the next ones are ratios on top of it.
            if (i === 0) {
                pf = a; pt = b;
            } else {
                pf = a.map(() => 1);
                pt = b.map((x, j) => (a[j] === 0 ? 1 : x / a[j]));
            }
        } else {
            pf = i === 0 ? a : a.map(() => 0);
            pt = i === 0 ? b : b.map((x, j) => x - a[j]);
        }
        const fv = pf.length === 1 ? pf[0] : { value1: pf[0], value2: pf[1] };
        const tv = pt.length === 1 ? pt[0] : { value1: pt[0], value2: pt[1] };
        const start = Math.round(delay + ks[i].t * ms);
        const anim = { type: type, to: tv, targetAnchor: Effect.Left | Effect.Top, sourceAnchor: Effect.Left | Effect.Top };
        // A source value makes the piece "wait at source", but its timeline then already runs
        // during the delay (the piece would play at once). Delayed pieces start from the identity
        // (1 for Scale/Opacity, 0 for Translation), which is KWin's default source: leave it out.
        // Only the first piece of a curve has another source, and it starts with the motion.
        if (start === 0) anim.from = fv;
        const id = set({
            window: window,
            duration: Math.max(1, Math.round((ks[i + 1].t - ks[i].t) * ms)),
            delay: start,
            curve: QEasingCurve.Linear,
            keepAlive: true,
            // Scale anchored at the window's top-left: no per-piece centring (it would not add up
            // across multiplied pieces); the Translation pieces place the picture exactly.
            animations: [anim],
        });
        ids.push(...(Array.isArray(id) ? id : [id]));
    }
    return ids;
}

const SHELL_CLASSES = ["fenestra-shell org.fenestra.Shell", "fenestra-shell fenestra-shell"];

class FenestraWindowMotion {
    constructor() {
        this.motions = new Map(); // window -> { kind, ids, end, done, endsAt }
        effect.animationEnded.connect(this.onAnimationEnded.bind(this));
        effects.windowAdded.connect(this.onWindowAdded.bind(this));
        effects.windowClosed.connect(this.onWindowClosed.bind(this));
        effects.windowDataChanged.connect(this.onWindowDataChanged.bind(this));
        effects.windowActivated.connect(() => this.sweep());
        effects.mouseChanged.connect(() => this.sweep());
        for (const w of effects.stackingOrder) this.manage(w);
    }

    static isAppWindow(w) {
        if (SHELL_CLASSES.includes(w.windowClass)) return w.hasDecoration; // its dialogs only
        if (w.lockScreen || w.outline || w.popupWindow || !w.managed) return false;
        if (w.desktopWindow || w.dock || w.splash || w.toolbar || w.menu || w.notification || w.criticalNotification
            || w.onScreenDisplay || w.tooltip || w.dropdownMenu || w.popupMenu || w.comboBox || w.dndIcon) return false;
        return w.normalWindow || w.dialog;
    }

    manage(w) {
        w.minimizedChanged.connect(() => (w.minimized ? this.onMinimized(w) : this.onUnminimized(w)));
        w.windowMaximizedStateAboutToChange.connect(() => this.onMaximizeAboutToChange(w));
        w.windowMaximizedStateChanged.connect(() => this.onMaximizeChanged(w));
    }

    // Ends the motions that are over (see onAnimationEnded).
    sweep() {
        if (!this.pending) return;
        this.pending = false;
        for (const [w, m] of Array.from(this.motions)) {
            if (m.done) this.stop(w);
            else this.pending = true;
        }
    }

    stop(w) {
        const m = this.motions.get(w);
        if (!m) return;
        this.motions.delete(w);
        // Roles first: a closed window is gone as soon as its last animation is.
        w.setData(Effect.WindowForceBlurRole, null);
        w.setData(Effect.WindowForceBackgroundContrastRole, null);
        cancel(m.ids.concat([m.end]));
    }

    start(w, kind, ms, build) {
        // The new pieces go on before the old ones come off: a closed window would be released
        // the moment it has no animation left.
        const old = this.motions.get(w);
        w.setData(Effect.WindowForceBlurRole, true);
        w.setData(Effect.WindowForceBackgroundContrastRole, true);
        const ids = build();
        // End mark: a no-op that is not kept, so animationEnded fires when the motion is over.
        const end = animate({ window: w, duration: ms, keepAlive: true, animations: [{ type: Effect.Opacity, from: 1, to: 1 }] });
        if (old) cancel(old.ids.concat([old.end]));
        this.motions.set(w, { kind, ids, end: Array.isArray(end) ? end[0] : end, done: false, endsAt: Date.now() + ms });
        this.pending = true;
        if (DEBUG) this.t0 = Date.now();
        if (DEBUG) console.warn("fenestra-window-motion", kind, w.windowClass, ms + " ms", ids.length + " pieces");
    }

    // The only animation of this effect that is not kept is a motion's end mark (the id does not
    // reach the script: quint64), so any end for a window in motion is that motion's end.
    onAnimationEnded(w, id) {
        const m = this.motions.get(w);
        if (m && Date.now() < m.endsAt - 5) return; // the X11 cross-fade, not the end mark
        if (DEBUG) console.warn("fenestra-window-motion ended", Date.now() - this.t0, m ? m.kind : "-");
        // Removing animations from inside this signal crashes KWin (it is emitted while
        // AnimationEffect walks its list): the pieces (all at their final, neutral values now)
        // are removed at the next pointer motion or window event.
        if (m) m.done = true;
    }

    onWindowDataChanged(w, role) {
        // Another effect took the window (e.g. the Overview): let it.
        if ((role === Effect.WindowAddedGrabRole || role === Effect.WindowClosedGrabRole) && effect.isGrabbed(w, role)) {
            const m = this.motions.get(w);
            if (m && (m.kind === "open" || m.kind === "close")) this.stop(w);
        }
    }

    onWindowAdded(w) {
        this.sweep();
        this.manage(w);
        if (effects.hasActiveFullScreenEffect || !FenestraWindowMotion.isAppWindow(w) || !w.visible) return;
        if (effect.isGrabbed(w, Effect.WindowAddedGrabRole)) return;
        const o = MOTION.open;
        const g = w.geometry, from = FenestraWindowMotion.scaled(g, o.scale.from, o.origin[0], o.origin[1]);
        this.start(w, "open", o.duration, () => [
            ...this.morph(w, g, from, g, o.scale.curve, o.duration),
            ...pieces(w, Effect.Opacity, [o.opacity.from], [1], o.opacity.curve, o.opacity.duration || o.duration, o.opacity.delay || 0, true),
        ]);
    }

    onWindowClosed(w) {
        if (effects.hasActiveFullScreenEffect || !FenestraWindowMotion.isAppWindow(w)
            || !w.visible || w.skipsCloseAnimation || effect.isGrabbed(w, Effect.WindowClosedGrabRole)) {
            this.stop(w);
            this.sweep();
            return;
        }
        const c = MOTION.close;
        const g = w.geometry, to = FenestraWindowMotion.scaled(g, c.scale.to, c.origin[0], c.origin[1]);
        this.start(w, "close", c.duration, () => [
            ...this.morph(w, g, g, to, c.scale.curve, c.duration),
            ...pieces(w, Effect.Opacity, [1], [c.opacity.to], c.opacity.curve, c.opacity.duration || c.duration, c.opacity.delay || 0, true),
        ]);
        this.sweep();
    }

    // The point the window shrinks into: the centre of its taskbar button (Fenestra's taskbar sends
    // org_kde_plasma_window.set_minimized_geometry), or the bottom centre of the screen.
    static target(w) {
        const r = w.iconGeometry;
        if (r.width > 0 && r.height > 0) return { x: r.x + r.width / 2, y: r.y + r.height / 2, width: 0, height: 0 };
        const g = w.geometry, a = w.screen ? w.screen.geometry : effects.virtualScreenGeometry;
        return { x: g.x + g.width / 2, y: a.y + a.height - 24, width: 0, height: 0 };
    }

    onMinimized(w) {
        if (effects.hasActiveFullScreenEffect || !FenestraWindowMotion.isAppWindow(w)) return;
        const m = MOTION.minimize, g = w.geometry, t = FenestraWindowMotion.target(w);
        if (DEBUG) console.warn("fenestra-window-motion target", JSON.stringify(w.iconGeometry), JSON.stringify(t));
        this.start(w, "minimize", m.duration, () => this.morph(w, g, g, t, m.curve, m.duration));
    }

    onUnminimized(w) {
        if (effects.hasActiveFullScreenEffect || !FenestraWindowMotion.isAppWindow(w)) return;
        const m = MOTION.restore, g = w.geometry, t = FenestraWindowMotion.target(w);
        this.start(w, "restore", m.duration, () => this.morph(w, g, t, g, m.curve, m.duration));
    }

    // The window (at rect `win`) drawn into rect a, then moving to rect b along `curve`: Scale
    // pieces (per axis, anchored top-left) and Translation pieces of the top-left corner. Both are
    // linear in the curve value, so they stay consistent between knots too.
    morph(w, win, a, b, curve, ms) {
        const sx = (r) => r.width / win.width, sy = (r) => r.height / win.height;
        return [
            ...pieces(w, Effect.Scale, [sx(a), sy(a)], [sx(b), sy(b)], curve, ms, 0, true),
            ...pieces(w, Effect.Translation, [a.x - win.x, a.y - win.y], [b.x - win.x, b.y - win.y], curve, ms, 0, false),
        ];
    }

    // `win` scaled by k about the point (ox, oy) (0..1 of the window: 0.5, 0.5 = centre).
    static scaled(win, k, ox, oy) {
        return { x: win.x + (1 - k) * win.width * ox, y: win.y + (1 - k) * win.height * oy, width: win.width * k, height: win.height * k };
    }

    onMaximizeAboutToChange(w) {
        if (!w.visible) return;
        w.fenestraOldGeometry = Object.assign({}, w.geometry);
        // X11 clients repaint at the new size a few frames after their frame has changed: until
        // then KWin only has the old picture, which the morph would squash. Show that old picture
        // instead (cross-fade from it) while the new one arrives. Wayland clients commit the new
        // size before the state changes, as Windows apps repaint in WM_SIZE: no cross-fade.
        if (w.x11Client) {
            if (w.fenestraCrossFade) cancel(w.fenestraCrossFade);
            w.fenestraCrossFade = animate({ window: w, duration: MOTION.maximize.duration, curve: QEasingCurve.OutCubic,
                                            animations: [{ type: Effect.CrossFadePrevious, from: 0, to: 1 }] });
        }
    }

    onMaximizeChanged(w) {
        const old = w.fenestraOldGeometry;
        delete w.fenestraOldGeometry;
        if (!w.visible || !old || effects.hasActiveFullScreenEffect || !FenestraWindowMotion.isAppWindow(w)) return;
        const m = MOTION.maximize, g = w.geometry;
        if (old.width === g.width && old.height === g.height && old.x === g.x && old.y === g.y) return;
        this.start(w, "maximize", m.duration, () => this.morph(w, g, old, g, m.curve, m.duration));
    }
}

new FenestraWindowMotion();

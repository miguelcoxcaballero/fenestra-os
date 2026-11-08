// SPDX-License-Identifier: GPL-3.0-or-later
// Unlocking as on Windows 11: the lock screen dissolves into the desktop. kscreenlocker's greeter
// quits once the user is authenticated and KWin unlocks; without an effect its surface is gone in
// one frame and the desktop appears at once. Here the closed greeter window stays on screen and
// fades out over the session (a 1.5 % zoom out with it), so the desktop shows through.
"use strict";

const DURATION = 350;   // ms

function onClosed(w) {
    // Only the greeter's windows. (A greeter that crashes while locked fades over the locked,
    // black scene: harmless, and its replacement is already on top.)
    if (!w.lockScreen) return;
    console.info("FENESTRA_UNLOCK fade", w.width, w.height);
    animate({
        window: w,
        duration: DURATION,
        animations: [
            { type: Effect.Opacity, from: 1.0, to: 0.0, curve: QEasingCurve.OutCubic },
            { type: Effect.Scale, from: 1.0, to: 1.015, curve: QEasingCurve.OutCubic },
        ],
    });
}

effects.windowClosed.connect(onClosed);

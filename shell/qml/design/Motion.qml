// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick
import Fenestra.Shell

// Popup motion of Windows 11, measured on reference-shots/motion/* (frames, fits and assumptions in
// design/motion.json). Every popup slides fully opaque (no fade, no stagger of its content):
//   taskbar  Start, Search, Quick settings: rise from fully hidden behind the taskbar's top edge
//            (travel = height + gap), cubic-bezier(0, 0, 0, 1), 250 ms (start 0.8 px, quick 3.4 px rms).
//   edge     Notification Center + calendar: in from fully off the right edge (travel = width +
//            margin), cubic-bezier(0.33, 0, 0.1, 1), 220 ms (4.3 px rms).
//   close    no frames: back the same way, cubic-bezier(0.7, 0, 1, 0.5), 167 ms (assumption: Fluent
//            accelerate at WinUI's "fast" duration).
// Popups without frames use the closest measured pattern (PopupMotion.qml says which).
QtObject {
    // Settings › Accessibility › Animation effects off, or the Saver power profile.
    readonly property bool reduced: ShellSettings.reduceMotion

    // Curves as easing.bezierCurve lists (x1, y1, x2, y2, 1, 1).
    readonly property var decelerate: [0, 0, 0, 1, 1, 1]            // Fluent decelerate-mid
    readonly property var decelerateEdge: [0.33, 0, 0.1, 1, 1, 1]   // Fluent decelerate-min
    readonly property var accelerate: [0.7, 0, 1, 0.5, 1, 1]        // Fluent accelerate-mid

    readonly property int taskbarOpen: 250
    readonly property int edgeOpen: 220
    readonly property int close: 167
    // Menus (WinUI MenuFlyout, assumption): reveal from half their height, fast fade in and out.
    readonly property real menuRatio: 0.5
    readonly property int menuOpen: 250
    readonly property int menuFade: 83
    // Hover previews and Snap layouts (assumption): fade.
    readonly property int fadeOpen: 167
    readonly property int fadeClose: 83
    // Start Pinned <-> All apps, Quick settings subpages (assumption: WinUI entrance, 40 px).
    readonly property int pageOffset: 40
    readonly property int pageOpen: 250
    readonly property int pageFade: 167
}

// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick
import Fenestra.Shell

QtObject {
    // Settings › Accessibility › Animation effects off, or the Saver power profile.
    readonly property bool reduced: ShellSettings.reduceMotion
    // Opening animations measured on the reference (reference-shots/motion/*/analysis.json; VM
    // screendumps every 17–38 ms, indicative): Quick settings rise 178 px from behind the taskbar,
    // Notification Center slides in 312 px from the right edge; both decelerate hard (about 60 %
    // of the way in the first third), as Fluent's "decelerate" curve.
    readonly property int quickOpen: Tokens.px("motion.quick.open", 250)
    readonly property int quickOffset: Tokens.px("motion.quick.offset", 178)
    readonly property int centerOpen: Tokens.px("motion.notifications.open", 260)
    readonly property int centerOffset: Tokens.px("motion.notifications.offset", 312)
    readonly property var decelerate: [0.1, 0.9, 0.2, 1, 1, 1]
}

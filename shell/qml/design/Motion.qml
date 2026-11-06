// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick
import Fenestra.Shell

QtObject {
    // Settings › Accessibility › Animation effects off, or the Saver power profile.
    readonly property bool reduced: ShellSettings.reduceMotion
}

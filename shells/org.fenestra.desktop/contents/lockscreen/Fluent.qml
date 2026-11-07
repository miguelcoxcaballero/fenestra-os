// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick

QtObject {
    // Segoe Fluent Icons / Segoe UI Variable come from the user's own Windows (font pack import);
    // without them the lock screen uses Fenestra's SVGs and the system sans.
    readonly property bool available: Qt.fontFamilies().indexOf("Segoe Fluent Icons") >= 0
    readonly property string text: Qt.fontFamilies().indexOf("Segoe UI Variable") >= 0 ? "Segoe UI Variable" : "sans-serif"
    // DirectWrite picks Segoe UI Variable's optical size from the size in points on the device;
    // at 150 % a px size p is p * 1.5 * 0.75 pt (Metrics.qml in the shell).
    function opsz(px) { return Math.max(8, Math.min(36, px * Screen.devicePixelRatio * 0.75)) }
}

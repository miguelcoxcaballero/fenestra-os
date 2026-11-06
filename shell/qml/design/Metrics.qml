// SPDX-License-Identifier: GPL-3.0-or-later
// Sizes of the GNOME layer (see docs/fenestra-shell/INVENTORY.md for the sources).
pragma Singleton
import QtQuick

QtObject {
    readonly property int taskbarHeight: 48        // dash-to-panel panel-sizes
    readonly property int taskButton: 44           // 40 px icon cell + appicon-margin 2 * 2
    readonly property int taskIcon: 24
    readonly property int flyoutGap: 12            // flyoutGap.js FLYOUT_GAP
    readonly property int flyoutEdge: 13           // flyoutGap.js FLYOUT_EDGE
    readonly property int flyoutRadius: 8          // stylesheet.css .popup-menu-content
    readonly property int controlRadius: 4         // buttons, menu items
    readonly property int menuItemHeight: 36
    readonly property int searchBoxWidth: 228      // .fenestra-taskbar-search-box
    readonly property int searchBoxHeight: 32
    readonly property string fontFamily: "Segoe UI Variable Text"  // fontconfig alias -> Selawik
    readonly property string assets: "file:///usr/share/fenestra/assets/"
}

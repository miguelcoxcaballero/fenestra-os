// SPDX-License-Identifier: GPL-3.0-or-later
// Taskbar search in its four modes (B06): hidden, icon, icon + "Search", search box.
import QtQuick
import Fenestra.Shell

Item {
    id: search
    property string mode: ShellSettings.searchMode
    // Search is open: the box is its entry (the text typed in the flyout shows here).
    property bool checked: false
    property string query: ""
    // Left edge of the box in this item (the Search flyout lines up with it).
    readonly property real boxX: (Metrics.taskPitch - Metrics.taskButton) / 2 + (mode === "box" ? Metrics.tok("search.box.offset", 1) : 0)
    property real dpr: 1   // the window's real scale (TaskButton.qml)
    signal clicked()
    visible: mode !== "hidden"
    // Cells of the taskbar.button.pitch row: the plate (or the box) with 2 px on each side.
    width: (mode === "box" ? Metrics.searchBoxWidth : mode === "iconLabel" ? row.implicitWidth + 22 : Metrics.taskButton)
           + Metrics.taskPitch - Metrics.taskButton
    height: Metrics.taskbarHeight
    Accessible.role: Accessible.Button
    Accessible.name: Strings.tr("Search")

    Rectangle {
        id: box
        readonly property bool boxMode: search.mode === "box"
        readonly property real px: 1 / search.dpr
        x: search.boxX
        // The icon modes' plate is the app buttons' (TaskButton.qml): 39.33 high from y = 4, white
        // over the acrylic (user-win11 160049: Search open and hovered, #15 fill, top 2 px brighter).
        y: boxMode ? (parent.height - height) / 2 : Metrics.tok("taskbar.plate.y", 4)
        width: parent.width - Metrics.taskPitch + Metrics.taskButton
        height: boxMode ? Metrics.searchBoxHeight : (Math.round(Metrics.taskButton * search.dpr) - 1.001) / search.dpr
        radius: boxMode ? height / 2 : Metrics.controlRadius
        readonly property bool lit: search.checked
        readonly property bool hot: mouse.containsMouse
        opacity: boxMode || lit || hot ? 1 : 0
        color: boxMode ? Metrics.themed(search.checked ? "search.box.open" : "search.box.fill")
               : mouse.pressed ? Metrics.themed("taskbar.plate.pressed")
               : hot && lit ? Metrics.themed("taskbar.plate.hover.lit") : Metrics.themed("taskbar.plate")
        border.width: boxMode ? 1 : lit ? Math.ceil(search.dpr) * px : 0
        border.color: boxMode ? Metrics.themed("search.box.border") : Metrics.themed("taskbar.plate.border")
        Item {
            visible: !box.boxMode
            width: parent.width; height: (Math.ceil(search.dpr) - 0.001) / search.dpr
            clip: true
            Rectangle { width: box.width; height: box.height; radius: box.radius; color: Metrics.themed("taskbar.plate.highlight") }
        }
        Behavior on opacity { enabled: !Motion.reduced && !box.boxMode; NumberAnimation { duration: 90 } }
    }
    Row {
        id: row
        anchors.verticalCenter: parent.verticalCenter
        x: search.mode === "icon" ? (parent.width - Metrics.taskIcon) / 2
           : search.boxX + (search.mode === "box" ? Metrics.tok("search.box.icon.x", 10) : 10)
        spacing: search.mode === "box" ? Metrics.tok("search.box.text.x", 37) - Metrics.tok("search.box.icon.x", 10) - 14 : 10
        Image {
            // In the box Windows' lens measures 14 x 14 (dark-100-01-taskbar.png 797..810 x 1049..1062).
            // In icon mode it is a 24 px app-sized icon (user-win11 163657: 36 device px at 150 %, x 1357-1391).
            width: search.mode === "box" ? 14 : search.mode === "icon" ? Metrics.taskIcon : 20; height: width
            anchors.verticalCenter: parent.verticalCenter
            sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
            // Windows' lens: in the box it is drawn in grey (ring #cbcdce..#d2d7da in dark-100-01-taskbar.png) (its translucent inside a
            // lighter grey, dark-100-12-quick) and in colour while Search is open (dark-100-10-search);
            // the icon modes always draw it in colour.
            readonly property string lens: ShellSettings.searchIcon !== "" ? ShellSettings.searchIcon : Metrics.assets + "search/search.svg"
            source: search.mode === "box" && !search.checked
                    ? "image://tint/" + (Theme.dark ? "d2d6d8" : "5f5f5f") + "/" + encodeURIComponent(lens)
                    : lens
            // In the box Windows draws the lens 1 px right of our 10 px inset, and its closed-state glyph
            // 1 px further right and down (dark-100-12-quick: 797..810 × 1049; open, dark-100-10-search: 796 × 1048).
            transform: Translate { x: search.mode !== "box" ? 0 : search.checked ? 1 : 2; y: search.mode === "box" && !search.checked ? 1 : 0 }
            scale: mouse.pressed ? 0.85 : 1
            Behavior on scale { NumberAnimation { duration: 110 } }
        }
        Text {
            visible: search.mode !== "icon"
            anchors.verticalCenter: parent.verticalCenter
            text: search.checked && search.mode === "box" ? search.query : Strings.tr("Search")
            font.family: Metrics.fontFamily
            font.pixelSize: Metrics.fontBody
            color: search.mode === "box" && !search.checked ? Metrics.themed("search.box.text") : Theme.text
        }
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: search.clicked() }
}

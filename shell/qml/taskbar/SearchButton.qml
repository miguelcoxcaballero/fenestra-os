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
        x: search.boxX; anchors.verticalCenter: parent.verticalCenter
        width: parent.width - Metrics.taskPitch + Metrics.taskButton
        height: search.mode === "box" ? Metrics.searchBoxHeight : Metrics.taskButton
        radius: search.mode === "box" ? height / 2 : Metrics.controlRadius
        readonly property bool lit: search.checked || mouse.containsMouse
        color: search.mode === "box" ? Metrics.themed(search.checked ? "search.box.open" : "search.box.fill")
               : !lit ? "transparent" : Metrics.themed(mouse.containsMouse ? "taskbar.plate.hover" : "taskbar.plate")
        border.width: search.mode === "box" || lit ? 1 : 0
        border.color: search.mode === "box" ? Metrics.themed("search.box.border") : Metrics.themed("taskbar.plate.border")
    }
    Row {
        id: row
        anchors.verticalCenter: parent.verticalCenter
        x: search.mode === "icon" ? (parent.width - 20) / 2
           : search.boxX + (search.mode === "box" ? Metrics.tok("search.box.icon.x", 10) : 10)
        spacing: search.mode === "box" ? Metrics.tok("search.box.text.x", 37) - Metrics.tok("search.box.icon.x", 10) - 16 : 10
        Image {
            width: 16 + (search.mode === "box" ? 0 : 4); height: width
            anchors.verticalCenter: parent.verticalCenter
            sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
            // Windows' lens: in the box it is drawn in the text colour (its translucent inside a
            // lighter grey, dark-100-12-quick) and in colour while Search is open (dark-100-10-search);
            // the icon modes always draw it in colour.
            readonly property string lens: ShellSettings.searchIcon !== "" ? ShellSettings.searchIcon : Metrics.assets + "search/search.svg"
            source: search.mode === "box" && !search.checked
                    ? "image://tint/" + Theme.text.toString().slice(1, 7) + "/" + encodeURIComponent(lens)
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

// SPDX-License-Identifier: GPL-3.0-or-later
// Taskbar search in its four modes (B06): hidden, icon, icon + "Search", search box.
import QtQuick
import Fenestra.Shell

Item {
    id: search
    property string mode: ShellSettings.searchMode
    signal clicked()
    visible: mode !== "hidden"
    width: mode === "box" ? Metrics.searchBoxWidth : mode === "iconLabel" ? row.implicitWidth + 22 : Metrics.taskButton
    height: Metrics.taskButton
    Accessible.role: Accessible.Button
    Accessible.name: Strings.tr("Search")

    Rectangle {
        anchors.centerIn: parent
        width: parent.width
        height: search.mode === "box" ? Metrics.searchBoxHeight : (search.mode === "iconLabel" ? 40 : parent.height)
        radius: search.mode === "box" ? height / 2 : Metrics.controlRadius
        color: search.mode === "box"
               ? (Theme.dark ? Qt.rgba(1, 1, 1, mouse.containsMouse ? 0.09 : 0.06) : Qt.rgba(1, 1, 1, mouse.containsMouse ? 0.85 : 0.7))
               : (mouse.containsMouse ? Theme.hover : "transparent")
        border.width: search.mode === "box" ? 1 : 0
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
    }
    Row {
        id: row
        anchors.verticalCenter: parent.verticalCenter
        x: search.mode === "icon" ? (parent.width - 20) / 2 : (search.mode === "box" ? 14 : 10)
        spacing: 10
        Image {
            width: 20; height: 20
            anchors.verticalCenter: parent.verticalCenter
            sourceSize: Qt.size(20 * Screen.devicePixelRatio, 20 * Screen.devicePixelRatio)
            source: ShellSettings.searchIcon !== "" ? ShellSettings.searchIcon : Metrics.assets + "search/search.svg"
            scale: mouse.pressed ? 0.85 : 1
            Behavior on scale { NumberAnimation { duration: 110 } }
        }
        Text {
            visible: search.mode !== "icon"
            anchors.verticalCenter: parent.verticalCenter
            text: Strings.tr("Search")
            font.family: Metrics.fontFamily
            font.pixelSize: 13
            color: search.mode === "box" ? (Theme.dark ? "#c5c5c5" : "#5c5c5c") : Theme.text
        }
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: search.clicked() }
}

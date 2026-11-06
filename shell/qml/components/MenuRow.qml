// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Fenestra.Shell

Rectangle {
    id: row
    property string text
    property string iconName
    property url iconSource
    signal triggered()

    width: Math.max(220, label.implicitWidth + 56)
    height: Metrics.menuItemHeight
    radius: Metrics.controlRadius
    color: mouse.pressed ? Theme.pressed : mouse.containsMouse ? Theme.hover : "transparent"
    Accessible.role: Accessible.MenuItem
    Accessible.name: text

    Image {
        id: icon
        x: 12; anchors.verticalCenter: parent.verticalCenter
        width: 16; height: 16
        sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
        source: row.iconSource.toString() !== "" ? row.iconSource : (row.iconName ? "image://icon/" + row.iconName : "")
        visible: source.toString() !== ""
    }
    Text {
        id: label
        x: 40; anchors.verticalCenter: parent.verticalCenter
        text: row.text
        color: Theme.text
        font.family: Metrics.fontFamily
        font.pixelSize: 14
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: row.triggered()
    }
}

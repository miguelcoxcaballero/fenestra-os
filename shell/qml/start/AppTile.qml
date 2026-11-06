// SPDX-License-Identifier: GPL-3.0-or-later
// Pinned tile (80 px wide, icon 32, 12 px label) and Grid view cell.
import QtQuick
import Fenestra.Shell

Item {
    id: tile
    property string storageId
    property string name
    property string icon
    property int tileWidth: 80
    signal activated()
    signal contextRequested(real x, real y)
    width: tileWidth + 8; height: 77
    Accessible.role: Accessible.Button
    Accessible.name: name
    Rectangle {
        x: 4; width: tile.tileWidth; height: 69
        radius: Metrics.controlRadius
        color: m.pressed ? Theme.pressed : m.containsMouse ? Theme.hover : "transparent"
    }
    Image {
        id: img
        x: 4 + (tile.tileWidth - 32) / 2; y: 8
        width: 32; height: 32
        sourceSize: Qt.size(32 * Screen.devicePixelRatio, 32 * Screen.devicePixelRatio)
        source: "image://icon/" + tile.icon
        scale: m.pressed ? 0.9 : 1
        Behavior on scale { NumberAnimation { duration: 110 } }
    }
    Text {
        x: 4; y: 46; width: tile.tileWidth
        horizontalAlignment: Text.AlignHCenter
        text: tile.name
        elide: Text.ElideRight
        color: Theme.text
        font.family: Metrics.fontFamily
        font.pixelSize: 12
    }
    MouseArea {
        id: m
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (e) => e.button === Qt.RightButton ? tile.contextRequested(e.x, e.y) : tile.activated()
    }
}

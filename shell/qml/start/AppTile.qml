// SPDX-License-Identifier: GPL-3.0-or-later
// Pinned tile and Grid view cell: a 96 × 84 cell (start.pinned.tile.*), 32 px icon 12 px from the
// top, 12 px label below it on up to two lines (design/tokens.json).
import QtQuick
import Fenestra.Shell

Item {
    id: tile
    property string storageId
    property string name
    property string icon
    property int tileWidth: Metrics.startTileWidth
    property int tileHeight: Metrics.startTileHeight
    signal activated()
    signal contextRequested(real x, real y)
    width: tileWidth; height: tileHeight
    Accessible.role: Accessible.Button
    Accessible.name: name
    Rectangle {
        anchors.fill: parent
        anchors.margins: 2
        radius: Metrics.controlRadius
        color: m.pressed ? Theme.pressed : m.containsMouse ? Metrics.themed("start.hover") : "transparent"
    }
    Image {
        id: img
        readonly property int size: Metrics.tok("start.pinned.icon", 32)
        x: Math.round((tile.width - size) / 2); y: Metrics.tok("start.pinned.icon.top", 12)
        width: size; height: size
        sourceSize: Qt.size(size * Screen.devicePixelRatio, size * Screen.devicePixelRatio)
        source: "image://icon/" + tile.icon
        scale: m.pressed ? 0.9 : 1
        Behavior on scale { NumberAnimation { duration: 110 } }
    }
    Text {
        x: 4; y: Metrics.tok("start.pinned.label.top", 48); width: tile.width - 8
        horizontalAlignment: Text.AlignHCenter
        text: tile.name
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
        lineHeightMode: Text.FixedHeight
        lineHeight: 16
        color: Theme.text
        font.family: Metrics.fontFamily
        font.pixelSize: Metrics.fontCaption
    }
    MouseArea {
        id: m
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (e) => e.button === Qt.RightButton ? tile.contextRequested(e.x, e.y) : tile.activated()
    }
}

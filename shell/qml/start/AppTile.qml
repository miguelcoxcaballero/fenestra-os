// SPDX-License-Identifier: GPL-3.0-or-later
// Pinned tile and Grid view cell (user-win11 160039 at 150 %): a 96 x 84 cell, 32 px icon 12 px
// from the top, 12 px label centred under it on up to two lines of 16 px, first baseline 60.67 px
// from the tile's top (start.pinned.* tokens).
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
        color: m.pressed ? Metrics.themed("popup.pressed") : m.containsMouse ? Metrics.themed("popup.hover") : "transparent"
    }
    Image {
        id: img
        readonly property int size: Metrics.tok("start.pinned.icon", 32)
        x: Math.round((tile.width - size) / 2); y: Metrics.tok("start.pinned.icon.top", 12)
        width: size; height: size
        sourceSize: Qt.size(size * 2, size * 2)
        source: "image://icon/" + tile.icon
        scale: m.pressed ? 0.9 : 1
        Behavior on scale { NumberAnimation { duration: 110 } }
    }
    Text {
        x: 2; width: tile.width - 4
        y: Metrics.num("start.pinned.label.baseline", 60.67) - baselineOffset
        horizontalAlignment: Text.AlignHCenter
        text: tile.name
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
        lineHeightMode: Text.FixedHeight
        lineHeight: 16
        color: Theme.text
        font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize)
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

// SPDX-License-Identifier: GPL-3.0-or-later
// Quick settings tile: 96 × 48 button (split with a 28 px chevron part when it has a subpage),
// 16 px glyph, two-line 12 px caption 8 px below; one grid cell is 96 px tall (quick.* tokens).
import QtQuick
import Fenestra.Shell

Item {
    id: tile
    property string label
    property string iconName
    property url iconSource
    property bool checked: false
    property bool hasPage: false
    signal toggled()
    signal pageRequested()
    width: Metrics.quickTileWidth
    height: Metrics.n("quick.tile.pitch.y", 96)
    Accessible.role: Accessible.CheckBox
    Accessible.name: label
    Accessible.checked: checked

    component Part: Rectangle {
        id: part
        property bool hovered: false
        property bool down: false
        property bool on: false
        height: Metrics.quickTileHeight
        radius: Metrics.controlRadius
        color: part.on ? (down ? Theme.accentPress : hovered ? Theme.accentHover : Theme.accentFill)
                            : (down ? Theme.pressed : hovered ? Qt.tint(Metrics.col("panel.control"), Theme.hover) : Metrics.col("panel.control"))
        border.width: part.on ? 0 : 1
        border.color: Metrics.col("panel.control.border")
        // Elevation: the bottom edge is a shade darker than the others.
        Rectangle { visible: !part.on; x: part.radius; width: parent.width - 2 * part.radius; y: parent.height - 1; height: 1
                    color: Metrics.col("panel.control.border.bottom") }
    }

    Part {
        id: main
        width: tile.hasPage ? parent.width - 28 : parent.width
        topRightRadius: tile.hasPage ? 0 : Metrics.controlRadius; bottomRightRadius: topRightRadius
        hovered: bm.containsMouse; down: bm.pressed; on: tile.checked
        Image {
            anchors.centerIn: parent; width: 16; height: 16
            sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
            source: {
                const t = tile.iconSource.toString() !== "" ? tile.iconSource.toString() : tile.iconName
                const onFill = tile.checked ? Theme.accentOn : Theme.text
                return (Theme.dark && !tile.checked) ? (tile.iconSource.toString() !== "" ? tile.iconSource : "image://icon/" + tile.iconName)
                                                     : "image://tint/" + onFill.toString().slice(1, 7) + "/" + encodeURIComponent(t)
            }
        }
        MouseArea { id: bm; anchors.fill: parent; hoverEnabled: true; onClicked: tile.toggled() }
    }
    Part {
        visible: tile.hasPage
        x: main.width; width: 28
        topLeftRadius: 0; bottomLeftRadius: 0
        hovered: cm.containsMouse; down: cm.pressed; on: tile.checked
        Rectangle { width: 1; height: 24; anchors.verticalCenter: parent.verticalCenter
                    color: tile.checked ? Qt.rgba(0, 0, 0, 0.2) : Metrics.col("panel.control.border") }
        SymbolicIcon { anchors.centerIn: parent; name: "go-next-symbolic"; size: 12 }
        MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; onClicked: tile.pageRequested() }
    }
    Text {
        y: Metrics.quickTileHeight + Metrics.n("quick.label.top", 8)
        width: parent.width; horizontalAlignment: Text.AlignHCenter
        text: tile.label; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
        lineHeight: Metrics.n("quick.label.line", 16); lineHeightMode: Text.FixedHeight
        color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Fenestra.Shell

Rectangle {
    id: row
    property string text
    property string iconName
    property url iconSource
    // Distance from the menu's outer edge to this row (border + padding): icon and text keep
    // their measured place from the outer edge (menu.icon.x, menu.text.x).
    property int inset: 0
    // Glyphs drawn on a 24 px grid (power/*.svg) need more than 16 px to fill 16 px.
    property int iconSize: 16
    signal triggered()

    implicitWidth: Metrics.menuTextX - inset + label.implicitWidth + Metrics.menuPaddingRight + 1 - inset
    width: implicitWidth
    height: Metrics.menuItemHeight
    color: "transparent"
    Accessible.role: Accessible.MenuItem
    Accessible.name: text

    Rectangle {
        // Hover plate 4 px inside the menu's border (the reference's focus ring at x5 of 296).
        x: Math.max(0, 5 - row.inset); width: parent.width - 2 * x; height: parent.height
        radius: Metrics.controlRadius
        color: mouse.pressed ? Theme.pressed : mouse.containsMouse ? Metrics.themed("menu.hover") : "transparent"
    }
    // Fenestra's own glyphs (assets) are white line art: tinted in light mode. Theme icons are not.
    SymbolicIcon {
        size: row.iconSize
        x: Metrics.menuIconX - row.inset - (row.iconSize - 16) / 2; anchors.verticalCenter: parent.verticalCenter
        visible: row.iconSource.toString() !== ""
        monochrome: true
        src: row.iconSource
    }
    Image {
        x: Metrics.menuIconX - row.inset; anchors.verticalCenter: parent.verticalCenter
        width: 16; height: 16
        sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
        visible: row.iconSource.toString() === "" && row.iconName !== ""
        source: row.iconName ? "image://icon/" + row.iconName : ""
    }
    Text {
        id: label
        x: Metrics.menuTextX - row.inset; anchors.verticalCenter: parent.verticalCenter
        text: row.text
        color: Theme.text
        font.family: Metrics.fontFamily
        font.pixelSize: Metrics.fontBody
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: row.triggered()
    }
}

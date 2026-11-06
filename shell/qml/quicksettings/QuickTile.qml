// SPDX-License-Identifier: GPL-3.0-or-later
// Quick settings tile (quickPanel.js): 104 px wide, 48 px button (split with a 28 px chevron when
// it has a subpage), caption 12 px below.
import QtQuick
import Fenestra.Shell

Column {
    id: tile
    property string label
    property string iconName
    property url iconSource
    property bool checked: false
    property bool hasPage: false
    signal toggled()
    signal pageRequested()
    width: 104; spacing: 6
    Accessible.role: Accessible.CheckBox
    Accessible.name: label
    Accessible.checked: checked
    Row {
        width: parent.width; height: 48
        Rectangle {
            width: tile.hasPage ? parent.width - 28 : parent.width; height: 48
            radius: Metrics.controlRadius
            topRightRadius: tile.hasPage ? 0 : Metrics.controlRadius; bottomRightRadius: topRightRadius
            color: tile.checked ? (bm.containsMouse ? Theme.accentHover : Theme.accentFill)
                                : (bm.containsMouse ? Qt.rgba(1, 1, 1, Theme.dark ? 0.09 : 0.6) : Qt.rgba(1, 1, 1, Theme.dark ? 0.06 : 0.7))
            border.color: tile.checked ? "transparent" : (Theme.dark ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.06))
            Image {
                anchors.centerIn: parent; width: 18; height: 18
                sourceSize: Qt.size(18 * Screen.devicePixelRatio, 18 * Screen.devicePixelRatio)
                source: {
                    const t = tile.iconSource.toString() !== "" ? tile.iconSource.toString() : tile.iconName
                    const onFill = tile.checked ? Theme.accentOn : Theme.text
                    return (Theme.dark && !tile.checked) ? (tile.iconSource.toString() !== "" ? tile.iconSource : "image://icon/" + tile.iconName)
                                                         : "image://tint/" + onFill.toString().slice(1, 7) + "/" + encodeURIComponent(t)
                }
            }
            MouseArea { id: bm; anchors.fill: parent; hoverEnabled: true; onClicked: tile.toggled() }
        }
        Rectangle {
            visible: tile.hasPage
            width: 28; height: 48
            topRightRadius: Metrics.controlRadius; bottomRightRadius: Metrics.controlRadius
            color: tile.checked ? (cm.containsMouse ? Theme.accentHover : Theme.accentFill)
                                : (cm.containsMouse ? Qt.rgba(1, 1, 1, Theme.dark ? 0.09 : 0.6) : Qt.rgba(1, 1, 1, Theme.dark ? 0.06 : 0.7))
            border.color: tile.checked ? "transparent" : (Theme.dark ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.06))
            Rectangle { width: 1; height: 24; anchors.verticalCenter: parent.verticalCenter; color: tile.checked ? Qt.rgba(0, 0, 0, 0.2) : Theme.separator }
            Text { anchors.centerIn: parent; text: "›"; font.pixelSize: 16; color: tile.checked ? Theme.accentOn : Theme.text }
            MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; onClicked: tile.pageRequested() }
        }
    }
    Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: tile.label; elide: Text.ElideRight
           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra Alt+Tab (W04): one row of thumbnails centred on the screen, each with the app icon and
// the window title above it, the current one outlined in the text colour; acrylic panel behind.
// Sizes: design/tokens.json "switcher.*" (placeholders until the reference measurements).
import QtQuick
import org.kde.kwin as KWin
import org.kde.kirigami as Kirigami

KWin.TabBoxSwitcher {
    id: tabBox
    readonly property bool dark: true
    readonly property int thumbHeight: 180
    readonly property int spacing: 12

    Instantiator {
        active: tabBox.visible
        delegate: Window {
            id: win
            visible: true
            color: "transparent"
            flags: Qt.ToolTip | Qt.FramelessWindowHint
            width: Math.min(tabBox.screenGeometry.width - 80, row.contentWidth + 2 * 16)
            height: tabBox.thumbHeight + 56 + 2 * 16
            x: tabBox.screenGeometry.x + (tabBox.screenGeometry.width - width) / 2
            y: tabBox.screenGeometry.y + (tabBox.screenGeometry.height - height) / 2

            Rectangle {
                anchors.fill: parent
                radius: 8
                color: Qt.rgba(32 / 255, 32 / 255, 32 / 255, 0.92)
                border.color: Qt.rgba(1, 1, 1, 0.10)
            }
            ListView {
                id: row
                anchors { fill: parent; margins: 16 }
                orientation: ListView.Horizontal
                spacing: tabBox.spacing
                model: tabBox.model
                currentIndex: tabBox.currentIndex
                highlightMoveDuration: 0
                keyNavigationWraps: true
                clip: true
                onCurrentIndexChanged: tabBox.currentIndex = currentIndex
                delegate: MouseArea {
                    id: cell
                    required property int index
                    required property var model
                    readonly property real ratio: tabBox.screenGeometry.width / tabBox.screenGeometry.height
                    width: Math.round(tabBox.thumbHeight * ratio * 0.8)
                    height: row.height
                    hoverEnabled: true
                    onClicked: tabBox.model.activate(index)
                    Accessible.name: model.caption
                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: cell.ListView.isCurrentItem ? Qt.rgba(1, 1, 1, 0.08) : cell.containsMouse ? Qt.rgba(1, 1, 1, 0.05) : "transparent"
                        border.width: cell.ListView.isCurrentItem ? 2 : 0
                        border.color: "white"
                    }
                    Row {
                        x: 8; y: 8; spacing: 8; width: parent.width - 16
                        Kirigami.Icon { width: 16; height: 16; source: cell.model.icon }
                        Text { width: parent.width - 24; elide: Text.ElideRight; text: cell.model.caption
                               color: "white"; font.pixelSize: 12 }
                    }
                    Item {
                        x: 8; y: 32; width: parent.width - 16; height: parent.height - 40
                        KWin.WindowThumbnail { anchors.fill: parent; wId: cell.model.windowId }
                    }
                }
            }
        }
    }
}

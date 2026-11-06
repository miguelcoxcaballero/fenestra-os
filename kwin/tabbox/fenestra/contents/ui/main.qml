// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra Alt+Tab (W04), as dark-100-25-alt-tab / light-100-25-alt-tab: one row of window cards
// centred on the screen. A card is a 39 px strip with the app icon and the window title over a
// 244 px tall thumbnail (width from the window's aspect); cards 27 px apart and 58 px from the
// panel edge; the current one ringed 11 px outside by a 4 px accent line (2 px dark inside it).
// Panel #202020 / #f3f3f3 with a 1 px #464646 / #c8c8c8 outline, radius 8. Values in px at scale
// 1 (design/tokens.json switcher.*: KWin's QML engine does not load the shell's token module).
import QtQuick
import org.kde.kwin as KWin
import org.kde.kirigami as Kirigami

KWin.TabBoxSwitcher {
    id: tabBox
    readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property int thumbHeight: 244      // switcher.thumbnail.height (243) + its 1 px top edge
    readonly property int titleHeight: 39       // switcher.title.height
    readonly property int padding: 58           // panel edge to card content
    readonly property int spacing: 27           // between card contents
    readonly property int ring: 4
    readonly property int ringGap: 7            // 2 px dark line + 5 px panel colour between ring and content
    readonly property color accent: dark ? "#4cc2ff" : "#0067c0"

    Instantiator {
        active: tabBox.visible
        delegate: Window {
            id: win
            visible: true
            color: "transparent"
            flags: Qt.ToolTip | Qt.FramelessWindowHint
            width: Math.min(tabBox.screenGeometry.width - 80, row.contentWidth + 2 * tabBox.padding)
            height: tabBox.titleHeight + tabBox.thumbHeight + 2 * tabBox.padding
            x: tabBox.screenGeometry.x + Math.round((tabBox.screenGeometry.width - width) / 2)
            y: tabBox.screenGeometry.y + Math.round((tabBox.screenGeometry.height - height) / 2)

            Rectangle {
                anchors.fill: parent
                radius: 8
                color: tabBox.dark ? "#202020" : "#f3f3f3"
                border.color: tabBox.dark ? "#464646" : "#c8c8c8"
            }
            ListView {
                id: row
                anchors { fill: parent; margins: tabBox.padding }
                orientation: ListView.Horizontal
                spacing: tabBox.spacing
                model: tabBox.model
                currentIndex: tabBox.currentIndex
                highlightMoveDuration: 0
                keyNavigationWraps: true
                // the ring sits outside the cards: do not clip it
                clip: false
                onCurrentIndexChanged: tabBox.currentIndex = currentIndex
                delegate: MouseArea {
                    id: cell
                    required property int index
                    required property var model
                    readonly property real aspect: thumb.sourceSize.height > 0 ? thumb.sourceSize.width / thumb.sourceSize.height
                                                                               : tabBox.screenGeometry.width / tabBox.screenGeometry.height
                    width: Math.round(Math.max(200, Math.min(560, tabBox.thumbHeight * aspect)))
                    height: row.height
                    hoverEnabled: true
                    onClicked: tabBox.model.activate(index)
                    Accessible.name: model.caption
                    // Selection ring (and a lighter one on hover).
                    Rectangle {
                        visible: cell.ListView.isCurrentItem || cell.containsMouse
                        x: -tabBox.ring - tabBox.ringGap; y: x
                        width: parent.width - 2 * x; height: parent.height - 2 * x
                        radius: 10
                        color: "transparent"
                        border.width: tabBox.ring
                        border.color: cell.ListView.isCurrentItem ? tabBox.accent : (tabBox.dark ? Qt.rgba(1, 1, 1, 0.3) : Qt.rgba(0, 0, 0, 0.3))
                        Rectangle {
                            x: tabBox.ring; y: x; width: parent.width - 2 * x; height: parent.height - 2 * x
                            radius: 6; color: "transparent"; border.width: 2
                            border.color: tabBox.dark ? "#0a0a0a" : "#fbfbfb"
                        }
                    }
                    Rectangle {
                        width: parent.width; height: tabBox.titleHeight
                        topLeftRadius: 4; topRightRadius: 4
                        color: tabBox.dark ? "#0b0b0b" : "#f6f6f6"
                        Kirigami.Icon { x: 13; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; source: cell.model.icon }
                        Text { x: 36; width: parent.width - 48; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                               text: cell.model.caption; color: tabBox.dark ? "white" : "#1a1a1a"
                               font.family: "Segoe UI Variable Text"; font.pixelSize: 14 }
                    }
                    Item {
                        y: tabBox.titleHeight; width: parent.width; height: tabBox.thumbHeight
                        clip: true
                        KWin.WindowThumbnail { id: thumb; anchors.fill: parent; wId: cell.model.windowId }
                    }
                }
            }
        }
    }
}

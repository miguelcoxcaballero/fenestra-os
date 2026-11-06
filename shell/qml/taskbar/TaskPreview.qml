// SPDX-License-Identifier: GPL-3.0-or-later
// Hover preview of a taskbar group (B03): one card per window (preview.* in design/tokens.json):
// icon and title on top, the window below; click activates, × closes.
// Live thumbnails need KWin's screencast (PipeWire, OpenGL): see docs/fenestra-shell/FEASIBILITY.md;
// until then the window's place shows the app icon.
import QtQuick
import Fenestra.Shell

Flyout {
    id: preview
    property var windows: []
    property string icon      // the group's icon (the windows of one app)
    property bool keepOpen: hoverArea.containsMouse
    takesFocus: false
    padding: 0
    background.color: Metrics.themed("menu.fill")
    background.border.color: Metrics.themed("preview.border")
    readonly property int thumbWidth: Metrics.tok("preview.thumb.width", 182)
    readonly property int thumbHeight: Metrics.tok("preview.thumb.height", 110)
    Row {
        id: list
        Repeater {
            model: preview.windows
            delegate: Item {
                id: card
                required property var modelData
                // 9 px around the window, 41 px title row (dark-100-03-preview.png).
                width: preview.thumbWidth + 19; height: preview.thumbHeight + 50
                Rectangle {
                    anchors.fill: parent; anchors.margins: 4
                    radius: Metrics.controlRadius
                    color: rowMouse.containsMouse ? Metrics.themed("menu.hover") : "transparent"
                }
                Image {
                    x: 9; y: 13; width: 16; height: 16
                    sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
                    source: preview.icon ? "image://icon/" + preview.icon : ""
                }
                Text {
                    x: 34; width: parent.width - 34 - 36; y: 13; height: 16
                    verticalAlignment: Text.AlignVCenter
                    text: card.modelData.title
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Metrics.fontFamily
                    font.pixelSize: Metrics.fontCaption
                }
                Rectangle {
                    x: 9; y: 41; width: preview.thumbWidth; height: preview.thumbHeight
                    color: Metrics.themed("preview.window")
                    Image {
                        anchors.centerIn: parent; width: 32; height: 32
                        sourceSize: Qt.size(32 * Screen.devicePixelRatio, 32 * Screen.devicePixelRatio)
                        source: preview.icon ? "image://icon/" + preview.icon : ""
                    }
                }
                MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true
                    onClicked: { WindowsModel.activate(card.modelData.row); preview.close() } }
                Rectangle {
                    anchors { right: parent.right; rightMargin: 6; top: parent.top; topMargin: 6 }
                    width: 28; height: 28; radius: Metrics.controlRadius
                    color: closeMouse.containsMouse ? "#c42b1c" : "transparent"
                    visible: rowMouse.containsMouse || closeMouse.containsMouse
                    SymbolicIcon { anchors.centerIn: parent; size: 16; src: Metrics.assets + "menu-icons/win11-menu-cancel.svg" }
                    MouseArea { id: closeMouse; anchors.fill: parent; hoverEnabled: true
                        onClicked: WindowsModel.close(card.modelData.row) }
                }
            }
        }
    }
    MouseArea { id: hoverArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; z: -1 }
}

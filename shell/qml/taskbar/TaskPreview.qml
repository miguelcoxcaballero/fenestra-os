// SPDX-License-Identifier: GPL-3.0-or-later
// Hover preview of a taskbar group (B03): the group's windows; click activates, × closes.
// Live thumbnails need KWin's screencast (PipeWire, OpenGL): see docs/fenestra-shell/FEASIBILITY.md.
import QtQuick
import Fenestra.Shell

Flyout {
    id: preview
    property var windows: []
    property bool keepOpen: hoverArea.containsMouse
    takesFocus: false
    Column {
        id: list
        spacing: 2
        Repeater {
            model: preview.windows
            delegate: Rectangle {
                required property var modelData
                width: 260; height: 40
                radius: Metrics.controlRadius
                color: rowMouse.containsMouse ? Theme.hover : modelData.active ? Theme.pressed : "transparent"
                Text {
                    x: 12; width: parent.width - 52
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.title
                    elide: Text.ElideRight
                    color: Theme.text
                    font.family: Metrics.fontFamily
                    font.pixelSize: 13
                }
                MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true
                    onClicked: { WindowsModel.activate(modelData.row); preview.close() } }
                Rectangle {
                    anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                    width: 32; height: 32; radius: Metrics.controlRadius
                    color: closeMouse.containsMouse ? "#c42b1c" : "transparent"
                    visible: rowMouse.containsMouse || closeMouse.containsMouse
                    Text { anchors.centerIn: parent; text: "✕"; color: closeMouse.containsMouse ? "white" : Theme.text; font.pixelSize: 12 }
                    MouseArea { id: closeMouse; anchors.fill: parent; hoverEnabled: true
                        onClicked: WindowsModel.close(modelData.row) }
                }
            }
        }
    }
    MouseArea { id: hoverArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; z: -1 }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Windows' input switcher (Win+Space, or the tray's input indicator): the installed keyboards in a
// card over the tray, the active one marked. Win+Space never takes the focus from the window being
// typed in, and it goes away by itself; the mouse can pick a keyboard. Row sizes and the delay are
// the shell's list rows and banner timeout: this flyout hasn't been measured on the reference.
import QtQuick
import Fenestra.Shell

Flyout {
    id: sw
    recipe: "panel"
    takesFocus: false
    padding: 4
    function present(ms) {
        open()
        hide.interval = ms
        hide.restart()
    }
    Timer { id: hide; onTriggered: if (!cardHover.hovered) sw.close(); else restart() }
    Item {
        width: 320; height: list.height
        HoverHandler { id: cardHover }
        Column {
            id: list
            width: parent.width
            Repeater {
                model: KeyboardStatus.layouts
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool active: index === KeyboardStatus.current
                    width: list.width; height: 52
                    radius: Metrics.controlRadius
                    color: rowMouse.pressed ? Theme.pressed : active || rowMouse.containsMouse ? Theme.hover : "transparent"
                    Rectangle {
                        visible: parent.active
                        x: 0; anchors.verticalCenter: parent.verticalCenter
                        width: 3; height: 16; radius: 1.5
                        color: Theme.accentFill
                    }
                    Text {
                        x: 16; width: 36; anchors.verticalCenter: parent.verticalCenter
                        text: parent.modelData.badge
                        color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                    }
                    Column {
                        x: 64; anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - x - 12
                        Text {
                            width: parent.width; elide: Text.ElideRight
                            text: parent.parent.modelData.name
                            color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                        }
                        Text {
                            width: parent.width; elide: Text.ElideRight
                            text: Strings.keyboardOf(parent.parent.modelData.name)
                            color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
                        }
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent; hoverEnabled: true
                        onClicked: { KeyboardStatus.setCurrent(parent.index); sw.present(Metrics.osdTimeout) }
                    }
                }
            }
            Rectangle {
                width: list.width; height: 40
                radius: Metrics.controlRadius
                color: moreMouse.pressed ? Theme.pressed : moreMouse.containsMouse ? Theme.hover : "transparent"
                Text {
                    x: 16; anchors.verticalCenter: parent.verticalCenter
                    text: Strings.tr("More keyboard settings")
                    color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                }
                MouseArea {
                    id: moreMouse
                    anchors.fill: parent; hoverEnabled: true
                    onClicked: { sw.close(); Apps.runCommand("fenestra-settings --page typing") }
                }
            }
        }
    }
}

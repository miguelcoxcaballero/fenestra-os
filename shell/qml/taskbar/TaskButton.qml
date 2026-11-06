// SPDX-License-Identifier: GPL-3.0-or-later
// One taskbar button: pinned launcher and/or a group of windows of one app (B02, B04).
import QtQuick
import Fenestra.Shell

Item {
    id: button
    property url iconSource
    property string iconName
    property string label
    property int windowCount: 0
    property bool focused: false
    property bool attention: false
    readonly property bool hovered: mouse.containsMouse
    signal clicked()
    signal rightClicked()
    signal middleClicked()

    width: Metrics.taskButton; height: Metrics.taskButton
    Accessible.role: Accessible.Button
    Accessible.name: label

    Rectangle {
        anchors.fill: parent
        radius: Metrics.controlRadius
        color: mouse.pressed ? Theme.pressed : (mouse.containsMouse || button.focused) ? Theme.hover : "transparent"
        border.width: button.focused ? 1 : 0
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.05)
    }
    Image {
        anchors.centerIn: parent
        width: Metrics.taskIcon; height: Metrics.taskIcon
        sourceSize: Qt.size(Metrics.taskIcon * Screen.devicePixelRatio, Metrics.taskIcon * Screen.devicePixelRatio)
        source: button.iconSource.toString() !== "" ? button.iconSource
                : (button.iconName !== "" ? "image://icon/" + button.iconName : "")
        // Press animation (pressAnimation.js): the icon shrinks while pressed.
        scale: mouse.pressed ? 0.82 : 1
        Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
    }
    // Running indicator (taskbarStyle.js): accent dash when focused, short grey dash otherwise.
    Rectangle {
        visible: button.windowCount > 0
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 2 }
        height: 3; radius: 1.5
        width: button.focused ? 16 : 6
        color: button.attention ? "#ffb900" : button.focused ? Theme.accentFill : Theme.textSecondary
        Behavior on width { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        onClicked: (m) => {
            if (m.button === Qt.RightButton) button.rightClicked()
            else if (m.button === Qt.MiddleButton) button.middleClicked()
            else button.clicked()
        }
    }
}

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
    // Start / Search while their flyout is open.
    property bool checked: false
    readonly property bool hovered: mouse.containsMouse
    signal clicked()
    signal rightClicked()
    signal middleClicked()

    // A 44 px cell (taskbar.button.pitch) with the 40 px plate centred in it (taskbar.button).
    width: Metrics.taskPitch; height: Metrics.taskbarHeight
    Accessible.role: Accessible.Button
    Accessible.name: label

    Rectangle {
        id: plate
        anchors.centerIn: parent
        width: Metrics.taskButton; height: Metrics.taskButton
        radius: Metrics.controlRadius
        readonly property bool lit: button.focused || button.checked || mouse.containsMouse
        color: !lit ? "transparent" : mouse.containsMouse && !mouse.pressed ? Metrics.themed("taskbar.plate.hover") : Metrics.themed("taskbar.plate")
        border.width: lit ? 1 : 0
        border.color: Metrics.themed("taskbar.plate.border")
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
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: Metrics.tok("taskbar.indicator.bottom", 5) }
        height: Metrics.indicatorHeight; radius: Metrics.indicatorHeight / 2
        width: button.focused ? Metrics.indicatorFocused : Metrics.indicatorUnfocused
        color: button.attention ? "#ffb900" : button.focused ? Theme.accentFill : Metrics.themed("taskbar.indicator")
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

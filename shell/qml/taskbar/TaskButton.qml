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
        // A window asking for attention: red plate without border (dark-100-24-caption-buttons:
        // Explorer flashing), until it is focused.
        readonly property bool alert: button.attention && !button.focused
        // Shown as a whole (opacity) so that it fades in and out without passing through black.
        opacity: lit || alert ? 1 : 0
        color: alert ? Metrics.themed("taskbar.plate.attention")
               : mouse.containsMouse && !mouse.pressed ? Metrics.themed("taskbar.plate.hover") : Metrics.themed("taskbar.plate")
        border.width: alert ? 0 : 1
        border.color: Metrics.themed("taskbar.plate.border")
        // Windows fades the plate in ~90 ms on hover and to the pressed fill in ~100 ms (motion.json,
        // observations_close_2026_11_07); the reference caught Notepad's plate half way from the
        // attention red to the hover grey (dark-100-02-taskbar-hover).
        Behavior on opacity { enabled: !Motion.reduced; NumberAnimation { duration: 90 } }
        Behavior on color { enabled: !Motion.reduced; ColorAnimation { duration: 90 } }
    }
    Image {
        anchors.centerIn: parent
        width: Metrics.taskIcon; height: Metrics.taskIcon
        sourceSize: Qt.size(Metrics.taskIcon * Screen.devicePixelRatio, Metrics.taskIcon * Screen.devicePixelRatio)
        source: button.iconSource.toString() !== "" ? button.iconSource
                : (button.iconName !== "" ? "image://icon/" + button.iconName : "")
        // Press animation (pressAnimation.js): the icon shrinks while pressed.
        scale: mouse.pressed ? 0.82 : 1
        // ~150 ms to shrink on the reference recording (motion.json).
        Behavior on scale { enabled: !Motion.reduced; NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
    }
    // Running indicator (taskbarStyle.js): accent dash when focused, short grey dash otherwise.
    Rectangle {
        visible: button.windowCount > 0
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: Metrics.tok("taskbar.indicator.bottom", 5) }
        height: Metrics.indicatorHeight; radius: Metrics.indicatorHeight / 2
        // Attention: 32 px in the critical colour (dark-100-24-caption-buttons, light-100-24).
        width: plate.alert ? Metrics.tok("taskbar.indicator.attention", 32) : button.focused ? Metrics.indicatorFocused : Metrics.indicatorUnfocused
        color: plate.alert ? Metrics.themed("taskbar.indicator.attention") : button.focused ? Theme.accentFill : Metrics.themed("taskbar.indicator")
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

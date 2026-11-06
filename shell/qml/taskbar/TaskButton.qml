// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Item {
    id: button
    property url iconSource
    property string iconName
    property string label
    property bool running: false
    property bool focused: false
    signal clicked()

    width: 44; height: 44
    anchors.verticalCenter: parent ? parent.verticalCenter : undefined
    Accessible.role: Accessible.Button
    Accessible.name: label

    Rectangle {
        anchors.fill: parent
        radius: 4
        color: Qt.rgba(1, 1, 1, mouse.pressed ? 0.05 : (mouse.containsMouse || button.focused) ? 0.08 : 0)
    }
    Image {
        id: icon
        anchors.centerIn: parent
        width: 24; height: 24
        sourceSize: Qt.size(24 * Screen.devicePixelRatio, 24 * Screen.devicePixelRatio)
        source: button.iconSource.toString() !== "" ? button.iconSource
                : (button.iconName !== "" ? "image://icon/" + button.iconName : "")
        // Press animation (pressAnimation.js): the icon shrinks while pressed.
        scale: mouse.pressed ? 0.8 : 1
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    }
    // Running indicator: a dash when focused (16 px), a dot otherwise (taskbarStyle.js).
    Rectangle {
        visible: button.running
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 1 }
        height: 3; radius: 1.5
        width: button.focused ? 16 : 6
        color: button.focused ? "#4cc2ff" : Qt.rgba(1, 1, 1, 0.55)
        Behavior on width { NumberAnimation { duration: 150 } }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: button.clicked()
    }
}

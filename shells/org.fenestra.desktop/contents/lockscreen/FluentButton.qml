// SPDX-License-Identifier: GPL-3.0-or-later
// Windows' standard button on the sign-in screen ("OK" after a wrong password): 120 x 32,
// white 6 % fill, 1 px border, radius 4; keyboard focus: 2 px white ring 3 px outside.
import QtQuick

Item {
    id: b
    property alias text: label.text
    signal clicked()
    width: Math.max(120, label.implicitWidth + 24); height: 32
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: clicked()
    Rectangle {
        anchors.fill: parent; radius: 4
        color: mouse.pressed ? Qt.rgba(1, 1, 1, 0.03) : mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.06)
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.09)
    }
    Rectangle {
        anchors.fill: parent; anchors.margins: -3; radius: 7
        color: "transparent"; border.width: 2; border.color: "white"
        visible: b.activeFocus
    }
    Text {
        id: label
        anchors.centerIn: parent
        color: mouse.pressed ? Qt.rgba(1, 1, 1, 0.786) : "white"
        font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
        renderType: Text.QtRendering
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: b.clicked() }
}

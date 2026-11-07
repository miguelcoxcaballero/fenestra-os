// SPDX-License-Identifier: GPL-3.0-or-later
// Sign-in screen corner button (network, accessibility, power, sign-in options): 40 x 40, 16 px
// glyph, radius 4; hover white 13 % (measured over the dimmed picture), pressed/open 9 %.
import QtQuick

Item {
    id: b
    property alias glyph: icon.glyph
    property alias fallback: icon.fallback
    property bool checked: false
    property string accessibleName
    signal clicked()
    width: 40; height: 40
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: accessibleName
    Accessible.onPressAction: clicked()
    Keys.onReturnPressed: clicked()
    Keys.onSpacePressed: clicked()
    Rectangle {
        anchors.fill: parent; radius: 4
        color: mouse.pressed ? Qt.rgba(1, 1, 1, 0.09) : mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.13) : b.checked ? Qt.rgba(1, 1, 1, 0.09) : "transparent"
    }
    Rectangle {   // keyboard focus: 2 px white ring
        anchors.fill: parent; anchors.margins: -3; radius: 7
        color: "transparent"; border.width: 2; border.color: "white"
        visible: b.activeFocus
    }
    Glyph { id: icon; anchors.centerIn: parent; size: 16 }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: b.clicked() }
}

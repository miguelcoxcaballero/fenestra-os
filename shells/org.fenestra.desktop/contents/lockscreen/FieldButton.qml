// SPDX-License-Identifier: GPL-3.0-or-later
// A button inside the password box (reveal, submit): 24 x 24, 12 px glyph, subtle fill on hover.
import QtQuick

Item {
    id: b
    property alias glyph: icon.glyph
    property alias fallback: icon.fallback
    readonly property alias pressed: mouse.pressed
    signal clicked()
    width: 24; height: 22
    Rectangle {
        anchors.fill: parent; radius: 3
        color: mouse.pressed ? Qt.rgba(1, 1, 1, 0.04) : mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
    }
    Glyph { id: icon; anchors.centerIn: parent; size: 12; color: mouse.pressed ? Qt.rgba(1, 1, 1, 0.786) : "white" }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: b.clicked() }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// On-screen keyboard of the accessibility flyout: types into the password box (Windows' touch
// keyboard layout, Spanish row with ñ; Shift for capitals and symbols).
import QtQuick

Rectangle {
    id: osk
    property bool shift: false
    signal typed(string text)
    signal backspace()
    signal enter()
    width: 15 * 52 + 16; height: 5 * 52 + 16
    radius: 8
    color: Qt.rgba(0.11, 0.11, 0.11, 0.96)
    border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.12)
    readonly property var rows: shift
        ? [["!", "\"", "·", "$", "%", "&", "/", "(", ")", "=", "?", "¿"], ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"], ["A", "S", "D", "F", "G", "H", "J", "K", "L", "Ñ"], ["Z", "X", "C", "V", "B", "N", "M", ";", ":", "_"]]
        : [["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "'", "¡"], ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"], ["a", "s", "d", "f", "g", "h", "j", "k", "l", "ñ"], ["z", "x", "c", "v", "b", "n", "m", ",", ".", "-"]]
    Column {
        anchors.centerIn: parent
        spacing: 4
        Repeater {
            model: osk.rows
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 4
                Repeater { model: modelData; Key { label: modelData; onPressed: osk.typed(modelData) } }
            }
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 4
            Key { label: "⇧"; w: 96; checked: osk.shift; onPressed: osk.shift = !osk.shift }
            Key { label: ""; w: 400; onPressed: osk.typed(" ") }
            Key { label: "⌫"; w: 96; onPressed: osk.backspace() }
            Key { label: "↵"; w: 96; onPressed: osk.enter() }
        }
    }
    component Key: Rectangle {
        id: k
        property string label
        property real w: 48
        property bool checked: false
        signal pressed()
        width: w; height: 48; radius: 4
        color: m.pressed ? Qt.rgba(1, 1, 1, 0.16) : k.checked ? root.accent : m.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.08)
        Text { anchors.centerIn: parent; text: k.label; color: "white"; font.family: Fluent.text; font.pixelSize: 18 }
        MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; onClicked: k.pressed() }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Keyboard layout of the sign-in screen ("ESP"), left of the network button, only with more than
// one layout; a click goes to the next one (KWin's layouts).
import QtQuick
import org.kde.plasma.workspace.keyboardlayout as Keyboards

Item {
    id: kb
    Keyboards.KeyboardLayout { id: layout }
    readonly property var names: layout.layoutsList && layout.layout >= 0 && layout.layout < layout.layoutsList.length ? layout.layoutsList[layout.layout] : null
    visible: layout.layoutsList && layout.layoutsList.length > 1
    width: visible ? Math.max(40, label.implicitWidth + 16) : 0; height: 40
    Rectangle { anchors.fill: parent; radius: 4; color: m.pressed ? Qt.rgba(1, 1, 1, 0.09) : m.containsMouse ? Qt.rgba(1, 1, 1, 0.13) : "transparent" }
    Text {
        id: label
        anchors.centerIn: parent
        text: kb.names ? String(kb.names.shortName).toUpperCase().slice(0, 3) : ""
        color: "white"
        font.family: Fluent.text; font.pixelSize: 12; font.variableAxes: ({ "opsz": Fluent.opsz(12) })
        renderType: Text.QtRendering
    }
    MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; onClicked: layout.switchToNextLayout() }
    Accessible.role: Accessible.Button
    Accessible.name: kb.names ? kb.names.longName : ""
}

// SPDX-License-Identifier: GPL-3.0-or-later
// A hoverable cell of the tray (the quick group, the keyboard indicator, the overflow arrow).
import QtQuick
import Fenestra.Shell

Item {
    id: cell
    default property alias content: row.data
    property int hpad: 7
    property int spacing: 4
    property string accessibleName
    signal clicked()
    signal rightClicked()
    signal wheel(int delta)
    width: row.implicitWidth + 2 * hpad
    height: 40
    Accessible.role: Accessible.Button
    Accessible.name: accessibleName
    Rectangle { anchors.fill: parent; radius: Metrics.controlRadius
        color: mouse.pressed ? Theme.pressed : mouse.containsMouse ? Theme.hover : "transparent" }
    Row { id: row; anchors.centerIn: parent; spacing: cell.spacing }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (m) => m.button === Qt.RightButton ? cell.rightClicked() : cell.clicked()
        onWheel: (w) => cell.wheel(w.angleDelta.y)
    }
}

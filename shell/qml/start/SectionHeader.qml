// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Fenestra.Shell

Item {
    property string title
    property string action
    signal actionClicked()
    height: 28
    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: parent.title
        color: Theme.text
        font.family: Metrics.fontFamily
        font.pixelSize: 14
        font.weight: Font.DemiBold
    }
    Rectangle {
        visible: parent.action !== ""
        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
        width: actionLabel.implicitWidth + 20; height: 24
        radius: Metrics.controlRadius
        color: am.containsMouse ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(0, 0, 0, 0.05)) : (Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.7))
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(0, 0, 0, 0.06)
        Text { id: actionLabel; anchors.centerIn: parent; text: parent.parent.action; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
        MouseArea { id: am; anchors.fill: parent; hoverEnabled: true; onClicked: parent.parent.actionClicked() }
    }
}

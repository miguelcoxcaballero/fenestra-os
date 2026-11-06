// SPDX-License-Identifier: GPL-3.0-or-later
// B05: condition icon, temperature and condition; opens the Weather app.
import QtQuick
import Fenestra.Shell

Item {
    id: weather
    property var targetScreen
    readonly property bool available: Weather.available
    width: row.implicitWidth + 20; height: 40
    Accessible.role: Accessible.Button
    Accessible.name: Weather.temperature + " " + Weather.condition
    Rectangle { anchors.fill: parent; radius: Metrics.controlRadius; color: mouse.containsMouse ? Theme.hover : "transparent" }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 8
        Image {
            width: 28; height: 28
            anchors.verticalCenter: parent.verticalCenter
            sourceSize: Qt.size(28 * Screen.devicePixelRatio, 28 * Screen.devicePixelRatio)
            // Coloured icons are drawn for dark surfaces; light mode uses the symbolic ones.
            source: "image://icon/" + (Theme.dark && Weather.iconName ? Weather.iconName : Weather.symbolicIconName)
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: Weather.temperature; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold }
            Text { text: Weather.condition; visible: text !== ""; color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
        }
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: Weather.openApp() }
}

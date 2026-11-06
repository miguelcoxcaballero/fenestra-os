// SPDX-License-Identifier: GPL-3.0-or-later
// Time and date in the system locale; wakes once a minute, on the minute.
import QtQuick
import Fenestra.Shell

Item {
    id: clock
    property date now: new Date()
    signal clicked()
    width: text.implicitWidth + 16; height: 40
    Rectangle { anchors.fill: parent; radius: Metrics.controlRadius; color: mouse.containsMouse ? Theme.hover : "transparent" }
    Text {
        id: text
        anchors.centerIn: parent
        horizontalAlignment: Text.AlignRight
        color: Theme.text
        font.family: Metrics.fontFamily
        font.pixelSize: 12
        lineHeight: 1.15
        // Hours and minutes (the C locale's short format has seconds).
        text: Qt.formatTime(clock.now, Qt.locale().timeFormat(Locale.ShortFormat).replace(/[:.]ss/, "")) + "\n"
              + Qt.formatDate(clock.now, Locale.ShortFormat)
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: clock.clicked() }
    Timer {
        interval: 60000 - new Date().getSeconds() * 1000
        running: true; repeat: true
        onTriggered: { clock.now = new Date(); interval = 60000 - clock.now.getSeconds() * 1000 }
    }
}

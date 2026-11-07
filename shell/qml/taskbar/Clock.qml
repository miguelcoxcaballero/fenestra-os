// SPDX-License-Identifier: GPL-3.0-or-later
// Time and date in the system locale; wakes once a minute, on the minute.
import QtQuick
import Fenestra.Shell

Item {
    id: clock
    property date now: new Date()
    signal clicked()
    width: text.textWidth + 16; height: 40
    Rectangle { anchors.fill: parent; radius: Metrics.controlRadius; color: mouse.containsMouse ? Theme.hover : "transparent" }
    // Right-aligned, 16 px apart (user-win11 163657 at 150 %: "16:36" and "04/11/2026" both end at
    // x 2850, glyph tops 1745 / 1769, 13 device px tall, every stem on whole pixels). Laid out and
    // hinted in device pixels (ShadowLabel without its shadow), as Windows does: Qt Quick's Text
    // at 1.5 put the digits a fraction of a pixel off the grid (one row lower and blurred).
    ShadowLabel {
        id: text
        anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter
                  verticalCenterOffset: Tokens.v("clock.dy", 0) }
        width: 140
        pad: 0
        maxLines: 2
        horizontalAlignment: Qt.AlignRight
        shadowStrength: 0
        gamma: Tokens.v("clock.gamma", 1)
        color: Theme.text
        lineHeight: Metrics.tok("clock.line", 16)
        // Windows' taskbar text: Segoe UI Variable at its small optical size, tabular figures
        // ("04/11/2026" 93 device px wide at 150 %: every digit 10 px, "1" too).
        font.family: Metrics.fontFamily
        font.pixelSize: 12
        font.variableAxes: ({ "opsz": Tokens.v("clock.font.opsz", 8) })
        font.features: ({ "tnum": 1 })
        font.hintingPreference: Font.PreferFullHinting
        // The locale's short time without seconds and its short date, as Windows takes them from the
        // regional format (en_GB: 16:00 over 04/11/2026). Qt.formatDate(d, Locale.ShortFormat) would be
        // ISO: Locale.ShortFormat is 1, which formatDate reads as Qt.ISODate.
        text: clock.now.toLocaleTimeString(Qt.locale(), Qt.locale().timeFormat(Locale.ShortFormat).replace(/[:.]ss/, "")) + "\n"
              + clock.now.toLocaleDateString(Qt.locale(), Locale.ShortFormat)
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: clock.clicked() }
    Timer {
        interval: 60000 - new Date().getSeconds() * 1000
        running: true; repeat: true
        onTriggered: { clock.now = new Date(); interval = 60000 - clock.now.getSeconds() * 1000 }
    }
}

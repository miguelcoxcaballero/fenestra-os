// SPDX-License-Identifier: GPL-3.0-or-later
// Power menu (Windows: 118.7 x 84 px with two items at 150 %, 2 px from the screen's right edge,
// 24.7 px over the button row): Sleep, Shut down, Restart; 40 px items, 16 px glyph at 18.7 px,
// text at 48 px. logind (systemctl) does it; the session is active while locked.
import QtQuick

Acrylic {
    id: menu
    width: Math.max(118.7, col.implicitWidth); height: col.implicitHeight + 4
    border: false
    tint: "#191919"; tintOpacity: 0.44
    readonly property var items: [
        { text: root.tr("Sleep", "Suspender"), glyph: "\uE708", fb: "sleep", cmd: "systemctl suspend" },
        { text: root.tr("Shut down", "Apagar"), glyph: "\uE7E8", fb: "shutdown", cmd: "systemctl poweroff" },
        { text: root.tr("Restart", "Reiniciar"), glyph: "\uE777", fb: "restart", cmd: "systemctl reboot" }]
    Column {
        id: col
        y: 2
        width: parent.width
        Repeater {
            model: menu.items
            Item {
                id: row
                width: Math.max(menu.width, label.implicitWidth + 48 + 24); height: 40
                implicitWidth: label.implicitWidth + 48 + 24
                Rectangle { anchors.fill: parent; anchors.margins: 4; anchors.topMargin: 2; anchors.bottomMargin: 2; radius: 4
                            color: m.pressed ? Qt.rgba(1, 1, 1, 0.04) : m.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent" }
                Glyph { x: 18.7 - 2; anchors.verticalCenter: parent.verticalCenter; size: 16; glyph: modelData.glyph
                        fallback: "file:///usr/share/fenestra/assets/security/" + modelData.fb + ".svg" }
                Text {
                    id: label
                    x: 48; anchors.verticalCenter: parent.verticalCenter
                    text: modelData.text; color: "white"
                    font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                    renderType: Text.QtRendering
                }
                MouseArea {
                    id: m; anchors.fill: parent; hoverEnabled: true
                    onClicked: {
                        const cmd = modelData.cmd
                        root.run(cmd)
                        root.menu = ""
                        if (cmd.indexOf("suspend") >= 0) root.showClock()
                    }
                }
                Accessible.role: Accessible.MenuItem
                Accessible.name: modelData.text
            }
        }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra slider: 4 px track, accent fill, 9 px thumb with an accent dot (osdStyle.js).
import QtQuick
import Fenestra.Shell

Item {
    id: slider
    property real value: 0      // 0–100
    property bool enabled_: true
    signal moved(real value)
    implicitHeight: 20
    readonly property real pos: Math.max(0, Math.min(1, value / 100))
    Rectangle { anchors.verticalCenter: parent.verticalCenter; x: 9; width: parent.width - 18; height: 4; radius: 2
                color: Theme.dark ? Qt.rgba(1, 1, 1, 0.54) : Qt.rgba(0, 0, 0, 0.45) }
    Rectangle { anchors.verticalCenter: parent.verticalCenter; x: 9; width: (parent.width - 18) * slider.pos; height: 4; radius: 2
                color: Theme.accentText }
    Rectangle {
        x: (parent.width - 18) * slider.pos; anchors.verticalCenter: parent.verticalCenter
        width: 18; height: 18; radius: 9
        color: Theme.dark ? "#454545" : "white"
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(0, 0, 0, 0.08)
        Rectangle { anchors.centerIn: parent; width: m.pressed ? 8 : m.containsMouse ? 12 : 10; height: width; radius: width / 2; color: Theme.accentText
                    Behavior on width { NumberAnimation { duration: 100 } } }
    }
    MouseArea {
        id: m
        anchors.fill: parent
        hoverEnabled: true
        function set(x) { slider.moved(Math.round(Math.max(0, Math.min(1, (x - 9) / (width - 18))) * 100)) }
        onPressed: (e) => set(e.x)
        onPositionChanged: (e) => { if (pressed) set(e.x) }
        onWheel: (w) => slider.moved(Math.max(0, Math.min(100, slider.value + (w.angleDelta.y > 0 ? 2 : -2))))
    }
}

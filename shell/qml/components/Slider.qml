// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra slider (quick settings, OSD): 4 px track, accent fill (the tiles' colour, dark-100-12-quick) up to a 20 px thumb with a 10 px
// accent dot (12 hovered, 8 pressed). The thumb overhangs the track by half its size on each end.
import QtQuick
import Fenestra.Shell

Item {
    id: slider
    property real value: 0      // 0–100
    property bool enabled_: true
    property bool dimmed: false    // no device behind it (quick settings without audio output)
    signal moved(real value)
    readonly property int thumb: Metrics.n("slider.thumb", 20)
    readonly property int track: Metrics.n("slider.track", 4)
    implicitHeight: thumb
    readonly property real pos: Math.max(0, Math.min(1, value / 100))
    readonly property real span: width - thumb
    Rectangle { anchors.verticalCenter: parent.verticalCenter; x: slider.thumb / 2; width: slider.span; height: slider.track; radius: slider.track / 2
                color: Metrics.col("slider.track") }
    Rectangle { anchors.verticalCenter: parent.verticalCenter; x: slider.thumb / 2; width: slider.span * slider.pos; height: slider.track; radius: slider.track / 2
                color: slider.dimmed ? Theme.textDisabled : Theme.accentFill }
    Rectangle {
        visible: !slider.dimmed
        x: Math.round(slider.span * slider.pos); anchors.verticalCenter: parent.verticalCenter
        width: slider.thumb; height: slider.thumb; radius: slider.thumb / 2
        color: Metrics.col("slider.thumb")
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(0, 0, 0, 0.08)
        readonly property int inner: Metrics.n("slider.thumb.inner", 10)
        Rectangle { anchors.centerIn: parent; width: m.pressed ? parent.inner - 2 : m.containsMouse ? parent.inner + 2 : parent.inner
                    height: width; radius: width / 2; color: Theme.accentFill
                    Behavior on width { enabled: !Motion.reduced; NumberAnimation { duration: 100 } } }
    }
    MouseArea {
        id: m
        anchors.fill: parent
        enabled: slider.enabled_
        hoverEnabled: true
        function set(x) { slider.moved(Math.round(Math.max(0, Math.min(1, (x - slider.thumb / 2) / slider.span)) * 100)) }
        onPressed: (e) => set(e.x)
        onPositionChanged: (e) => { if (pressed) set(e.x) }
        onWheel: (w) => slider.moved(Math.max(0, Math.min(100, slider.value + (w.angleDelta.y > 0 ? 2 : -2))))
    }
}

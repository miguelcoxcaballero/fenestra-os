// SPDX-License-Identifier: GPL-3.0-or-later
// WinUI's indeterminate ProgressRing (32 px, 3 px stroke): an arc whose length breathes while it
// turns, drawn by the GPU (Shape, CurveRenderer) and driven by the animation clock.
import QtQuick
import QtQuick.Shapes

Item {
    id: ring
    width: 32; height: 32
    property real phase: 0
    NumberAnimation on phase { from: 0; to: 1; duration: 2000; loops: Animation.Infinite; running: ring.visible }
    // Head and tail of the arc (degrees): the head leads, the tail catches up (WinUI's Lottie curve).
    readonly property real head: 450 * ring.ease(Math.min(1, phase * 2)) + 360 * phase
    readonly property real tail: 450 * ring.ease(Math.max(0, phase * 2 - 1)) + 360 * phase
    function ease(x) { return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2 }
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: "white"; strokeWidth: 3; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: 16; centerY: 16; radiusX: 14.5; radiusY: 14.5
                           startAngle: ring.tail - 90; sweepAngle: Math.max(4, ring.head - ring.tail) }
        }
    }
}

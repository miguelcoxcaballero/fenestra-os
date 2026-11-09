// SPDX-License-Identifier: GPL-3.0-or-later
// The translucent rectangle KWin shows while a window is dragged to a screen edge, in place of
// Plasma's (a themed SVG frame flush with the edges). KWin loads this through [Outline] QmlPath
// in kwinrc, written by shell/src/services/kwinintegration.cpp, once per session.
// Fill, edge and 8 px radius: the snap.preview tokens (docs/fenestra-shell/INVENTORY.md). The
// rectangle floats clear of the screen edges and grows from the dragged window.
import QtQuick
import QtQuick.Window as QuickWindow

QuickWindow.Window {
    id: window

    // KWin's context property; a composite type can't see it, so dark.qml and light.qml pass it.
    property var target
    property bool dark: true
    readonly property int inset: 8
    readonly property int duration: 250
    readonly property real dpr: Screen.devicePixelRatio
    // Same pixel grid as the shell's acrylic edge: 2 device px at 150 %.
    readonly property real edge: (dpr > 1 && dpr < 2 ? 2 : Math.max(1, Math.round(dpr))) / dpr
    property bool animated: false

    flags: Qt.BypassWindowManagerHint | Qt.FramelessWindowHint
    color: "transparent"
    x: target.unifiedGeometry.x
    y: target.unifiedGeometry.y
    width: target.unifiedGeometry.width
    height: target.unifiedGeometry.height
    visible: target.active

    function place(g, gap) {
        preview.x = g.x - target.unifiedGeometry.x + gap
        preview.y = g.y - target.unifiedGeometry.y + gap
        preview.width = Math.max(0, g.width - 2 * gap)
        preview.height = Math.max(0, g.height - 2 * gap)
    }

    onVisibleChanged: {
        if (!visible)
            return
        const parentRect = target.visualParentGeometry
        animated = false
        if (parentRect.width > 0 && parentRect.height > 0) {
            place(parentRect, 0)
            animated = true
        }
        place(target.geometry, inset)
        animated = true
    }

    Connections {
        target: window.target
        // The window itself moved: an animation would be offset from it.
        function onUnifiedGeometryChanged() {
            if (!window.visible)
                return
            window.animated = false
            window.place(window.target.geometry, window.inset)
            window.animated = true
        }
    }

    Rectangle {
        id: preview
        radius: 8
        antialiasing: true
        color: window.dark ? Qt.rgba(200 / 255, 205 / 255, 204 / 255, 0.17) : Qt.rgba(1, 1, 1, 0.35)
        border.width: window.edge
        border.color: window.dark ? Qt.rgba(235 / 255, 240 / 255, 238 / 255, 0.55) : Qt.rgba(0, 0, 0, 0.15)

        Rectangle {
            anchors.fill: parent
            anchors.margins: window.edge
            radius: Math.max(0, parent.radius - window.edge)
            antialiasing: true
            color: "transparent"
            border.width: window.edge
            border.color: window.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.4)
        }

        Behavior on x { enabled: window.animated; PropertyAnimation { duration: window.duration; easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] } }
        Behavior on y { enabled: window.animated; PropertyAnimation { duration: window.duration; easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] } }
        Behavior on width { enabled: window.animated; PropertyAnimation { duration: window.duration; easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] } }
        Behavior on height { enabled: window.animated; PropertyAnimation { duration: window.duration; easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] } }
    }
}

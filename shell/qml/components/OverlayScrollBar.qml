// SPDX-License-Identifier: GPL-3.0-or-later
// WinUI's overlay scroll bar (ScrollBar in ScrollViewer, "conscious" mode): nothing while idle; a
// 2 px rounded indicator while the pointer is over the list or it scrolls; 6 px with a faint
// track when the pointer is on the bar itself; it fades out 1 s after the last activity. The thumb
// can be dragged and the track clicked (page up / down).
import QtQuick
import Fenestra.Shell

Item {
    id: bar
    property Flickable flickable
    // The pointer is over the scrolled area (the owner's HoverHandler).
    property bool areaHovered: false
    readonly property bool needed: flickable && flickable.contentHeight > flickable.height + 0.5
    readonly property bool expanded: barMouse.containsMouse || barMouse.pressed
    property bool active: false
    width: 12
    visible: needed
    opacity: active || expanded ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: bar.active || bar.expanded ? 83 : 167 } }

    function poke() { active = true; idle.restart() }
    Timer { id: idle; interval: 1000; onTriggered: if (!bar.areaHovered && !bar.expanded) bar.active = false; else restart() }
    onAreaHoveredChanged: if (areaHovered) poke()
    Connections { target: bar.flickable; function onContentYChanged() { bar.poke() } }

    Rectangle {
        // Track: only when expanded.
        anchors.fill: parent
        anchors.margins: 1
        radius: width / 2
        color: Theme.dark ? "#0fffffff" : "#0a000000"
        opacity: bar.expanded ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 83 } }
    }
    Rectangle {
        id: thumb
        readonly property real trackH: bar.height - 4
        readonly property real ratio: bar.flickable ? Math.min(1, bar.flickable.height / Math.max(1, bar.flickable.contentHeight)) : 1
        readonly property real range: Math.max(1, bar.flickable ? bar.flickable.contentHeight - bar.flickable.height : 1)
        width: bar.expanded ? 6 : 2
        Behavior on width { NumberAnimation { duration: 83 } }
        x: bar.width - 3 - width
        height: Math.max(24, trackH * ratio)
        y: 2 + (trackH - height) * (bar.flickable ? Math.max(0, Math.min(1, bar.flickable.contentY / range)) : 0)
        radius: width / 2
        color: Theme.dark ? "#8bffffff" : "#72000000"
    }
    MouseArea {
        id: barMouse
        anchors.fill: parent
        hoverEnabled: true
        property real grabY: -1
        onPressed: (e) => {
            if (e.y >= thumb.y && e.y <= thumb.y + thumb.height) { grabY = e.y - thumb.y; return }
            grabY = -1
            const f = bar.flickable
            f.contentY = Math.max(0, Math.min(f.contentHeight - f.height, f.contentY + (e.y < thumb.y ? -f.height : f.height)))
        }
        onPositionChanged: (e) => {
            if (!pressed || grabY < 0) return
            const f = bar.flickable
            const t = Math.max(0, Math.min(1, (e.y - grabY - 2) / Math.max(1, thumb.trackH - thumb.height)))
            f.contentY = t * (f.contentHeight - f.height)
        }
        onContainsMouseChanged: bar.poke()
    }
}

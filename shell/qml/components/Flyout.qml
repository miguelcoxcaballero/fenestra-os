// SPDX-License-Identifier: GPL-3.0-or-later
// A taskbar flyout: layer-shell surface 12 px above the taskbar (its exclusive zone), at least
// 13 px from the screen edges, no arrow (B11). Closes when it loses keyboard focus.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: flyout
    property var targetScreen
    // Horizontal centre the flyout should line up with (screen coordinates), or -1 for "right edge".
    property real anchorX: -1
    property bool rightAligned: anchorX < 0
    default property alias content: body.data
    property alias background: frame
    property int padding: 4
    // Hover popups (previews, tooltips) must not take the keyboard focus from the active window.
    property bool takesFocus: true

    signal dismissed()

    color: "transparent"
    flags: Qt.FramelessWindowHint
    width: body.childrenRect.width + 2 * padding
    height: body.childrenRect.height + 2 * padding
    visible: false

    LayerShell.Window.screenConfiguration: LayerShell.Window.ScreenFromQWindow
    LayerShell.Window.scope: "fenestra-flyout"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom
                               | (rightAligned ? LayerShell.Window.AnchorRight : LayerShell.Window.AnchorLeft)
    LayerShell.Window.margins.bottom: Metrics.flyoutGap
    LayerShell.Window.margins.right: Metrics.flyoutEdge
    LayerShell.Window.margins.left: {
        if (rightAligned || !targetScreen) return Metrics.flyoutEdge
        const x = Math.round(anchorX - width / 2)
        return Math.max(Metrics.flyoutEdge, Math.min(x, targetScreen.width - width - Metrics.flyoutEdge))
    }
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: takesFocus ? LayerShell.Window.KeyboardInteractivityOnDemand
                                                       : LayerShell.Window.KeyboardInteractivityNone

    function open() { if (targetScreen) ShellUtil.placeOnScreen(flyout, targetScreen.name); visible = true; if (takesFocus) requestActivate() }
    function close() { if (visible) { visible = false; dismissed() } }
    function toggle() { visible ? close() : open() }

    onActiveChanged: if (takesFocus && !active && visible) close()

    Rectangle {
        id: frame
        anchors.fill: parent
        radius: Metrics.flyoutRadius
        color: Theme.flyout
        border.color: Theme.flyoutBorder
        border.width: 1
    }
    Item {
        id: body
        x: flyout.padding; y: flyout.padding
        width: childrenRect.width; height: childrenRect.height
        focus: true
        Keys.onEscapePressed: flyout.close()
    }
}

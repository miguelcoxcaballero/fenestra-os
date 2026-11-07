// SPDX-License-Identifier: GPL-3.0-or-later
// Start and Search: a fixed-size layer surface 12 px above the taskbar, centred on the screen
// (or at the left with left-aligned icons). Opens and closes with PopupMotion "taskbar", as Windows 11
// (design/motion.json): rises from fully hidden behind the taskbar (height + 12 px) in 250 ms on
// cubic-bezier(0, 0, 0, 1), opaque, and goes back down in 167 ms. The surface ends 12 px above the
// taskbar (its size is the panel's), so the panel is clipped there instead of at the taskbar's edge.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: popup
    property var targetScreen
    property bool leftAligned: ShellSettings.taskbarAlignment === "left"
    property bool shown: false
    // Screen x of the left edge (Search: the taskbar's search box), -1 = centred (Start).
    property real anchorLeft: -1
    // Where it lands on its screen (for menus opened from inside it).
    readonly property real screenX: anchorLeft >= 0 && targetScreen ? Math.max(Metrics.flyoutEdge, Math.min(Math.round(anchorLeft), targetScreen.width - width - Metrics.flyoutEdge))
                                    : leftAligned || !targetScreen ? Metrics.flyoutEdge : Math.round((targetScreen.width - width) / 2)
    // PopupMotion kind (taskbar for Start and Search, as measured).
    property string motion: "taskbar"
    readonly property bool moving: motionCtl.busy
    default property alias content: panel.data
    property alias panel: panel
    signal opened()
    signal closed()

    color: "transparent"
    visible: false
    LayerShell.Window.scope: "fenestra-start"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | (leftAligned || anchorLeft >= 0 ? LayerShell.Window.AnchorLeft : 0)
    LayerShell.Window.margins.bottom: Metrics.flyoutGap
    LayerShell.Window.margins.left: anchorLeft >= 0 ? screenX : Metrics.flyoutEdge
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand

    function open() {
        if (shown) return
        if (targetScreen) ShellUtil.placeOnScreen(popup, targetScreen.name)
        shown = true
        visible = true
        ShellUtil.enableBlur(popup, Metrics.flyoutRadius)
        requestActivate()
        motionCtl.enter()
        opened()
    }
    function close() {
        if (!shown) return
        shown = false
        motionCtl.leave()
    }
    function toggle() { shown ? close() : open() }
    onActiveChanged: if (!active && shown) close()

    PopupMotion {
        id: motionCtl
        kind: popup.motion
        target: panel
        travel: popup.height + Metrics.flyoutGap
        onGone: { popup.visible = false; popup.closed() }
    }

    // Clip: the panel slides out of the bottom edge (the taskbar's top), never over the taskbar.
    Item {
        anchors.fill: parent
        clip: true
        Rectangle {
            id: panel
            width: parent.width; height: parent.height
            transform: motionCtl.shift
            radius: Metrics.flyoutRadius
            // Flat fill of the reference (acrylic fallback); KWin's blur still runs behind it.
            color: Metrics.themed("start.fill")
            border.color: Metrics.themed("start.border")
            border.width: 1
            Keys.onEscapePressed: popup.close()
            focus: true
        }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Start and Search: a fixed-size layer surface 12 px above the taskbar, centred on the screen
// (or at the left with left-aligned icons). Opens sliding up 96 px in 200 ms (OutQuint) and closes
// sliding down in 120 ms (InQuad), clipped at the taskbar edge (arc/windowsPopupMotion.js).
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
    // Opening motion: rise by openOffset in openDuration (decelerate), or fade when openOffset is 0.
    property int openOffset: Metrics.popupOffset
    property int openDuration: Metrics.popupOpen
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
        panel.y = Motion.reduced ? 0 : openOffset
        panel.opacity = Motion.reduced || openOffset > 0 ? 1 : 0
        slideIn.restart()
        opened()
    }
    function close() {
        if (!shown) return
        shown = false
        if (Motion.reduced) { visible = false; closed(); return }
        slideOut.restart()
    }
    function toggle() { shown ? close() : open() }
    onActiveChanged: if (!active && shown) close()

    ParallelAnimation {
        id: slideIn
        NumberAnimation { target: panel; property: "y"; to: 0; duration: popup.openDuration
                          easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.decelerate }
        NumberAnimation { target: panel; property: "opacity"; to: 1; duration: popup.openDuration }
    }
    SequentialAnimation {
        id: slideOut
        NumberAnimation { target: panel; property: popup.openOffset > 0 ? "y" : "opacity"; to: popup.openOffset > 0 ? popup.openOffset : 0
                          duration: Metrics.popupClose; easing.type: Easing.InQuad }
        ScriptAction { script: { popup.visible = false; popup.closed() } }
    }

    // Clip: the panel slides out of the bottom edge (the taskbar's top), never over the taskbar.
    Item {
        anchors.fill: parent
        clip: true
        Rectangle {
            id: panel
            width: parent.width; height: parent.height
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

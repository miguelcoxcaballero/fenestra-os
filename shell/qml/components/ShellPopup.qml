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
    default property alias content: panel.data
    property alias panel: panel
    signal opened()
    signal closed()

    color: "transparent"
    visible: false
    LayerShell.Window.scope: "fenestra-start"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | (leftAligned ? LayerShell.Window.AnchorLeft : 0)
    LayerShell.Window.margins.bottom: Metrics.flyoutGap
    LayerShell.Window.margins.left: Metrics.flyoutEdge
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand

    function open() {
        if (shown) return
        if (targetScreen) ShellUtil.placeOnScreen(popup, targetScreen.name)
        shown = true
        visible = true
        ShellUtil.enableBlur(popup, Metrics.flyoutRadius)
        requestActivate()
        panel.y = Motion.reduced ? 0 : Metrics.popupOffset
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

    NumberAnimation { id: slideIn; target: panel; property: "y"; to: 0; duration: Metrics.popupOpen; easing.type: Easing.OutQuint }
    SequentialAnimation {
        id: slideOut
        NumberAnimation { target: panel; property: "y"; to: Metrics.popupOffset; duration: Metrics.popupClose; easing.type: Easing.InQuad }
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
            color: Theme.acrylic
            border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(0, 0, 0, 0.10)
            border.width: 1
            Keys.onEscapePressed: popup.close()
            focus: true
        }
    }
}

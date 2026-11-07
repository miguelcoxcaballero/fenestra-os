// SPDX-License-Identifier: GPL-3.0-or-later
// Start and Search: a fixed-size panel 12 px above the taskbar, centred on the screen (or at the
// left with left-aligned icons, or at `anchorLeft`), as the user's Windows 11 (reference-shots/
// user-win11 160039 / 160049: 834 x 866 at 150 %, 18 device px above the taskbar).
// The layer surface reaches down to the taskbar's top edge and is larger than the panel by the
// shadow's margin; its input region is the panel only, so the shadow and the gap stay
// click-through. Opens and closes with PopupMotion "taskbar" (design/motion.json): the panel rises
// from fully hidden behind the taskbar's top edge (travel = height + gap) and is clipped there, as
// on Windows. KWin's blur follows the moving, clipped panel on every frame (ShellUtil.setBlurItems),
// so no blurred rectangle waits where the panel lands.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: popup
    property var targetScreen
    property bool leftAligned: ShellSettings.taskbarAlignment === "left"
    property bool shown: false
    // Screen x of the panel's left edge (Search: the taskbar's search box), -1 = centred (Start).
    property real anchorLeft: -1
    // false: ignore anchorLeft (Search opened from the taskbar's icon sits where Start does).
    property bool useAnchor: true
    property int panelWidth: Metrics.startWidth
    property int panelHeight: Metrics.startHeight
    readonly property int shadowMargin: Metrics.tok("popup.shadow.margin", 28)
    readonly property bool anchored: useAnchor && anchorLeft >= 0
    // Where the panel lands on its screen (for menus opened from inside it).
    readonly property real screenX: anchored && targetScreen ? Math.max(Metrics.flyoutEdge, Math.min(Math.round(anchorLeft), targetScreen.width - panelWidth - Metrics.flyoutEdge))
                                    : leftAligned || !targetScreen ? Metrics.flyoutEdge : Math.round((targetScreen.width - panelWidth) / 2)
    // PopupMotion kind (taskbar for Start and Search, as measured).
    property string motion: "taskbar"
    readonly property bool moving: motionCtl.busy
    default property alias content: body.data
    property alias panel: panel
    property alias material: material
    signal opened()
    signal closed()

    color: "transparent"
    visible: false
    width: panelWidth + 2 * shadowMargin
    height: shadowMargin + panelHeight + Metrics.flyoutGap
    LayerShell.Window.scope: "fenestra-start"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | (leftAligned || anchored ? LayerShell.Window.AnchorLeft : 0)
    LayerShell.Window.margins.bottom: 0
    LayerShell.Window.margins.left: screenX - shadowMargin
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand

    function updateBlur() {
        if (visible && material.translucent) ShellUtil.setBlurItems(popup, [material], Metrics.flyoutRadius)
    }
    function open() {
        if (shown) return
        if (targetScreen) ShellUtil.placeOnScreen(popup, targetScreen.name)
        shown = true
        motionCtl.enter()   // the first frame already has the panel behind the taskbar
        visible = true
        ShellUtil.setInputItems(popup, [inputArea])
        updateBlur()
        requestActivate()
        opened()
    }
    function close() {
        if (!shown) return
        shown = false
        motionCtl.leave()
    }
    function toggle() { shown ? close() : open() }
    onActiveChanged: if (!active && shown) close()
    onWidthChanged: if (visible) { ShellUtil.setInputItems(popup, [inputArea]); updateBlur() }
    onHeightChanged: if (visible) { ShellUtil.setInputItems(popup, [inputArea]); updateBlur() }
    Connections {
        target: ShellSettings
        function onTransparencyChanged() { if (!ShellSettings.transparency) ShellUtil.clearBlur(popup); else popup.updateBlur() }
    }

    PopupMotion {
        id: motionCtl
        kind: popup.motion
        target: panel
        travel: popup.panelHeight + Metrics.flyoutGap
        onGone: { popup.visible = false; ShellUtil.clearBlur(popup); popup.closed() }
    }
    Connections { target: motionCtl.shift; function onYChanged() { popup.updateBlur() } function onXChanged() { popup.updateBlur() } }

    // The panel's final place: the surface's input region.
    Item { id: inputArea; x: popup.shadowMargin; y: popup.shadowMargin; width: popup.panelWidth; height: popup.panelHeight }
    // Clip: the panel slides out of the surface's bottom edge (the taskbar's top), never over the taskbar.
    Item {
        anchors.fill: parent
        clip: true
        Item {
            id: panel
            x: popup.shadowMargin; y: popup.shadowMargin
            width: popup.panelWidth; height: popup.panelHeight
            transform: motionCtl.shift
            Acrylic { id: material; anchors.fill: parent }
            Item {
                id: body
                anchors.fill: parent
                Keys.onEscapePressed: popup.close()
                focus: true
            }
            AcrylicOutline { acrylic: material }
        }
    }
}

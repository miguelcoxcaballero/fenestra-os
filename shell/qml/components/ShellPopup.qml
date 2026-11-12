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
    // ---- The real acrylic (core/backdrop.h) ----------------------------------------------------
    // Recipes computed from the capture (Start adds "base" for its bands); the popup shows the
    // fallback material (fill over KWin's blur) until they are ready, then fades them in and drops
    // KWin's blur.
    property var backdropRecipes: [material.backdropRecipe]
    property int backdropId: 0
    // The acrylic on screen: the last one computed, kept while the popup is closed so that the
    // next opening shows it from its first frame (the backdrop rarely changed) until the new
    // capture replaces it (~40 ms later).
    property int shownId: 0
    property bool acrylicOn: false
    // false: the popup draws its own BackdropViews (Start's three parts).
    property bool materialBackdrop: true
    signal backdropArrived(int id)
    // The panel's place on the screen at rest, and the area it can cover while it moves (down to
    // the taskbar's top edge), logical px.
    readonly property real restY: targetScreen ? targetScreen.height - Metrics.taskbarHeight - Metrics.flyoutGap - panelHeight : 0
    readonly property rect backdropArea: Qt.rect(screenX, restY, panelWidth, panelHeight + Metrics.flyoutGap)
    // The whole surface on the screen (for a menu opened over it: Backdrop grabs it).
    readonly property rect screenRect: Qt.rect(screenX - shadowMargin, restY - shadowMargin, width, height)
    property int pendingId: 0
    property bool refreshAfterMotion: false
    Connections {
        target: motionCtl
        function onBusyChanged() {
            if (motionCtl.busy || !popup.shown) return
            if (popup.pendingId > 0) {
                const id = popup.pendingId; popup.pendingId = 0
                if (id === popup.backdropId) { popup.showBackdrop(id); if (popup.shownId !== id) Backdrop.release(popup.shownId); popup.shownId = id }
            }
            if (popup.refreshAfterMotion) { popup.refreshAfterMotion = false; popup.requestBackdrop() }
        }
    }
    function requestBackdrop() {
        if (backdropId !== shownId) Backdrop.release(backdropId)
        backdropId = 0
        if (!ShellSettings.transparency || !targetScreen) return
        backdropId = Backdrop.request(popup, backdropArea, WallpaperSource.image !== "" ? WallpaperSource.image : WallpaperSource.color,
                                      backdropRecipes)
        if (shownId > 0) { showBackdrop(shownId); acrylicOn = true; ShellUtil.clearBlur(popup) }
    }
    function showBackdrop(id) {
        material.backdrop.area = Backdrop.area(id)
        material.backdrop.origin = Qt.point(popup.screenX, popup.restY)
        material.backdrop.shift = motionCtl.shift
        if (popup.materialBackdrop && popup.backdropRecipes.indexOf(material.backdropRecipe) >= 0)
            material.backdrop.source = "image://backdrop/" + id + "/" + material.backdropRecipe
        popup.backdropArrived(id)
    }
    // As Flyout: the kept acrylic is given back after two minutes closed.
    Timer { interval: 120000; running: !popup.shown && popup.shownId > 0; onTriggered: if (!popup.shown && !popup.visible) popup.dropBackdrop() }
    function dropBackdrop() {
        Backdrop.release(backdropId)
        Backdrop.release(shownId)
        backdropId = 0; shownId = 0
        acrylicOn = false
        material.backdrop.source = ""
        popup.backdropArrived(0)
    }
    Connections {
        target: Backdrop
        function onReady(id, ms) {
            if (id !== popup.backdropId || !popup.shown) return
            if (motionCtl.busy) { popup.pendingId = id; return }   // swap after the slide
            popup.showBackdrop(id)
            if (popup.shownId !== id) Backdrop.release(popup.shownId)
            popup.shownId = id
            if (!popup.acrylicOn) acrylicTimer.restart()
        }
    }
    // After the fade: KWin's blur is under an opaque acrylic, drop it.
    Timer { id: acrylicTimer; interval: 100; onTriggered: { popup.acrylicOn = true; ShellUtil.clearBlur(popup) } }

    color: "transparent"
    // Keep the scene (the acrylic's masked layers) while hidden: the next opening draws the last
    // acrylic in its first frame instead of building the layers after it.
    Component.onCompleted: ShellUtil.keepScene(this)
    visible: false
    width: panelWidth + 2 * shadowMargin
    height: shadowMargin + panelHeight + Metrics.flyoutGap
    // "dock": KWin types layer surfaces by scope (LayerShellV1Window: unknown scopes are Normal
    // windows), and its scale effect fades and scales Normal windows in when they map; Windows'
    // popups slide in opaque (PopupMotion). A dock is neither scaled nor faded (fadingpopups).
    LayerShell.Window.scope: "dock"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | (leftAligned || anchored ? LayerShell.Window.AnchorLeft : 0)
    LayerShell.Window.margins.bottom: 0
    LayerShell.Window.margins.left: screenX - shadowMargin
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand

    function updateBlur() {
        if (visible && material.translucent && !acrylicOn) ShellUtil.setBlurItems(popup, [material], Metrics.flyoutRadius)
    }
    function open() {
        if (shown) return
        if (targetScreen) ShellUtil.placeOnScreen(popup, targetScreen.name)
        shown = true
        // The capture (KWin renders the scene once more) and the new texture cost frames at the
        // start of the slide, where it moves fastest (60 fps for ~80 ms): with an acrylic kept from
        // the last opening, show it now and capture again when the entrance is over.
        if (shownId > 0) { showBackdrop(shownId); acrylicOn = true; ShellUtil.clearBlur(popup); refreshAfterMotion = true }
        else requestBackdrop()
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
        function onTransparencyChanged() { if (!ShellSettings.transparency) { ShellUtil.clearBlur(popup); popup.dropBackdrop() } else popup.updateBlur() }
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

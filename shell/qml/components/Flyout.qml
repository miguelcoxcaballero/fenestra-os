// SPDX-License-Identifier: GPL-3.0-or-later
// A taskbar flyout: layer-shell surface 12 px above the taskbar (its exclusive zone), at least
// 13 px from the screen edges, no arrow (B11). Closes when it loses keyboard focus.
// Opens and closes with PopupMotion (`motion`): taskbar flyouts rise from behind the taskbar.
// Material: Acrylic (translucent fill over KWin's blur, light border, shadow). The surface is
// larger than the flyout by the shadow's margin (cut at the screen edges) and, for the taskbar
// motion, reaches down to the taskbar's top edge so that the flyout is clipped there while it
// moves; its input region is the flyout only. KWin's blur follows the moving flyout (or its cards,
// `blurItems`) on every frame.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: flyout
    property var targetScreen
    // Horizontal centre the flyout should line up with (screen coordinates), or -1 for "right edge".
    property real anchorX: -1
    // Or the screen x of its left edge (menus that open at the pointer), -1 = use anchorX.
    property real anchorLeft: -1
    property bool rightAligned: anchorX < 0 && anchorLeft < 0
    // Distance above the taskbar (its exclusive zone); menus opened from Start sit higher.
    property int gap: Metrics.flyoutGap
    default property alias content: body.data
    property alias background: material.fill
    property alias material: material
    // Acrylic recipe of the flyout's own background (menu: over the desktop; menu.panel: menus
    // opened over Start or Search, measured on user-win11 160110).
    property bool overPanel: false
    property string recipe: overPanel ? "menu.panel" : "menu"
    // Items whose rounded rectangles get KWin's blur (cards of Quick settings / Notification
    // Center); empty: the flyout's own background when it is visible.
    property var blurItems: []
    property int padding: 4
    // Hover popups (previews, tooltips) must not take the keyboard focus from the active window.
    property bool takesFocus: true
    // PopupMotion kind: taskbar (default), edge, menu, fade or none.
    property string motion: "taskbar"
    property bool shown: false
    // Flyout (without shadow) size.
    readonly property int sheetWidth: Math.max(1, body.childrenRect.width + 2 * padding)
    readonly property int sheetHeight: Math.max(1, body.childrenRect.height + 2 * padding)
    // Shadow room on each side, cut where the screen ends.
    readonly property int shadowMargin: Metrics.tok((recipe.startsWith("menu") ? "menu" : "popup") + ".shadow.margin", 28)
    readonly property real sheetX: {
        if (rightAligned || !targetScreen) return targetScreen ? targetScreen.width - Metrics.flyoutEdge - sheetWidth : Metrics.flyoutEdge
        const x = Math.round(anchorLeft >= 0 ? anchorLeft : anchorX - sheetWidth / 2)
        return Math.max(Metrics.flyoutEdge, Math.min(x, targetScreen.width - sheetWidth - Metrics.flyoutEdge))
    }
    readonly property int marginLeft: Math.min(shadowMargin, Math.max(0, Math.floor(sheetX)))
    readonly property int marginRight: targetScreen ? Math.min(shadowMargin, Math.max(0, Math.floor(targetScreen.width - sheetX - sheetWidth))) : 0
    readonly property int marginTop: targetScreen ? Math.min(shadowMargin, Math.max(0, targetScreen.height - Metrics.taskbarHeight - gap - sheetHeight)) : 0
    // Rising from behind the taskbar, the surface reaches down to the taskbar's top edge (gap below
    // the flyout) so that the flyout shows in the gap while it moves, as on Windows.
    readonly property int marginBottom: motion === "taskbar" ? gap : Math.min(shadowMargin, gap)
    readonly property int slideInset: marginBottom

    signal dismissed()

    color: "transparent"
    // Keep the scene (the acrylic's masked layers) while hidden: the next opening draws the last
    // acrylic in its first frame instead of building the layers after it.
    Component.onCompleted: ShellUtil.keepScene(this)
    flags: Qt.FramelessWindowHint
    // Never 0: a layer surface of width 0 must be anchored left and right (protocol error).
    width: marginLeft + sheetWidth + marginRight
    height: marginTop + sheetHeight + marginBottom
    visible: false

    // "dock": KWin types layer surfaces by scope (LayerShellV1Window: unknown scopes are Normal
    // windows), and its scale effect fades and scales Normal windows in when they map; Windows'
    // popups slide in opaque (PopupMotion). A dock is neither scaled nor faded (fadingpopups).
    LayerShell.Window.scope: "dock"
    // Hover popups (tooltips, previews) never take the focus, and KWin keeps the focused layer
    // surface (Start) above the others of its layer: they go one layer up.
    LayerShell.Window.layer: takesFocus ? LayerShell.Window.LayerTop : LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom
                               | (rightAligned ? LayerShell.Window.AnchorRight : LayerShell.Window.AnchorLeft)
    LayerShell.Window.margins.bottom: gap - marginBottom
    LayerShell.Window.margins.right: Metrics.flyoutEdge - marginRight
    LayerShell.Window.margins.left: Math.round(sheetX) - marginLeft
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: takesFocus ? LayerShell.Window.KeyboardInteractivityOnDemand
                                                       : LayerShell.Window.KeyboardInteractivityNone

    // ---- The real acrylic (core/backdrop.h) ----------------------------------------------------
    // Computed from a capture of what is behind the flyout's final place (plus `overWindow`, the
    // shell popup it opens over, e.g. Start under its power menu); the fallback material (fill
    // over KWin's blur) shows until it is ready. Hover previews keep their own look.
    property bool backdropEnabled: takesFocus || recipe === "tooltip"
    property var overWindow: null
    property rect overRect
    property int backdropId: 0
    property int shownId: 0          // kept while closed: the next opening starts with it
    property bool acrylicOn: false
    readonly property real restY: targetScreen ? targetScreen.height - Metrics.taskbarHeight - gap - sheetHeight : 0
    // Where the flyout can be while it moves: down to the taskbar, out to the screen's right edge,
    // or half its height lower (menus).
    readonly property rect backdropArea: !targetScreen ? Qt.rect(0, 0, 0, 0)
        : motion === "taskbar" ? Qt.rect(Math.round(sheetX), restY, sheetWidth, sheetHeight + gap)
        : motion === "edge" ? Qt.rect(Math.round(sheetX), restY, targetScreen.width - Math.round(sheetX), sheetHeight)
        : motion === "menu" ? Qt.rect(Math.round(sheetX), restY, sheetWidth, Math.min(sheetHeight * 1.5, targetScreen.height - Metrics.taskbarHeight - restY))
        : Qt.rect(Math.round(sheetX), restY, sheetWidth, sheetHeight)
    readonly property var acrylics: blurItems.length ? blurItems : (material.fill.visible ? [material] : [])
    function requestBackdrop() {
        if (backdropId !== shownId) Backdrop.release(backdropId)
        backdropId = 0
        if (!backdropEnabled || !ShellSettings.transparency || !targetScreen || acrylics.length === 0) return
        const recipes = []
        for (const a of acrylics) if (recipes.indexOf(a.backdropRecipe) < 0) recipes.push(a.backdropRecipe)
        backdropId = Backdrop.request(flyout, backdropArea, WallpaperSource.image !== "" ? WallpaperSource.image : WallpaperSource.color,
                                      recipes, overWindow, overRect)
        if (shownId > 0) { showBackdrop(shownId); acrylicOn = true; ShellUtil.clearBlur(flyout) }
    }
    function showBackdrop(id) {
        for (const a of acrylics) {
            const p = a.mapToItem(sheet, 0, 0)
            a.backdrop.area = Backdrop.area(id)
            a.backdrop.origin = Qt.point(Math.round(sheetX) + p.x, restY + p.y)
            a.backdrop.shift = motionCtl.shift
            a.backdrop.source = "image://backdrop/" + id + "/" + a.backdropRecipe
        }
    }
    function dropBackdrop() {
        Backdrop.release(backdropId)
        Backdrop.release(shownId)
        backdropId = 0; shownId = 0
        acrylicOn = false
        for (const a of acrylics) a.backdrop.source = ""
    }
    Connections {
        target: Backdrop
        function onReady(id, ms) {
            if (id !== flyout.backdropId || !flyout.shown) return
            flyout.showBackdrop(id)
            if (flyout.shownId !== id) Backdrop.release(flyout.shownId)
            flyout.shownId = id
            if (!flyout.acrylicOn) acrylicTimer.restart()
        }
    }
    Connections { target: ShellSettings; function onTransparencyChanged() { if (!ShellSettings.transparency) flyout.dropBackdrop() } }
    Timer { id: acrylicTimer; interval: 100; onTriggered: { flyout.acrylicOn = true; ShellUtil.clearBlur(flyout) } }
    // Cards that change size while open (calendar, notifications): a new capture for the new area.
    Timer { id: recapture; interval: 50; onTriggered: if (flyout.shown && flyout.backdropId) flyout.requestBackdrop() }

    function updateBlur() {
        if (!visible) return
        if (!ShellSettings.transparency || acrylicOn) { ShellUtil.clearBlur(flyout); return }
        ShellUtil.setBlurItems(flyout, blurItems.length ? blurItems : (material.fill.visible ? [material] : []), Metrics.flyoutRadius)
    }
    function open() {
        if (targetScreen) ShellUtil.placeOnScreen(flyout, targetScreen.name)
        const already = shown && visible   // re-anchored while open (previews): no new entrance
        shown = true
        if (!already) requestBackdrop()
        if (!already) motionCtl.enter()
        visible = true
        ShellUtil.setInputItems(flyout, [inputArea])
        updateBlur()
        if (takesFocus) requestActivate()
    }
    function close() { if (visible && shown) { shown = false; motionCtl.leave() } }
    function toggle() { shown ? close() : open() }

    onActiveChanged: if (takesFocus && !active && shown) close()
    onWidthChanged: if (visible) { ShellUtil.setInputItems(flyout, [inputArea]); updateBlur() }
    onHeightChanged: if (visible) { ShellUtil.setInputItems(flyout, [inputArea]); updateBlur() }
    onBlurItemsChanged: updateBlur()

    PopupMotion {
        id: motionCtl
        kind: flyout.motion
        target: sheet
        travel: flyout.motion === "edge" ? flyout.sheetWidth + (flyout.rightAligned ? Metrics.flyoutEdge : 0)
                                         : flyout.motion === "taskbar" ? flyout.sheetHeight + flyout.gap : flyout.sheetHeight
        onGone: { flyout.visible = false; ShellUtil.clearBlur(flyout); flyout.dismissed() }
    }
    Connections { target: motionCtl.shift; function onYChanged() { flyout.updateBlur() } function onXChanged() { flyout.updateBlur() } }
    // Cards that change size (calendar collapsing, notifications arriving) move the blur too.
    Timer { id: settle; interval: 0; onTriggered: flyout.updateBlur() }
    onSheetHeightChanged: { settle.restart(); if (shown && backdropId) recapture.restart() }

    Item { id: inputArea; x: flyout.marginLeft; y: flyout.marginTop; width: flyout.sheetWidth; height: flyout.sheetHeight }
    Item {
        id: sheet
        x: flyout.marginLeft; y: flyout.marginTop
        width: flyout.sheetWidth; height: flyout.sheetHeight
        transform: motionCtl.shift
        Acrylic {
            id: material
            anchors.fill: parent
            recipe: flyout.recipe
            shadowKind: flyout.recipe.startsWith("menu") ? "menu" : "popup"
        }
        Item {
            id: body
            x: flyout.padding; y: flyout.padding
            width: childrenRect.width; height: childrenRect.height
            focus: true
            Keys.onEscapePressed: flyout.close()
        }
        AcrylicOutline { acrylic: material; visible: material.fill.visible }
    }
}

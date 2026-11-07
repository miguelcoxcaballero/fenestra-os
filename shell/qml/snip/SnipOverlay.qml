// SPDX-License-Identifier: GPL-3.0-or-later
// Snipping overlay of one output (Q04): the frozen picture (Snip, CaptureWorkspace) dimmed, the
// selection undimmed with a white border, the toolbar on the first output. Layer-shell OVERLAY,
// over the whole output, exclusive keyboard focus (Esc cancels).
import QtQuick
import QtQuick.Shapes
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: ov
    property var targetScreen
    property bool hasToolbar: false
    // Transparent: until the frozen picture is drawn the live screen (the same pixels) shows through.
    color: "transparent"
    visible: false
    // "dock": KWin's scale effect animates surfaces with other names as opening apps (scale + fade),
    // which made the overlay look like an app starting. Windows has no such motion (see `dimLevel`).
    LayerShell.Window.scope: "dock"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityExclusive

    readonly property real originX: targetScreen ? targetScreen.virtualX : 0
    readonly property real originY: targetScreen ? targetScreen.virtualY : 0

    // Selection state, in this surface's coordinates.
    property bool selecting: false          // rectangle / freeform drag in progress
    property point pressAt
    property rect sel: Qt.rect(0, 0, 0, 0)  // rectangle mode
    property var lasso: []                  // freeform mode: points
    property int hoverRow: -1               // window mode: WindowsModel row under the pointer
    property rect hoverRect: Qt.rect(0, 0, 0, 0)
    readonly property bool hoverScreen: Snip.mode === "screen" && area.containsMouse

    function reset() {
        selecting = false; sel = Qt.rect(0, 0, 0, 0); lasso = []
        hoverRow = -1; hoverRect = Qt.rect(0, 0, 0, 0)
        if (toolbarLoader.item) toolbarLoader.item.tipIndex = -1
    }
    // Motion, recorded on Windows 11 (26100, 2026-11-07, reference-shots/motion-snip-2026-11-07):
    // the toolbar and the frozen screen appear at once, already in place; only the dim fades in
    // (to black at 60 %: 238 -> 95) in ~250 ms, decelerating. Esc fades the dim out the same way
    // (~250-300 ms) with the toolbar still shown, then everything goes. A capture closes at once.
    property real dimLevel: 0
    property bool instantClose: false
    property string shot: ""
    NumberAnimation { id: dimIn; target: ov; property: "dimLevel"; to: 1; duration: Motion.reduced ? 0 : 250
                      easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] }
    SequentialAnimation {
        id: dimOut
        NumberAnimation { target: ov; property: "dimLevel"; to: 0; duration: Motion.reduced ? 0 : 280
                          easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] }
        ScriptAction { script: { ov.visible = false; ov.shot = ""; ov.reset() } }
    }
    function open() {
        if (targetScreen) ShellUtil.placeOnScreen(ov, targetScreen.name)
        dimOut.stop()
        reset()
        instantClose = false
        shot = targetScreen ? "image://snip/" + encodeURIComponent(targetScreen.name) + "/" + Snip.serial : ""
        dimLevel = 0
        visible = true
        requestActivate()
        keys.forceActiveFocus()
        dimIn.restart()
    }
    function close() {
        dimIn.stop()
        if (instantClose || !visible) { dimOut.stop(); visible = false; shot = ""; reset(); return }
        dimOut.restart()
    }
    Connections {
        target: Snip
        function onActiveChanged() { Snip.active ? ov.open() : ov.close() }
        function onModeChanged() { ov.reset() }
    }

    // ---- what is undimmed: the hole of the dim layer, as a closed polygon ----
    readonly property var hole: {
        const r = Snip.mode === "rectangle" && sel.width > 0 && sel.height > 0 ? sel
                : Snip.mode === "window" && hoverRow >= 0 ? hoverRect
                : hoverScreen ? Qt.rect(0, 0, width, height) : null
        if (r) return [Qt.point(r.x, r.y), Qt.point(r.x + r.width, r.y), Qt.point(r.x + r.width, r.y + r.height),
                       Qt.point(r.x, r.y + r.height), Qt.point(r.x, r.y)]
        if (Snip.mode === "freeform" && lasso.length > 2) return lasso.concat([lasso[0]])
        return []
    }
    readonly property rect holeRect: {
        if (Snip.mode === "rectangle") return sel
        if (Snip.mode === "window" && hoverRow >= 0) return hoverRect
        if (hoverScreen) return Qt.rect(0, 0, width, height)
        return Qt.rect(0, 0, 0, 0)
    }

    // ---- selection logic ----
    function clampX(x) { return Math.max(0, Math.min(width, x)) }
    function clampY(y) { return Math.max(0, Math.min(height, y)) }
    function toGlobal(r) { return Qt.rect(r.x + originX, r.y + originY, r.width, r.height) }

    // Window mode: topmost window under (x, y) — stacking order from KWin when known, else the
    // active window, else the smallest one. Roles: 260 active, 261 minimized, 266 geometry, 267 stacking.
    function windowAt(x, y) {
        const gx = x + originX, gy = y + originY
        let best = -1, key = null
        for (let i = 0; i < WindowsModel.count; ++i) {
            const idx = WindowsModel.index(i, 0)
            if (WindowsModel.data(idx, 261)) continue
            const g = WindowsModel.data(idx, 266)
            if (!g || g.width <= 0 || gx < g.x || gy < g.y || gx >= g.x + g.width || gy >= g.y + g.height) continue
            const k = [WindowsModel.data(idx, 267), WindowsModel.data(idx, 260) ? 1 : 0, -g.width * g.height]
            if (!key || k[0] > key[0] || (k[0] === key[0] && (k[1] > key[1] || (k[1] === key[1] && k[2] > key[2])))) {
                best = i; key = k
            }
        }
        return best
    }
    function updateHover(x, y) {
        const row = windowAt(x, y)
        hoverRow = row
        if (row < 0) { hoverRect = Qt.rect(0, 0, 0, 0); return }
        const g = WindowsModel.data(WindowsModel.index(row, 0), 266)
        hoverRect = Qt.rect(g.x - originX, g.y - originY, g.width, g.height)
    }
    function commitRect() {
        const r = sel
        selecting = false
        if (r.width < 2 || r.height < 2) { sel = Qt.rect(0, 0, 0, 0); return false }
        instantClose = true
        return Snip.captureRect(toGlobal(r))
    }
    function commitLasso() {
        const pts = lasso
        selecting = false
        if (pts.length < 3) { lasso = []; return false }
        const xy = []
        for (const p of pts) xy.push(p.x + originX, p.y + originY)
        instantClose = true
        return Snip.captureFreeform(xy)
    }
    function commitWindow() {
        if (hoverRow < 0) return false
        const g = WindowsModel.data(WindowsModel.index(hoverRow, 0), 266)
        instantClose = true
        return Snip.captureRect(Qt.rect(g.x, g.y, g.width, g.height))
    }

    // Test probe hooks (tests/shell-kwin/session.sh): the same paths as the pointer.
    function testSelect(x, y, w, h, commit) {
        Snip.mode = "rectangle"
        sel = Qt.rect(x, y, w, h); selecting = !commit
        return commit ? commitRect() : true
    }
    function testHover(x, y) { Snip.mode = "window"; updateHover(x, y); return hoverRow }
    function testClickWindow() { return commitWindow() }
    function testLasso(points, commit) {
        Snip.mode = "freeform"
        lasso = points.map(p => Qt.point(p[0], p[1])); selecting = !commit
        return commit ? commitLasso() : true
    }

    // ---- drawing ----
    Image {
        anchors.fill: parent
        source: ov.shot   // kept while the dim fades out after Esc
        cache: false
        smooth: false
    }
    Shape {
        anchors.fill: parent
        ShapePath {
            fillColor: Qt.rgba(0, 0, 0, Metrics.snipDim * ov.dimLevel)
            strokeWidth: -1
            fillRule: ShapePath.OddEvenFill
            PathMultiline {
                paths: {
                    const outer = [Qt.point(0, 0), Qt.point(ov.width, 0), Qt.point(ov.width, ov.height), Qt.point(0, ov.height), Qt.point(0, 0)]
                    return ov.hole.length ? [outer, ov.hole] : [outer]
                }
            }
        }
    }
    // Window and screen: a solid 1 px line just outside the selection (never in the picture); a
    // rectangle being drawn: the same line dashed 4 on, 3 off (snip_overlay.*.rectangle_in_progress).
    Rectangle {
        readonly property int bw: Metrics.snipBorderWidth
        visible: ov.holeRect.width > 0 && ov.holeRect.height > 0 && Snip.mode !== "rectangle"
        x: ov.holeRect.x - bw; y: ov.holeRect.y - bw
        width: ov.holeRect.width + 2 * bw; height: ov.holeRect.height + 2 * bw
        color: "transparent"
        border.color: Metrics.snipBorderColor
        border.width: bw
    }
    Shape {
        anchors.fill: parent
        visible: ov.holeRect.width > 0 && ov.holeRect.height > 0 && Snip.mode === "rectangle"
        ShapePath {
            id: dashed
            readonly property real o: Metrics.snipBorderWidth / 2
            readonly property rect r: ov.holeRect
            strokeColor: Metrics.snipBorderColor
            strokeWidth: Metrics.snipBorderWidth
            fillColor: "transparent"
            strokeStyle: ShapePath.DashLine
            dashPattern: [Metrics.n("snip.dash", 4), Metrics.n("snip.dash.gap", 3)]
            capStyle: ShapePath.FlatCap
            PathPolyline { path: [Qt.point(dashed.r.x - dashed.o, dashed.r.y - dashed.o), Qt.point(dashed.r.x + dashed.r.width + dashed.o, dashed.r.y - dashed.o), Qt.point(dashed.r.x + dashed.r.width + dashed.o, dashed.r.y + dashed.r.height + dashed.o),
                                  Qt.point(dashed.r.x - dashed.o, dashed.r.y + dashed.r.height + dashed.o), Qt.point(dashed.r.x - dashed.o, dashed.r.y - dashed.o)] }
        }
    }
    // Freeform: the lasso line.
    Shape {
        anchors.fill: parent
        visible: Snip.mode === "freeform" && ov.lasso.length > 1
        ShapePath {
            strokeColor: Metrics.snipBorderColor
            strokeWidth: Metrics.snipBorderWidth
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            capStyle: ShapePath.RoundCap
            PathPolyline { path: ov.selecting ? ov.lasso : ov.lasso.concat(ov.lasso.length ? [ov.lasso[0]] : []) }
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Snip.mode === "rectangle" || Snip.mode === "freeform" ? Qt.CrossCursor : Qt.ArrowCursor
        onPressed: (m) => {
            ov.pressAt = Qt.point(m.x, m.y)
            if (Snip.mode === "rectangle") { ov.selecting = true; ov.sel = Qt.rect(m.x, m.y, 0, 0) }
            else if (Snip.mode === "freeform") { ov.selecting = true; ov.lasso = [Qt.point(m.x, m.y)] }
        }
        onPositionChanged: (m) => {
            const x = ov.clampX(m.x), y = ov.clampY(m.y)
            if (Snip.mode === "window" && !pressed) ov.updateHover(x, y)
            if (!ov.selecting) return
            if (Snip.mode === "rectangle") {
                ov.sel = Qt.rect(Math.min(ov.pressAt.x, x), Math.min(ov.pressAt.y, y),
                                 Math.abs(x - ov.pressAt.x), Math.abs(y - ov.pressAt.y))
            } else if (Snip.mode === "freeform") {
                const last = ov.lasso[ov.lasso.length - 1]
                if (Math.abs(last.x - x) + Math.abs(last.y - y) >= 2) ov.lasso = ov.lasso.concat([Qt.point(x, y)])
            }
        }
        onReleased: {
            if (Snip.mode === "rectangle" && ov.selecting) ov.commitRect()
            else if (Snip.mode === "freeform" && ov.selecting) ov.commitLasso()
        }
        onClicked: {
            if (Snip.mode === "window") ov.commitWindow()
            else if (Snip.mode === "screen" && ov.targetScreen) { ov.instantClose = true; Snip.captureScreen(ov.targetScreen.name) }
        }
    }

    Loader {
        id: toolbarLoader
        active: ov.hasToolbar
        x: Math.round((ov.width - width) / 2)
        y: Metrics.snipToolbarTop
        sourceComponent: SnipToolbar { }
    }
    property alias toolbar: toolbarLoader.item

    Item {
        id: keys
        focus: true
        Keys.onPressed: (e) => {
            if (e.key === Qt.Key_Escape) Snip.cancel()
            e.accepted = true
        }
    }
}

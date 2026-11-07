// SPDX-License-Identifier: GPL-3.0-or-later
// Snap Layouts (W03): Super+Z shows the layouts under the active window's Maximize button (or at the
// top of the screen without one); clicking a zone puts the active window there (KWin scripting).
// Edge and corner snapping by dragging is KWin's quick tiling. dark-100-27-snap-layouts: a 344 × 244
// panel, eight 98 × 64 layouts in rows of three, 12 px apart; zones 4 px apart with a 1 px outline.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: snap
    property var targetScreen
    readonly property int pad: Metrics.n("snap.padding", 13)
    readonly property int cellW: Metrics.n("snap.layout.width", 98)
    readonly property int cellH: Metrics.n("snap.layout.height", 64)
    readonly property int gap: Metrics.n("snap.layout.gap", 12)
    property point at: Qt.point(-1, -1)        // top-left on the screen, or (-1, -1) = top centre
    color: "transparent"
    visible: false
    width: Metrics.n("snap.width", 344)
    height: Metrics.n("snap.height", 244)
    LayerShell.Window.scope: "fenestra-snap"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: at.x < 0 ? LayerShell.Window.AnchorTop : (LayerShell.Window.AnchorTop | LayerShell.Window.AnchorLeft)
    LayerShell.Window.margins.top: at.x < 0 ? 12 : at.y
    LayerShell.Window.margins.left: at.x < 0 ? 0 : at.x
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand
    onActiveChanged: if (!active && visible) visible = false

    // Zones as fractions of the work area: [x, y, w, h], in the reference's order.
    readonly property var layouts: [
        [[0, 0, 0.5, 1], [0.5, 0, 0.5, 1]],
        [[0, 0, 2 / 3, 1], [2 / 3, 0, 1 / 3, 1]],
        [[0, 0, 0.5, 1], [0.5, 0, 0.5, 1]],
        [[0, 0, 2 / 3, 1], [2 / 3, 0, 1 / 3, 1]],
        [[0, 0, 1 / 3, 1], [1 / 3, 0, 1 / 3, 1], [2 / 3, 0, 1 / 3, 1]],
        [[0, 0, 0.5, 1], [0.5, 0, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
        [[0, 0, 0.5, 0.5], [0.5, 0, 0.5, 0.5], [0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
        [[0, 0, 0.25, 1], [0.25, 0, 0.5, 1], [0.75, 0, 0.25, 1]],
    ]
    // Under the Maximize button of the active window: its centre is 70 px left of the frame's right
    // edge (45 px buttons, 1 px apart, 1 px border); the panel starts 31 px below the frame's top.
    function placeUnderMaximize() {
        at = Qt.point(-1, -1)
        if (!targetScreen) return
        for (let i = 0; i < WindowsModel.count; ++i) {
            const ix = WindowsModel.index(i, 0)
            if (!WindowsModel.data(ix, 260) || WindowsModel.data(ix, 262)) continue     // active, not maximized
            const g = WindowsModel.data(ix, 266)
            const sx = targetScreen.virtualX, sy = targetScreen.virtualY
            const x = Math.round(g.x + g.width - 2 * Metrics.windowButtonWidth + 20 - width / 2) - sx
            const y = g.y + 2 + Metrics.windowButtonHeight - sy
            if (y < 0 || y + height > targetScreen.height) return
            at = Qt.point(Math.max(12, Math.min(x, targetScreen.width - width - 12)), y)
            return
        }
    }
    function open() {
        if (targetScreen) ShellUtil.placeOnScreen(snap, targetScreen.name)
        placeUnderMaximize()
        visible = true
        requestActivate()
        snapMotion.enter()
    }
    // No frames of it in the reference: fades in (PopupMotion "fade", design/motion.json).
    PopupMotion { id: snapMotion; kind: "fade"; target: snap.contentItem }
    function choose(zone) {
        visible = false
        KWinIntegration.placeActiveWindow(Qt.rect(zone[0], zone[1], zone[2], zone[3]))
    }

    Rectangle {
        anchors.fill: parent
        radius: Metrics.flyoutRadius
        color: Metrics.col("panel.fill.alt")
        border.color: Metrics.col("panel.border")
        Keys.onEscapePressed: snap.visible = false
        focus: true
    }
    Grid {
        x: snap.pad + 1; y: snap.pad + 1; columns: 3; spacing: snap.gap
        Repeater {
            model: snap.layouts
            delegate: Item {
                id: layout
                required property var modelData
                width: snap.cellW; height: snap.cellH
                readonly property int zgap: Tokens.px("snap.zone.gap", 4)
                Repeater {
                    model: layout.modelData
                    delegate: Rectangle {
                        required property var modelData
                        // Zone edges on the 4 px grid: a zone ends 4 px before the next one starts.
                        readonly property real x0: modelData[0] === 0 ? 0 : Math.round(modelData[0] * (snap.cellW + layout.zgap))
                        readonly property real y0: modelData[1] === 0 ? 0 : Math.round(modelData[1] * (snap.cellH + layout.zgap))
                        readonly property real x1: modelData[0] + modelData[2] >= 1 ? snap.cellW : Math.round((modelData[0] + modelData[2]) * (snap.cellW + layout.zgap)) - layout.zgap
                        readonly property real y1: modelData[1] + modelData[3] >= 1 ? snap.cellH : Math.round((modelData[1] + modelData[3]) * (snap.cellH + layout.zgap)) - layout.zgap
                        x: x0; y: y0; width: x1 - x0; height: y1 - y0
                        radius: Metrics.controlRadius
                        color: zm.containsMouse ? Theme.accentFill : Metrics.col("snap.zone.fill")
                        border.color: zm.containsMouse ? Theme.accentFill : Metrics.col("snap.zone.border")
                        MouseArea { id: zm; anchors.fill: parent; hoverEnabled: true; onClicked: snap.choose(modelData) }
                    }
                }
            }
        }
    }
}

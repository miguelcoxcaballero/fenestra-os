// SPDX-License-Identifier: GPL-3.0-or-later
// Snap Layouts (W03): Super+Z shows the layouts at the top of the screen; clicking a zone puts the
// active window there (KWin scripting). Edge and corner snapping by dragging is KWin's quick tiling.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: snap
    property var targetScreen
    color: "transparent"
    visible: false
    width: layoutsRow.width + 2 * 12 + 2
    height: 82 + 2 * 12 + 2
    LayerShell.Window.scope: "fenestra-snap"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop
    LayerShell.Window.margins.top: 12
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand
    onActiveChanged: if (!active && visible) visible = false

    // Zones as fractions of the work area: [x, y, w, h].
    readonly property var layouts: [
        [[0, 0, 0.5, 1], [0.5, 0, 0.5, 1]],
        [[0, 0, 2 / 3, 1], [2 / 3, 0, 1 / 3, 1]],
        [[0, 0, 1 / 3, 1], [1 / 3, 0, 1 / 3, 1], [2 / 3, 0, 1 / 3, 1]],
        [[0, 0, 0.5, 1], [0.5, 0, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
        [[0, 0, 0.5, 0.5], [0.5, 0, 0.5, 0.5], [0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
        [[0, 0, 0.25, 1], [0.25, 0, 0.5, 1], [0.75, 0, 0.25, 1]],
    ]
    function open() {
        if (targetScreen) ShellUtil.placeOnScreen(snap, targetScreen.name)
        visible = true
        requestActivate()
    }
    function choose(zone) {
        visible = false
        KWinIntegration.placeActiveWindow(Qt.rect(zone[0], zone[1], zone[2], zone[3]))
    }

    Rectangle {
        anchors.fill: parent
        radius: Metrics.flyoutRadius
        color: Theme.flyout
        border.color: Theme.flyoutBorder
        Keys.onEscapePressed: snap.visible = false
        focus: true
    }
    Row {
        id: layoutsRow
        x: 13; y: 13; spacing: 12
        Repeater {
            model: snap.layouts
            delegate: Item {
                required property var modelData
                width: 120; height: 82
                Repeater {
                    model: modelData
                    delegate: Rectangle {
                        required property var modelData
                        readonly property int gap: Tokens.px("snap.zone.gap", 4)
                        x: modelData[0] * 120 + gap / 2; y: modelData[1] * 82 + gap / 2
                        width: modelData[2] * 120 - gap; height: modelData[3] * 82 - gap
                        radius: 4
                        color: zm.containsMouse ? Theme.accentFill : (Theme.dark ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.08))
                        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.18) : Qt.rgba(0, 0, 0, 0.12)
                        MouseArea { id: zm; anchors.fill: parent; hoverEnabled: true; onClicked: snap.choose(modelData) }
                    }
                }
            }
        }
    }
}

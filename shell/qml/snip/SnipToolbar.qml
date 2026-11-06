// SPDX-License-Identifier: GPL-3.0-or-later
// The snipping toolbar (snip_toolbar in design/reference/measurements.json): top centre of the first
// output, 48 px tall fill with a 1 px outline, radius 8, 8 px padding. The mode button (56 × 32,
// current mode's glyph and a chevron) opens the mode menu (125 px wide, 35 px rows: Rectangle,
// Window, Full screen, Freeform); a 1 × 24 separator 8 px either side; Close. Tooltips 32 px tall,
// 44 px below the bar's top. (No Snapshot / Video switch, quick markup, colour picker or text
// extractor: the shell does not record the screen nor edit the picture.)
import QtQuick
import Fenestra.Shell

Item {
    id: bar
    // Index of the button whose tooltip shows (-1 none): 0 mode, 1 close. Set on hover after a
    // delay, or by tests.
    property int tipIndex: -1
    property bool menuOpen: false
    readonly property var modes: [
        { mode: "rectangle", icon: "snip-rectangle", label: "Rectangle" },
        { mode: "window", icon: "snip-window", label: "Window" },
        { mode: "screen", icon: "snip-screen", label: "Full screen" },
        { mode: "freeform", icon: "snip-freeform", label: "Freeform" },
    ]
    readonly property var current: modes.find(m => m.mode === Snip.mode) || modes[0]
    width: frame.width
    height: frame.height

    // Soft shadow: rounded rings of decreasing alpha (no shader effects with the software renderer).
    Repeater {
        model: Metrics.snipToolbarShadow
        delegate: Rectangle {
            required property int index
            readonly property int grow: Metrics.snipToolbarShadow - index
            x: -grow; y: -grow + 2
            width: frame.width + 2 * grow; height: frame.height + 2 * grow
            radius: Metrics.snipToolbarRadius + grow
            color: Qt.rgba(0, 0, 0, (Theme.dark ? 0.05 : 0.025) * (index + 1) / Metrics.snipToolbarShadow)
        }
    }
    Rectangle {
        id: frame
        width: row.width + 2 * Metrics.snipToolbarPadding + 2
        height: Metrics.snipButtonHeight + 2 * Metrics.snipToolbarPadding + 2
        radius: Metrics.snipToolbarRadius
        // Opaque: the picture under it is frozen, nothing to blur live.
        color: Metrics.col("snip.toolbar.fill")
        border.color: Metrics.col("snip.toolbar.border")
        border.width: 1
        Row {
            id: row
            x: Metrics.snipToolbarPadding + 1; y: Metrics.snipToolbarPadding + 1
            spacing: Metrics.snipButtonSpacing
            SnipButton {
                id: modeButton
                icon: bar.current.icon
                chevron: true
                checked: bar.menuOpen
                tip: "Snipping area"
                onClicked: { bar.menuOpen = !bar.menuOpen; bar.hover(-1) }
                onHoveredChanged: bar.hover(hovered && !bar.menuOpen ? 0 : -1)
            }
            Item {
                width: 1; height: Metrics.snipButtonHeight
                Rectangle {
                    anchors.centerIn: parent
                    width: 1; height: Metrics.snipSeparatorHeight
                    color: Metrics.col("snip.separator")
                }
            }
            SnipButton {
                id: closeButton
                icon: "snip-close"
                tip: "Close (Esc)"
                onClicked: Snip.cancel()
                onHoveredChanged: bar.hover(hovered ? 1 : -1)
            }
        }
    }

    property int pendingTip: -1
    function hover(i) {
        pendingTip = i
        if (i < 0) { tipTimer.stop(); tipIndex = -1 }
        else if (tipIndex >= 0) tipIndex = i
        else tipTimer.restart()
    }
    Timer { id: tipTimer; interval: Metrics.snipTooltipDelay; onTriggered: bar.tipIndex = bar.pendingTip }

    function buttonAt(i) { return i === 0 ? modeButton : closeButton }
    Rectangle {
        id: tooltip
        visible: bar.tipIndex >= 0 && !bar.menuOpen
        readonly property var target: bar.tipIndex >= 0 ? bar.buttonAt(bar.tipIndex) : null
        width: tipText.implicitWidth + 20; height: Metrics.n("snip.tooltip.height", 32)
        x: target ? Math.round(target.mapToItem(bar, 0, 0).x + (target.width - width) / 2) : 0
        y: Metrics.n("snip.tooltip.y", 44)
        radius: Metrics.controlRadius
        color: Metrics.col("snip.tooltip")
        border.color: Theme.dark ? "#191919" : "#e5e5e5"
        Text {
            id: tipText
            anchors.centerIn: parent
            text: tooltip.target ? Strings.tr(tooltip.target.tip) : ""
            color: Theme.text
            font.family: Metrics.fontFamily
            font.pixelSize: Metrics.fontCaption
        }
    }
    // Mode menu: opens over the bar at the mode button (reference: x 887, y 15 for a bar at y 12).
    Rectangle {
        id: menu
        visible: bar.menuOpen
        x: modeButton.mapToItem(bar, 0, 0).x; y: 3
        width: Metrics.n("snip.menu.width", 125); height: menuColumn.height + 8
        radius: Metrics.snipToolbarRadius
        color: Metrics.col("snip.tooltip")
        border.color: Theme.dark ? "#191919" : "#e5e5e5"
        Column {
            id: menuColumn
            x: 4; y: 4; width: parent.width - 8
            Repeater {
                model: bar.modes
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool selected: Snip.mode === modelData.mode
                    width: menuColumn.width; height: Metrics.n("snip.menu.row", 35)
                    radius: Metrics.controlRadius
                    color: selected || mm.containsMouse ? (Theme.dark ? "#383838" : "#f0f0f0") : "transparent"
                    Rectangle { visible: parent.selected; x: 0; anchors.verticalCenter: parent.verticalCenter
                                width: 3; height: 16; radius: 1.5; color: Theme.accentText }
                    Image {
                        x: 12; anchors.verticalCenter: parent.verticalCenter
                        width: Metrics.snipIcon; height: Metrics.snipIcon
                        sourceSize: Qt.size(Metrics.snipIcon * Screen.devicePixelRatio, Metrics.snipIcon * Screen.devicePixelRatio)
                        source: modeButton.glyph(modelData.icon)
                    }
                    Text { x: 40; anchors.verticalCenter: parent.verticalCenter; text: Strings.tr(modelData.label)
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: mm; anchors.fill: parent; hoverEnabled: true
                                onClicked: { Snip.mode = modelData.mode; bar.menuOpen = false } }
                    Accessible.role: Accessible.MenuItem
                    Accessible.name: Strings.tr(modelData.label)
                }
            }
        }
    }
}

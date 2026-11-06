// SPDX-License-Identifier: GPL-3.0-or-later
// The snipping toolbar: top centre of the first output, the four selection modes, a separator and
// Close. (No Snapshot / Video switch: recording the screen is not implemented in the shell.)
import QtQuick
import Fenestra.Shell

Item {
    id: bar
    // Index of the button whose tooltip shows (-1 none); set on hover after a delay, or by tests.
    property int tipIndex: -1
    readonly property var modes: [
        { mode: "rectangle", icon: "snip-rectangle", tip: "Rectangle mode" },
        { mode: "window", icon: "snip-window", tip: "Window mode" },
        { mode: "screen", icon: "snip-screen", tip: "Full screen mode" },
        { mode: "freeform", icon: "snip-freeform", tip: "Freeform mode" },
    ]
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
        width: row.width + 2 * Metrics.snipToolbarPadding
        height: row.height + 2 * Metrics.snipToolbarPadding
        radius: Metrics.snipToolbarRadius
        // Mica-like: the opaque acrylic tint (the picture under it is frozen, nothing to blur live).
        color: Theme.acrylic
        border.color: Theme.flyoutBorder
        border.width: 1
        Row {
            id: row
            x: Metrics.snipToolbarPadding; y: Metrics.snipToolbarPadding
            spacing: Metrics.snipButtonSpacing
            Repeater {
                id: modeButtons
                model: bar.modes
                delegate: SnipButton {
                    required property var modelData
                    required property int index
                    icon: modelData.icon
                    tip: modelData.tip
                    checked: Snip.mode === modelData.mode
                    onClicked: Snip.mode = modelData.mode
                    onHoveredChanged: bar.hover(hovered ? index : -1)
                }
            }
            Item {
                width: 1 + 2 * Metrics.snipButtonSpacing; height: Metrics.snipButtonHeight
                Rectangle {
                    anchors.centerIn: parent
                    width: 1; height: Metrics.snipSeparatorHeight
                    color: Theme.separator
                }
            }
            SnipButton {
                id: closeButton
                icon: "snip-close"
                tip: "Close"
                onClicked: Snip.cancel()
                onHoveredChanged: bar.hover(hovered ? bar.modes.length : -1)
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

    function buttonAt(i) { return i < modes.length ? modeButtons.itemAt(i) : closeButton }
    Rectangle {
        id: tooltip
        visible: bar.tipIndex >= 0
        readonly property var target: bar.tipIndex >= 0 ? bar.buttonAt(bar.tipIndex) : null
        width: tipText.implicitWidth + 16; height: tipText.implicitHeight + 12
        x: target ? target.mapToItem(bar, 0, 0).x + (target.width - width) / 2 : 0
        y: frame.height + 6
        radius: Metrics.controlRadius
        color: Theme.acrylic
        border.color: Theme.flyoutBorder
        Text {
            id: tipText
            anchors.centerIn: parent
            text: tooltip.target ? Strings.tr(tooltip.target.tip) : ""
            color: Theme.text
            font.family: Metrics.fontFamily
            font.pixelSize: Metrics.fontCaption
        }
    }
}

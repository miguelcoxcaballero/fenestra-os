// SPDX-License-Identifier: GPL-3.0-or-later
// Start section header: 14 px semibold title and an optional 24 px button ("All ›", "‹ Back")
// whose right edge is start.header.inset from the panel edge (design/tokens.json).
import QtQuick
import Fenestra.Shell

Item {
    id: header
    property string title
    property string action
    // Chevron side of the button: "right" (All ›) or "left" (‹ Back).
    property string chevron: "right"
    signal actionClicked()
    height: Metrics.tok("start.header.button.height", 24)
    Text {
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: Metrics.tok("start.text.offset", 0)
        text: header.title
        color: Theme.text
        font.family: Metrics.fontFamily
        font.pixelSize: Metrics.fontBody
        font.weight: Font.DemiBold
    }
    Rectangle {
        id: button
        visible: header.action !== ""
        readonly property int pad: Metrics.tok("start.header.button.padding", 8)
        anchors.right: parent.right
        width: actionRow.implicitWidth + 2 * pad - (header.chevron === "right" ? 2 : 0)
        height: parent.height
        radius: Metrics.controlRadius
        color: am.containsMouse ? Metrics.themed("start.hover") : Metrics.themed("start.button.fill")
        border.color: Metrics.themed("start.button.border")
        Row {
            id: actionRow
            x: button.pad + 1 - (header.chevron === "left" ? 2 : 0)
            anchors.verticalCenter: parent.verticalCenter
            layoutDirection: header.chevron === "left" ? Qt.RightToLeft : Qt.LeftToRight
            spacing: 9
            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: Metrics.tok("start.text.offset", 0) - 1
                text: header.action; color: Theme.text
                font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
            }
            Canvas {
                // 5 × 8 chevron in a 12 px box, 1 px stroke.
                width: 12; height: 12
                anchors.verticalCenter: parent.verticalCenter
                property color ink: Metrics.themed("start.chevron")
                property string dir: header.chevron
                onInkChanged: requestPaint()
                onDirChanged: requestPaint()
                onPaint: {
                    const c = getContext("2d")
                    c.reset()
                    c.strokeStyle = ink; c.lineWidth = 1.2
                    c.beginPath()
                    if (header.chevron === "right") { c.moveTo(4, 2); c.lineTo(8, 6); c.lineTo(4, 10) }
                    else { c.moveTo(8, 2); c.lineTo(4, 6); c.lineTo(8, 10) }
                    c.stroke()
                }
            }
        }
        MouseArea { id: am; anchors.fill: parent; hoverEnabled: true; onClicked: header.actionClicked() }
    }
}

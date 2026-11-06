// SPDX-License-Identifier: GPL-3.0-or-later
// A button of the snipping toolbar (snip_toolbar in design/reference/measurements.json): 32 × 32,
// radius 3, hover #2c2c2c / #dddddd; one glyph from qml/snip/icons in the text colour, optionally
// followed by a chevron (the mode button, 56 px wide).
import QtQuick
import QtQuick.Shapes
import Fenestra.Shell

Rectangle {
    id: button
    property string icon            // file name in qml/snip/icons, without .svg
    property string tip             // English source text (Strings.tr)
    property bool checked: false
    property bool chevron: false
    readonly property bool hovered: area.containsMouse
    signal clicked()

    width: chevron ? Metrics.n("snip.mode.width", 56) : Metrics.snipButtonWidth
    height: Metrics.snipButtonHeight
    radius: Metrics.snipButtonRadius
    color: area.pressed || checked ? Qt.tint(Metrics.col("snip.hover"), Theme.pressed)
         : area.containsMouse ? Metrics.col("snip.hover") : "transparent"

    function glyph(name) {
        return "image://tint/" + Theme.text.toString().slice(1, 7) + "/"
               + encodeURIComponent(Qt.resolvedUrl("icons/" + name + ".svg").toString())
    }
    Row {
        anchors.centerIn: parent
        spacing: 6
        Image {
            anchors.verticalCenter: parent.verticalCenter
            width: Metrics.snipIcon; height: Metrics.snipIcon
            sourceSize: Qt.size(Metrics.snipIcon * Screen.devicePixelRatio, Metrics.snipIcon * Screen.devicePixelRatio)
            source: button.glyph(button.icon)
        }
        Shape {
            visible: button.chevron
            anchors.verticalCenter: parent.verticalCenter
            width: 10; height: 10
            ShapePath {
                strokeColor: Theme.text; strokeWidth: 1; fillColor: "transparent"
                capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                PathPolyline { path: [Qt.point(1.5, 3.5), Qt.point(5, 7), Qt.point(8.5, 3.5)] }
            }
        }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        onClicked: button.clicked()
    }
    Accessible.role: Accessible.Button
    Accessible.name: Strings.tr(tip)
}

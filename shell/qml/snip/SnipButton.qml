// SPDX-License-Identifier: GPL-3.0-or-later
// A button of the snipping toolbar: one glyph from qml/snip/icons, drawn in the text colour (accent
// when it is the selected mode).
import QtQuick
import Fenestra.Shell

Rectangle {
    id: button
    property string icon            // file name in qml/snip/icons, without .svg
    property string tip             // English source text (Strings.tr)
    property bool checked: false
    readonly property bool hovered: area.containsMouse
    signal clicked()

    width: Metrics.snipButtonWidth
    height: Metrics.snipButtonHeight
    radius: Metrics.snipButtonRadius
    color: area.pressed ? Theme.pressed
         : checked ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(0, 0, 0, 0.06))
         : area.containsMouse ? Theme.hover : "transparent"

    Image {
        anchors.centerIn: parent
        width: Metrics.snipIcon; height: Metrics.snipIcon
        sourceSize: Qt.size(Metrics.snipIcon * Screen.devicePixelRatio, Metrics.snipIcon * Screen.devicePixelRatio)
        readonly property color tint: button.checked ? Theme.accentText : Theme.text
        source: "image://tint/" + tint.toString().slice(1, 7) + "/"
                + encodeURIComponent(Qt.resolvedUrl("icons/" + button.icon + ".svg").toString())
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

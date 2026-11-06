// SPDX-License-Identifier: GPL-3.0-or-later
// 16 px status glyph from the Fenestra icon theme, recoloured for light mode.
import QtQuick
import QtQuick.Effects
import Fenestra.Shell

Item {
    property string name
    property url source
    width: 16; height: 16
    visible: name !== "" || source.toString() !== ""
    Image {
        id: img
        anchors.fill: parent
        sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
        source: parent.source.toString() !== "" ? parent.source : (parent.name ? "image://icon/" + parent.name : "")
        visible: Theme.dark
    }
    MultiEffect {
        anchors.fill: img
        source: img
        visible: !Theme.dark
        colorization: 1
        colorizationColor: Theme.text
    }
}

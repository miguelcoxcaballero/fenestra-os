// SPDX-License-Identifier: GPL-3.0-or-later
// A Windows glyph: the Segoe Fluent Icons code point when that font is installed (an imported
// Windows font pack: the glyph LogonUI itself draws), else Fenestra's own SVG drawn in its place.
// The item is the glyph's em box (size x size), as in XAML's FontIcon.
import QtQuick
import QtQuick.Effects

Item {
    id: g
    property string glyph            // e.g. ""
    property string fallback         // file URL of an SVG, or ""
    property real size: 16
    property color color: "white"
    // The fallback is drawn in currentColor (black for Qt SVG): lift it to white.
    property bool whiten: fallback.indexOf("/packs/") >= 0 && fallback.indexOf("/white/") < 0
    readonly property bool fluent: Fluent.available && glyph !== ""
    width: size; height: size
    Text {
        visible: g.fluent
        anchors.fill: parent
        text: g.glyph; color: g.color
        font.family: "Segoe Fluent Icons"; font.pixelSize: g.size
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignTop
        lineHeightMode: Text.FixedHeight; lineHeight: g.size
        renderType: Text.QtRendering
    }
    Image {
        visible: !g.fluent && g.fallback !== ""
        anchors.fill: parent
        source: visible ? g.fallback : ""
        sourceSize: Qt.size(Math.ceil(g.size * Screen.devicePixelRatio), Math.ceil(g.size * Screen.devicePixelRatio))
        smooth: true
        layer.enabled: visible && g.whiten
        layer.effect: MultiEffect { brightness: 1.0 }
    }
}

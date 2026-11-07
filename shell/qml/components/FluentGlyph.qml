// SPDX-License-Identifier: GPL-3.0-or-later
// A Windows glyph: the Segoe Fluent Icons code point when that font is installed (an imported
// Windows font pack: the glyphs Windows itself draws), else the fallback icon (name or file) tinted.
// The glyph's em box is the item: size × size, like a SymbolicIcon of the same size.
import QtQuick
import Fenestra.Shell

Item {
    id: g
    property string glyph          // e.g. ""
    property string fallback       // icon name or file URL
    property int size: 16
    property color color: Theme.text
    readonly property bool fluent: FluentFont.available && glyph !== ""
    width: size; height: size
    Text {
        visible: g.fluent
        anchors.fill: parent
        text: g.glyph; color: g.color
        font.family: "Segoe Fluent Icons"; font.pixelSize: g.size
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignTop
        lineHeightMode: Text.FixedHeight; lineHeight: g.size
    }
    Image {
        visible: !g.fluent && g.fallback !== ""
        anchors.fill: parent
        sourceSize: Qt.size(g.size * Screen.devicePixelRatio, g.size * Screen.devicePixelRatio)
        source: visible ? "image://tint/" + g.color.toString().slice(1, 7) + "/" + encodeURIComponent(g.fallback) : ""
    }
}

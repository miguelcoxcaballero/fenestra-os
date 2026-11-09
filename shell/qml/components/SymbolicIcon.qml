// SPDX-License-Identifier: GPL-3.0-or-later
// Status / menu glyph: drawn as is on dark surfaces, recoloured to the text colour in light mode.
import QtQuick
import Fenestra.Shell

Image {
    id: glyph
    property string name
    property url source_
    property int size: 16
    // Always recolour to the text colour, also in dark mode (menu glyphs: some assets carry
    // Explorer's tinted ink, the shell's menus draw them in the text colour).
    property bool monochrome: false
    // The colour of a recoloured glyph.
    property color tint: Theme.text
    property alias src: glyph.source_
    width: size; height: size
    visible: name !== "" || source_.toString() !== ""
    sourceSize: Qt.size(size * Screen.devicePixelRatio, size * Screen.devicePixelRatio)
    readonly property string target: source_.toString() !== "" ? source_.toString() : name
    source: target === "" ? ""
            : Theme.dark && !monochrome ? (source_.toString() !== "" ? source_ : "image://icon/" + name)
            : "image://tint/" + glyph.tint.toString().slice(1, 7) + "/" + encodeURIComponent(target)
}

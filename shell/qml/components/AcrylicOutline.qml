// SPDX-License-Identifier: GPL-3.0-or-later
// The edge of an Acrylic, drawn after (over) its owner's content: white 20 % over Start's fill
// (79, 93, 89 on user-win11 160039), black 15 % on menus (160110).
import QtQuick
import Fenestra.Shell

Rectangle {
    property Item acrylic
    visible: acrylic && acrylic.visible && acrylic.border
    x: acrylic ? acrylic.x : 0; y: acrylic ? acrylic.y : 0
    width: acrylic ? acrylic.width : 0; height: acrylic ? acrylic.height : 0
    color: "transparent"
    radius: acrylic ? acrylic.radius : 0
    border.width: acrylic ? acrylic.borderWidth : 0
    border.color: acrylic ? acrylic.borderColor : "transparent"
    // Windows' elevation edge is lighter on top: (87, 105, 101) over Start's header (26, 42, 38)
    // = white 28 % against 20.5 % on the sides (user-win11 160039).
    Rectangle {
        visible: acrylic && acrylic.translucent && !acrylic.recipe.startsWith("menu") && acrylic.recipe !== "tooltip"
        x: parent.radius; width: parent.width - 2 * parent.radius; height: parent.border.width; antialiasing: true
        color: Metrics.themed("acrylic.border.top")
    }
}

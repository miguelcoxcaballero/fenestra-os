// SPDX-License-Identifier: GPL-3.0-or-later
// Material of the shell's popups (Start, Search, Quick settings, Notification Center, calendar,
// menus, tooltips) as measured on the user's Windows 11 (reference-shots/user-win11, 150 %, dark,
// transparency on, wallpaper (72, 104, 96); tests/shell-kwin/pixel/MEASUREMENTS.md):
//   - a translucent fill drawn over KWin's blur (the popup window asks for the blur behind each
//     Acrylic item with ShellUtil.setBlurItems). Windows' acrylic keeps half the backdrop's chroma
//     and pins its luminosity to the tint's; KWin has no colour matrix any more (6.8), so the fill
//     is the overlay that gives the measured colour over the wallpaper: Start's body = black 52 %,
//     its header and footer = black 61 % (acrylic.<recipe> tokens);
//   - a 1 px light border (white over the fill), 2 device px at 150 % as on the reference;
//   - the two-layer shadow of image://popupshadow around it (nothing under the panel).
// Appearance/Transparency=false: the opaque fallback colours (acrylic.<recipe>.solid), no blur.
import QtQuick
import Fenestra.Shell

Item {
    id: acrylic
    // panel (Start body, Search, Quick settings, calendar), base (Start header/footer,
    // notifications), menu (menus over the desktop), menu.panel (menus over Start / Search),
    // tooltip.
    property string recipe: "panel"
    property real radius: Metrics.flyoutRadius
    property bool shadow: true
    property string shadowKind: "popup"
    property bool border: true
    property alias fill: fillRect
    readonly property bool translucent: ShellSettings.transparency
    readonly property int shadowMargin: Metrics.tok(shadowKind + ".shadow.margin", 28)
    // Device pixels per logical pixel of the window (1.5 at 150 %), for the shadow's pixel grid.
    readonly property real dpr: Window.window ? ShellUtil.scaleOf(Window.window) : 1

    Image {
        visible: acrylic.shadow && acrylic.width > 0 && acrylic.height > 0
        x: -acrylic.shadowMargin; y: -acrylic.shadowMargin
        width: acrylic.width + 2 * acrylic.shadowMargin; height: acrylic.height + 2 * acrylic.shadowMargin
        smooth: false
        source: visible ? "image://popupshadow/" + acrylic.width + "/" + acrylic.height + "/" + acrylic.radius + "/"
                          + acrylic.shadowMargin + "/" + acrylic.dpr + "/" + acrylic.shadowKind : ""
    }
    Rectangle {
        id: fillRect
        anchors.fill: parent
        radius: acrylic.radius
        color: Metrics.themed("acrylic." + acrylic.recipe + (acrylic.translucent ? "" : ".solid"))
        // 2 device px at 150 % (4/3 logical), 1 at 100 %.
        border.width: acrylic.border ? (acrylic.dpr > 1 && acrylic.dpr < 2 ? 2 : Math.max(1, Math.round(acrylic.dpr))) / acrylic.dpr : 0
        border.color: Metrics.themed(!acrylic.translucent ? "acrylic.border.solid"
                                     : acrylic.recipe.startsWith("menu") || acrylic.recipe === "tooltip" ? "acrylic.border.menu" : "acrylic.border")
    }
}

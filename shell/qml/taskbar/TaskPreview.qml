// SPDX-License-Identifier: GPL-3.0-or-later
// Hover preview of a taskbar group (B03): one card per window (preview.* in design/tokens.json):
// icon and title on top, the window below; click activates, × closes.
// Live thumbnails need KWin's screencast (PipeWire, OpenGL): see docs/fenestra-shell/FEASIBILITY.md;
// until then the window's place shows the app icon.
//
// Measured on user-win11 163657 at 150 % ("Home - File Explorer", device px): card 1383-1631 x
// 1470-1709 (166 x 160), 12 above the taskbar, centred on the button; radius 8; acrylic
// (AcrylicBackgroundFillColorDefault: (30, 57, 50) over the green wallpaper); 2 px gradient border;
// shadow below and beside it (acrylic.cpp, renderCard). Icon 16 at (14, 20); title 14 px, "H" from
// x 52, cap top 26; thumbnail at (14, 62), 222 x 164 (the window's aspect in a 182 x 109.33 box),
// 13 / 14 px from the right and bottom edges.
import QtQuick
import Fenestra.Shell

Flyout {
    id: preview
    property var windows: []
    property string icon      // the group's icon (the windows of one app)
    property bool keepOpen: hoverArea.containsMouse
    takesFocus: false
    motion: "fade"
    padding: 0
    // The card is drawn by the acrylic provider with its shadow: the surface is `shadow` larger
    // left, right and below, and its bottom edge touches the taskbar (the 12 px gap is shadow room).
    readonly property real shadow: Metrics.flyoutGap
    gap: 0
    background.color: "transparent"
    background.border.width: 0
    // The surface's real scale (1.5 at 150 %; the screen's devicePixelRatio is its integer one).
    readonly property real dpr: scaleProbe.devicePixelRatio > 0 ? scaleProbe.devicePixelRatio : 1
    ShadowLabel { id: scaleProbe; parent: preview.contentItem; visible: false; width: 1; height: 1 }
    function snap(v) { return Math.round(v * dpr) / dpr }
    readonly property real thumbMaxWidth: Tokens.v("preview.thumb.width", 182)
    readonly property real thumbMaxHeight: Tokens.v("preview.thumb.height", 109.33)
    readonly property real thumbX: snap(Tokens.v("preview.thumb.x", 9.33))
    readonly property real thumbY: snap(Tokens.v("preview.thumb.y", 41.33))
    readonly property real thumbRight: snap(Tokens.v("preview.thumb.right", 8.67))
    readonly property real thumbBottom: snap(Tokens.v("preview.thumb.bottom", 9.33))
    // Screen position of the card (for the acrylic behind it).
    readonly property real cardX: Math.round(anchorX - width / 2) + shadow
    readonly property real cardY: targetScreen ? targetScreen.height - Metrics.taskbarHeight - height : 0

    Row {
        id: list
        Repeater {
            model: preview.windows
            delegate: Item {
                id: card
                required property var modelData
                required property int index
                readonly property real aspect: modelData.width > 0 && modelData.height > 0 ? modelData.width / modelData.height : preview.thumbMaxWidth / preview.thumbMaxHeight
                readonly property real thumbW: preview.snap(Math.min(preview.thumbMaxWidth, preview.thumbMaxHeight * aspect))
                readonly property real thumbH: preview.snap(Math.min(preview.thumbMaxHeight, preview.thumbMaxWidth / aspect))
                readonly property real cardW: preview.thumbX + thumbW + preview.thumbRight
                readonly property real cardH: preview.thumbY + thumbH + preview.thumbBottom
                width: cardW + (index === 0 ? preview.shadow : 0) + (index === preview.windows.length - 1 ? preview.shadow : 0)
                height: cardH + preview.shadow
                Item {
                    id: face
                    x: card.index === 0 ? preview.shadow : 0
                    width: card.cardW; height: card.cardH
                    Image {
                        x: -preview.shadow; y: 0
                        width: card.cardW + 2 * preview.shadow; height: card.cardH + preview.shadow
                        visible: ShellSettings.transparency && status === Image.Ready
                        smooth: false
                        readonly property var scr: preview.targetScreen
                        source: !preview.visible || !scr || !ShellSettings.transparency ? ""
                                : "image://acrylic/card/" + (Theme.dark ? "dark" : "light") + "/" + scr.width + "/" + scr.height + "/"
                                  + preview.dpr + "/" + (preview.cardX + face.mapToItem(list, 0, 0).x) + "/" + preview.cardY + "/"
                                  + card.cardW + "/" + card.cardH + "/" + Metrics.flyoutRadius + "/" + preview.shadow + "/"
                                  + encodeURIComponent(WallpaperSource.image !== "" ? decodeURIComponent(WallpaperSource.image.replace(/^file:\/\//, ""))
                                                                                   : WallpaperSource.color)
                    }
                    // Without transparency: the acrylic's fallback colour and a plain border.
                    Rectangle {
                        anchors.fill: parent
                        visible: !ShellSettings.transparency
                        radius: Metrics.flyoutRadius
                        color: Metrics.themed("menu.fill")
                        border.color: Metrics.themed("preview.border")
                    }
                    Rectangle {
                        anchors.fill: parent; anchors.margins: 4
                        radius: Metrics.controlRadius
                        color: rowMouse.containsMouse ? Metrics.themed("menu.hover") : "transparent"
                    }
                    Image {
                        x: preview.snap(Tokens.v("preview.icon.x", 9.33)); y: preview.snap(Tokens.v("preview.icon.y", 13.33))
                        width: 16; height: 16
                        sourceSize: Qt.size(16 * preview.dpr, 16 * preview.dpr)
                        source: preview.icon ? "image://icon/" + preview.icon : ""
                    }
                    Text {
                        x: preview.snap(Tokens.v("preview.title.x", 34)); width: parent.width - x - 8
                        y: preview.snap(Tokens.v("preview.title.y", 11))
                        text: card.modelData.title
                        elide: Text.ElideRight
                        color: Theme.text
                        font.family: Metrics.fontFamily
                        font.pixelSize: Metrics.fontBody
                    }
                    Rectangle {
                        x: preview.thumbX; y: preview.thumbY; width: card.thumbW; height: card.thumbH
                        color: Metrics.themed("preview.window")
                        Image {
                            anchors.centerIn: parent; width: 32; height: 32
                            sourceSize: Qt.size(32 * preview.dpr, 32 * preview.dpr)
                            source: preview.icon ? "image://icon/" + preview.icon : ""
                        }
                    }
                    MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true
                        onClicked: { WindowsModel.activate(card.modelData.row); preview.close() } }
                    Rectangle {
                        anchors { right: parent.right; rightMargin: 6; top: parent.top; topMargin: 6 }
                        width: 28; height: 28; radius: Metrics.controlRadius
                        color: closeMouse.containsMouse ? "#c42b1c" : "transparent"
                        visible: rowMouse.containsMouse || closeMouse.containsMouse
                        SymbolicIcon { anchors.centerIn: parent; size: 16; src: Metrics.assets + "menu-icons/win11-menu-cancel.svg" }
                        MouseArea { id: closeMouse; anchors.fill: parent; hoverEnabled: true
                            onClicked: WindowsModel.close(card.modelData.row) }
                    }
                }
            }
        }
    }
    MouseArea { id: hoverArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; z: -1 }
}

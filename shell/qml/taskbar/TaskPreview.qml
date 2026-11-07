// SPDX-License-Identifier: GPL-3.0-or-later
// Hover preview of a taskbar group (B03): one card per window (preview.* in design/tokens.json):
// icon and title on top, the LIVE window below (LiveThumbnail.qml: KWin's screencast of the window
// over PipeWire; KWin's still pictures, refreshed, where it cannot stream); click activates, × or a
// middle click closes the window.
//
// Measured on user-win11 163657 at 150 % ("Home - File Explorer", device px): card 1383-1631 x
// 1470-1709 (166 x 160), 12 above the taskbar, centred on the button; radius 8; acrylic
// (AcrylicBackgroundFillColorDefault: (30, 57, 50) over the green wallpaper); 2 px gradient border;
// shadow below and beside it (acrylic.cpp, renderCard). Icon 16 at (14, 20); title 14 px, "H" from
// x 52, cap top 26; thumbnail at (14, 62), 222 x 164 (the window's aspect in a 182 x 109.33 box),
// 13 / 14 px from the right and bottom edges.
// Behaviour and motion: recorded on the reference VM (design/motion.json "preview").
import QtQuick
import Fenestra.Shell

Flyout {
    id: preview
    // The taskbar button whose windows are shown (its model's `windows` follow the windows live).
    property Item owner: null
    readonly property var windows: owner && owner.windowList ? owner.windowList : []
    property string icon: owner ? owner.iconName : ""
    // The last window of the group closed (× or middle click): nothing left to show.
    onWindowsChanged: if (shown && windows.length === 0) close()
    property bool keepOpen: hoverArea.hovered
    takesFocus: false
    motion: "fade"
    padding: 0
    // The card is drawn by the acrylic provider with its shadow: the surface is `shadow` larger
    // left, right and below, and its bottom edge touches the taskbar (the 12 px gap is shadow room).
    readonly property real shadow: Metrics.flyoutGap
    gap: 0
    // The cards draw their own material: no flyout background, shadow or KWin blur behind the row.
    background.visible: false
    material.shadow: false
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
    readonly property real cardGap: snap(Tokens.v("preview.card.gap", 0))
    // Screen position of the cards' row (for the acrylic behind them): the sheet's top-left.
    readonly property real rowX: Math.round(sheetX)
    readonly property real rowY: targetScreen ? targetScreen.height - Metrics.taskbarHeight - sheetHeight : 0

    // ---- The real acrylic (core/backdrop.h) ----------------------------------------------------
    // One capture of what is behind the strip where cards can be (the screen's width, the tallest
    // card) when the preview opens; switching buttons keeps it. Until it is in, and without
    // transparency effects, the cards show the acrylic computed from the wallpaper alone.
    readonly property real stripHeight: Math.ceil(thumbY + thumbMaxHeight + thumbBottom)
    property int stripId: 0
    property int readyId: 0
    property rect readyArea
    function requestStrip() {
        dropStrip()
        if (!ShellSettings.transparency || !targetScreen) return
        stripId = Backdrop.request(preview, Qt.rect(0, targetScreen.height - Metrics.taskbarHeight - shadow - stripHeight,
                                                       targetScreen.width, stripHeight),
                                      WallpaperSource.image !== "" ? WallpaperSource.image : WallpaperSource.color, ["preview"])
    }
    function dropStrip() {
        if (stripId) Backdrop.release(stripId)
        stripId = 0; readyId = 0
    }
    Connections {
        target: Backdrop
        function onReady(id, ms) { if (id === preview.stripId && preview.shown) { preview.readyArea = Backdrop.area(id); preview.readyId = id } }
    }
    onShownChanged: if (shown && stripId === 0) requestStrip()
    onDismissed: dropStrip()

    // Stills (WindowSnapshot) for the cards KWin cannot stream: taken on opening, then refreshed.
    property int stillCards: 0
    Timer {
        id: stillRefresh
        interval: Tokens.v("preview.still.refresh", 1000)
        repeat: true
        running: preview.visible && preview.shown && preview.stillCards > 0
        onTriggered: {
            for (let i = 0; i < cards.count; ++i) {
                const c = cards.itemAt(i)
                if (c && c.still) WindowSnapshot.capture(c.win.uuid)
            }
        }
    }

    Row {
        id: list
        spacing: preview.cardGap
        Repeater {
            id: cards
            // A count, not the list: the cards (and their streams) stay while titles change.
            model: preview.windows.length
            delegate: Item {
                id: card
                required property int index
                readonly property var win: preview.windows[index] || ({ uuid: "", title: "", width: 0, height: 0, row: -1 })
                readonly property real aspect: win.width > 0 && win.height > 0 ? win.width / win.height : preview.thumbMaxWidth / preview.thumbMaxHeight
                readonly property real thumbW: preview.snap(Math.min(preview.thumbMaxWidth, preview.thumbMaxHeight * aspect))
                readonly property real thumbH: preview.snap(Math.min(preview.thumbMaxHeight, preview.thumbMaxWidth / aspect))
                readonly property real cardW: preview.thumbX + thumbW + preview.thumbRight
                readonly property real cardH: preview.thumbY + thumbH + preview.thumbBottom
                readonly property bool last: index === preview.windows.length - 1
                width: cardW + (index === 0 ? preview.shadow : 0) + (last ? preview.shadow : 0)
                height: cardH + preview.shadow
                readonly property bool hot: rowMouse.containsMouse || closeMouse.containsMouse
                // KWin cannot stream this window (or KPipeWire is missing): stills instead.
                readonly property bool still: live.status === Loader.Error || (live.item !== null && live.item.unavailable)
                property int stillSerial: 0
                onStillChanged: { preview.stillCards += still ? 1 : -1; if (still) WindowSnapshot.capture(win.uuid) }
                Component.onDestruction: if (still) preview.stillCards -= 1
                Connections {
                    target: WindowSnapshot
                    enabled: card.still
                    function onCaptured(uuid, serial) { if (uuid === card.win.uuid) card.stillSerial = serial }
                }
                Item {
                    id: face
                    x: card.index === 0 ? preview.shadow : 0
                    width: card.cardW; height: card.cardH
                    readonly property real screenX: preview.rowX + face.mapToItem(list, 0, 0).x
                    readonly property string cardSource: "/" + (Theme.dark ? "dark" : "light") + "/" + (preview.targetScreen ? preview.targetScreen.width + "/" + preview.targetScreen.height : "0/0") + "/"
                                  + preview.dpr + "/" + screenX + "/" + preview.rowY + "/"
                                  + card.cardW + "/" + card.cardH + "/" + Metrics.flyoutRadius + "/" + preview.shadow + "/"
                                  + encodeURIComponent(WallpaperSource.image !== "" ? decodeURIComponent(WallpaperSource.image.replace(/^file:\/\//, ""))
                                                                                   : WallpaperSource.color)
                    // The acrylic from the wallpaper (with its shadow and border), until the real one is in.
                    Image {
                        x: -preview.shadow; y: 0
                        width: card.cardW + 2 * preview.shadow; height: card.cardH + preview.shadow
                        visible: ShellSettings.transparency && status === Image.Ready && realAcrylic.opacity < 1
                        smooth: false
                        source: !preview.visible || !preview.targetScreen || !ShellSettings.transparency ? "" : "image://acrylic/card" + face.cardSource
                    }
                    BackdropView {
                        id: realAcrylic
                        anchors.fill: parent
                        source: preview.readyId > 0 ? "image://backdrop/" + preview.readyId + "/preview" : ""
                        area: preview.readyArea
                        origin: Qt.point(face.screenX, preview.rowY)
                    }
                    // Its shadow and border.
                    Image {
                        x: -preview.shadow; y: 0
                        width: card.cardW + 2 * preview.shadow; height: card.cardH + preview.shadow
                        visible: realAcrylic.visible && status === Image.Ready
                        smooth: false
                        source: !realAcrylic.everReady ? "" : "image://acrylic/cardframe" + face.cardSource
                    }
                    // Without transparency: the acrylic's fallback colour and a plain border.
                    Rectangle {
                        anchors.fill: parent
                        visible: !ShellSettings.transparency
                        radius: Metrics.flyoutRadius
                        color: Metrics.themed("menu.fill")
                        border.color: Metrics.themed("preview.border")
                    }
                    // Hovered: the whole card lightens (preview.hover), pressed a little less.
                    Rectangle {
                        anchors.fill: parent
                        radius: Metrics.flyoutRadius
                        color: rowMouse.pressed ? Metrics.themed("preview.pressed") : Metrics.themed("preview.hover")
                        opacity: card.hot ? 1 : 0
                        Behavior on opacity { enabled: !Motion.reduced; NumberAnimation { duration: Tokens.v("motion.preview.hover", 83) } }
                    }
                    Image {
                        x: preview.snap(Tokens.v("preview.icon.x", 9.33)); y: preview.snap(Tokens.v("preview.icon.y", 13.33))
                        width: 16; height: 16
                        sourceSize: Qt.size(16 * preview.dpr, 16 * preview.dpr)
                        source: preview.icon ? "image://icon/" + preview.icon : ""
                    }
                    Text {
                        x: preview.snap(Tokens.v("preview.title.x", 34))
                        width: parent.width - x - (card.hot ? Tokens.v("preview.close.reserve", 34) : 8)
                        y: preview.snap(Tokens.v("preview.title.y", 11))
                        text: card.win.title
                        elide: Text.ElideRight
                        color: Theme.text
                        font.family: Metrics.fontFamily
                        font.pixelSize: Metrics.fontBody
                    }
                    Item {
                        id: thumbBox
                        x: preview.thumbX; y: preview.thumbY; width: card.thumbW; height: card.thumbH
                        Loader {
                            id: live
                            anchors.fill: parent
                            // Streams only while the preview shows (KWin renders the window for it).
                            active: preview.visible && card.win.uuid !== ""
                            source: "LiveThumbnail.qml"
                        }
                        Binding { target: live.item; property: "uuid"; value: card.win.uuid; when: live.item !== null }
                        Image {
                            anchors.fill: parent
                            visible: card.still && status === Image.Ready
                            source: card.still && card.stillSerial > 0 ? "image://windowshot/" + card.win.uuid + "/" + card.stillSerial : ""
                            sourceSize: Qt.size(Math.round(card.thumbW * preview.dpr), Math.round(card.thumbH * preview.dpr))
                            fillMode: Image.PreserveAspectFit
                            retainWhileLoading: true
                            cache: false
                            smooth: true
                        }
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                        onClicked: (m) => {
                            // Middle click closes the window, as on Windows.
                            if (m.button === Qt.MiddleButton) { WindowsModel.close(card.win.row); return }
                            WindowsModel.activate(card.win.row)
                            preview.close()
                        }
                    }
                    Rectangle {
                        id: closeButton
                        anchors { right: parent.right; rightMargin: preview.snap(Tokens.v("preview.close.right", 6))
                                  top: parent.top; topMargin: preview.snap(Tokens.v("preview.close.top", 6)) }
                        width: Tokens.v("preview.close.size", 28); height: width
                        radius: Metrics.controlRadius
                        color: closeMouse.pressed ? Metrics.themed("preview.close.pressed")
                               : closeMouse.containsMouse ? Metrics.themed("preview.close.hover") : "transparent"
                        visible: card.hot
                        SymbolicIcon { anchors.centerIn: parent; size: 16; src: Metrics.assets + "menu-icons/win11-menu-cancel.svg" }
                        MouseArea { id: closeMouse; anchors.fill: parent; hoverEnabled: true
                            onClicked: WindowsModel.close(card.win.row) }
                    }
                }
            }
        }
    }
    // Passive: sees the pointer over the cards' own mouse areas too.
    HoverHandler { id: hoverArea }
}

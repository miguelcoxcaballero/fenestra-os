// SPDX-License-Identifier: GPL-3.0-or-later
// Hover preview of a taskbar group (B03), as Windows 11: ONE acrylic panel with a slot per window
// (icon and title on top, the LIVE window below: LiveThumbnail.qml, KWin's screencast of the window
// over PipeWire; KWin's still pictures, refreshed, where it cannot stream). Click a slot: activate
// the window; × or a middle click: close it.
//
// Measured on user-win11 163657 at 150 % ("Home - File Explorer", device px): panel 1383-1631 x
// 1470-1709 (166 x 160), 12 above the taskbar, centred on the button; radius 8; acrylic
// (AcrylicBackgroundFillColorDefault: (30, 57, 50) over the green wallpaper); 2 px gradient border;
// shadow below and beside it (acrylic.cpp, renderCard). Icon 16 at (14, 20); title 14 px, "H" from
// x 52, cap top 26; thumbnail at (14, 62), 222 x 164, 13 / 14 px from the right and bottom edges.
// Recorded on the reference VM (150 %, reference-shots/motion-preview-2026-11-07, design/motion.json
// "preview"): two windows = one panel 633 px wide, slots side by side (thumbnails 292 px, 24 px
// apart: each slot is margin + thumbnail + margin); the thumbnail keeps the window's aspect at the
// full 164 px height (292 x 165 for a 1.77 window). Hovering a slot lights it at once (white 6 %
// over the acrylic, 44 -> 56 on the VM's flat fill; radius 4 inside, the panel's 8 at its corners)
// and shows × (10 px glyph, centred in a 30 x 30 button 5.33 from the slot's top and right; hovered
// #C42B1C, ~80 ms) while the title ellipsis moves in front of it.
import QtQuick
import Fenestra.Shell

Flyout {
    id: preview
    // The taskbar button whose windows are shown (its model's `windows` follow the windows live).
    property Item owner: null
    readonly property var windows: owner && owner.windowList ? owner.windowList : []
    property string icon: owner ? owner.iconName : ""
    property bool keepOpen: hoverArea.hovered
    // The last window of the group closed (× or middle click): nothing left to show.
    onWindowsChanged: if (shown && windows.length === 0) close()
    takesFocus: false
    // Rises from behind the taskbar like Start (250 ms, decelerate; travel = panel + 12 px gap).
    motion: "taskbar"
    padding: 0
    // The panel is drawn by the acrylic provider with its shadow: the surface is `shadow` larger
    // left, right and below, and its bottom edge touches the taskbar (the 12 px gap is shadow room).
    readonly property real shadow: Metrics.flyoutGap
    gap: 0
    // The panel draws its own material: no flyout background, shadow or KWin blur behind it.
    background.visible: false
    material.shadow: false
    // Windows hides the preview at once (no motion: nothing in the 30 ms frames after it is gone).
    function close() {
        if (!visible || !shown) return
        shown = false
        visible = false
        ShellUtil.clearBlur(preview)
        dismissed()
    }
    // The surface's real scale (1.5 at 150 %; the screen's devicePixelRatio is its integer one).
    readonly property real dpr: scaleProbe.devicePixelRatio > 0 ? scaleProbe.devicePixelRatio : 1
    ShadowLabel { id: scaleProbe; parent: preview.contentItem; visible: false; width: 1; height: 1 }
    function snap(v) { return Math.round(v * dpr) / dpr }
    readonly property real thumbMaxWidth: Tokens.v("preview.thumb.width", 200)
    readonly property real thumbMaxHeight: Tokens.v("preview.thumb.height", 109.33)
    readonly property real thumbX: snap(Tokens.v("preview.thumb.x", 9.33))
    readonly property real thumbY: snap(Tokens.v("preview.thumb.y", 41.33))
    readonly property real thumbRight: snap(Tokens.v("preview.thumb.right", 8.67))
    readonly property real thumbBottom: snap(Tokens.v("preview.thumb.bottom", 9.33))
    // Between two thumbnails: 24 device px at 150 % on the VM, half of it in each slot.
    readonly property real slotGap: snap(Tokens.v("preview.thumb.gap", 16)) / 2
    readonly property real radius: Metrics.flyoutRadius
    readonly property real hoverRadius: Metrics.controlRadius
    // Screen position of the panel (for the acrylic behind it): the sheet's top-left + the shadow room.
    readonly property real panelX: Math.round(sheetX) + shadow
    readonly property real panelY: targetScreen ? targetScreen.height - Metrics.taskbarHeight - sheetHeight : 0

    // ---- The real acrylic (core/backdrop.h) ----------------------------------------------------
    // One capture of what is behind the strip where the panel can be (the screen's width, the
    // tallest panel) when the preview opens; switching buttons keeps it. Until it is in, and
    // without transparency effects, the panel shows the acrylic computed from the wallpaper alone.
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
    onShownChanged: {
        if (shown && stripId === 0) requestStrip()
        if (!shown) testHot = -1
    }
    onDismissed: dropStrip()

    // Stills (WindowSnapshot) for the windows KWin cannot stream: taken on opening, then refreshed.
    property int stillSlots: 0
    Timer {
        id: stillRefresh
        interval: Tokens.v("preview.still.refresh", 1000)
        repeat: true
        running: preview.visible && preview.shown && preview.stillSlots > 0
        onTriggered: {
            for (let i = 0; i < slots.count; ++i) {
                const c = slots.itemAt(i)
                if (c && c.still) WindowSnapshot.capture(c.win.uuid)
            }
        }
    }

    // The shadow room around the panel (left, right, below).
    Item {
        id: room
        width: panel.width + 2 * preview.shadow
        height: panel.height + preview.shadow
        Item {
            id: panel
            x: preview.shadow
            width: Math.max(1, row.width)
            height: Math.max(1, row.height)
            readonly property string cardSource: "/" + (Theme.dark ? "dark" : "light") + "/"
                          + (preview.targetScreen ? preview.targetScreen.width + "/" + preview.targetScreen.height : "0/0") + "/"
                          + preview.dpr + "/" + preview.panelX + "/" + preview.panelY + "/"
                          + panel.width + "/" + panel.height + "/" + preview.radius + "/" + preview.shadow + "/"
                          + encodeURIComponent(WallpaperSource.image !== "" ? decodeURIComponent(WallpaperSource.image.replace(/^file:\/\//, ""))
                                                                           : WallpaperSource.color)
            // The acrylic from the wallpaper (with its shadow and border), until the real one is in.
            Image {
                x: -preview.shadow; y: 0
                width: panel.width + 2 * preview.shadow; height: panel.height + preview.shadow
                visible: ShellSettings.transparency && status === Image.Ready && realAcrylic.opacity < 1
                smooth: false
                source: !preview.visible || !preview.targetScreen || !ShellSettings.transparency ? "" : "image://acrylic/card" + panel.cardSource
            }
            BackdropView {
                id: realAcrylic
                anchors.fill: parent
                source: preview.readyId > 0 ? "image://backdrop/" + preview.readyId + "/preview" : ""
                area: preview.readyArea
                origin: Qt.point(preview.panelX, preview.panelY)
                topRadius: preview.radius; bottomRadius: preview.radius
            }
            // Its shadow and border.
            Image {
                x: -preview.shadow; y: 0
                width: panel.width + 2 * preview.shadow; height: panel.height + preview.shadow
                visible: realAcrylic.visible && status === Image.Ready
                smooth: false
                source: !realAcrylic.everReady ? "" : "image://acrylic/cardframe" + panel.cardSource
            }
            // Without transparency: the acrylic's fallback colour and a plain border.
            Rectangle {
                anchors.fill: parent
                visible: !ShellSettings.transparency
                radius: preview.radius
                color: Metrics.themed("menu.fill")
                border.color: Metrics.themed("preview.border")
            }

            Row {
                id: row
                Repeater {
                    id: slots
                    // A count, not the list: the slots (and their streams) stay while titles change.
                    model: preview.windows.length
                    delegate: Item {
                        id: slot
                        required property int index
                        readonly property var win: preview.windows[index] || ({ uuid: "", title: "", width: 0, height: 0, row: -1 })
                        readonly property real aspect: win.width > 0 && win.height > 0 ? win.width / win.height : preview.thumbMaxWidth / preview.thumbMaxHeight
                        readonly property real thumbW: preview.snap(Math.min(preview.thumbMaxWidth, preview.thumbMaxHeight * aspect))
                        readonly property real thumbH: preview.snap(Math.min(preview.thumbMaxHeight, preview.thumbMaxWidth / aspect))
                        readonly property bool first: index === 0
                        readonly property bool last: index === preview.windows.length - 1
                        readonly property real leftPad: first ? preview.thumbX : preview.slotGap
                        readonly property real rightPad: last ? preview.thumbRight : preview.slotGap
                        width: leftPad + thumbW + rightPad
                        height: preview.thumbY + preview.snap(preview.thumbMaxHeight) + preview.thumbBottom
                        readonly property bool hot: rowMouse.containsMouse || closeMouse.containsMouse || preview.testHot === index
                        // KWin cannot stream this window (or KPipeWire is missing): stills instead.
                        readonly property bool still: live.status === Loader.Error || (live.item !== null && live.item.unavailable)
                        property int stillSerial: 0
                        onStillChanged: { preview.stillSlots += still ? 1 : -1; if (still) WindowSnapshot.capture(win.uuid) }
                        Component.onDestruction: if (still) preview.stillSlots -= 1
                        Connections {
                            target: WindowSnapshot
                            enabled: slot.still
                            function onCaptured(uuid, serial) { if (uuid === slot.win.uuid) slot.stillSerial = serial }
                        }
                        // Hovered: the slot lights at once (no fade on the recording).
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 1 / preview.dpr
                            visible: slot.hot
                            color: rowMouse.pressed ? Metrics.themed("preview.pressed") : Metrics.themed("preview.hover")
                            topLeftRadius: slot.first ? preview.radius : preview.hoverRadius
                            bottomLeftRadius: slot.first ? preview.radius : preview.hoverRadius
                            topRightRadius: slot.last ? preview.radius : preview.hoverRadius
                            bottomRightRadius: slot.last ? preview.radius : preview.hoverRadius
                        }
                        Image {
                            x: slot.leftPad + preview.snap(Tokens.v("preview.icon.x", 9.33)) - preview.thumbX; y: preview.snap(Tokens.v("preview.icon.y", 13.33))
                            width: 16; height: 16
                            sourceSize: Qt.size(16 * preview.dpr, 16 * preview.dpr)
                            source: preview.icon ? "image://icon/" + preview.icon : ""
                        }
                        Text {
                            x: slot.leftPad + preview.snap(Tokens.v("preview.title.x", 34)) - preview.thumbX
                            // Up to the thumbnail's right edge; in front of × while it shows.
                            width: (slot.hot ? closeButton.x - Tokens.v("preview.title.close.gap", 4) : slot.leftPad + slot.thumbW) - x
                            y: preview.snap(Tokens.v("preview.title.y", 11))
                            text: slot.win.title
                            elide: Text.ElideRight
                            color: Theme.text
                            font.family: Metrics.fontFamily
                            font.pixelSize: Metrics.fontBody
                        }
                        Item {
                            id: thumbBox
                            x: slot.leftPad; y: preview.thumbY; width: slot.thumbW; height: slot.thumbH
                            Loader {
                                id: live
                                anchors.fill: parent
                                // Streams only while the preview shows (KWin renders the window for it).
                                active: preview.visible && slot.win.uuid !== ""
                                source: "LiveThumbnail.qml"
                            }
                            Binding { target: live.item; property: "uuid"; value: slot.win.uuid; when: live.item !== null }
                            Image {
                                anchors.fill: parent
                                visible: slot.still && status === Image.Ready
                                source: slot.still && slot.stillSerial > 0 ? "image://windowshot/" + encodeURIComponent(slot.win.uuid) + "/" + slot.stillSerial : ""
                                sourceSize: Qt.size(Math.round(slot.thumbW * preview.dpr), Math.round(slot.thumbH * preview.dpr))
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
                                if (m.button === Qt.MiddleButton) { WindowsModel.close(slot.win.row); return }
                                WindowsModel.activate(slot.win.row)
                                preview.close()
                            }
                        }
                        Rectangle {
                            id: closeButton
                            readonly property real size: Tokens.v("preview.close.size", 30)
                            x: slot.leftPad + slot.thumbW + preview.thumbRight - preview.snap(Tokens.v("preview.close.right", 5.33)) - size
                            y: preview.snap(Tokens.v("preview.close.top", 5.33))
                            width: size; height: size
                            radius: preview.hoverRadius
                            color: closeMouse.pressed ? Metrics.themed("preview.close.pressed") : Metrics.themed("preview.close.hover")
                            opacity: closeMouse.containsMouse ? 1 : 0
                            Behavior on opacity { enabled: !Motion.reduced; NumberAnimation { duration: Tokens.v("motion.preview.close.hover", 83) } }
                        }
                        SymbolicIcon {
                            anchors.centerIn: closeButton
                            visible: slot.hot
                            size: Tokens.v("preview.close.glyph", 10)
                            src: Metrics.assets + "menu-icons/win11-menu-cancel.svg"
                        }
                        MouseArea {
                            id: closeMouse
                            anchors.fill: closeButton
                            hoverEnabled: true
                            visible: slot.hot
                            onClicked: WindowsModel.close(slot.win.row)
                        }
                    }
                }
            }
        }
    }
    // Test hook (tests/shell-kwin): the slot drawn as hovered.
    property int testHot: -1
    // Passive: sees the pointer over the slots' own mouse areas too.
    HoverHandler { id: hoverArea }
}

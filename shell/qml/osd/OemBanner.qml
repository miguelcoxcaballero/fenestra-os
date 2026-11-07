// SPDX-License-Identifier: GPL-3.0-or-later
// The laptop maker's on-screen banner, for the keys its firmware handles (Fn+F11 performance mode,
// Fn+F9 keyboard backlight on Samsung Galaxy Books): SamsungSystemSupportOSD as disassembled
// (design/tokens.json oem.samsung.osd.*): a 20 px picture and one line of Segoe UI 14, 12 px
// apart, padded 14 × 12 (44 px high, as wide as the text), centred 75 px above the taskbar; DWM's
// blur behind it with #2C2C2C at 60 % (#F9F9F9 at 80 % in light mode) and 8 px corners
// (acrylic.samsung: the blur computed by core/backdrop.h); shown at once, hidden 2.4 s after
// the last change, without animation. Never takes focus or input.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: banner
    property var targetScreen
    property string text
    property string picture          // file URL, or "" for the fallback glyph
    property string glyph            // Segoe Fluent glyph when there is no picture
    color: "transparent"
    visible: false
    flags: Qt.FramelessWindowHint | Qt.WindowTransparentForInput
    readonly property int padX: Metrics.n("oem.samsung.osd.padding.x", 14)
    readonly property int padY: Metrics.n("oem.samsung.osd.padding.y", 12)
    readonly property int iconSize: Metrics.n("oem.samsung.osd.icon", 20)
    // OSDHandler measures the text with DirectWrite and truncates the width to whole px.
    width: padX + iconSize + Metrics.n("oem.samsung.osd.icon.gap", 12) + Math.floor(label.implicitWidth) + padX
    height: Metrics.n("oem.samsung.osd.height", 44)
    LayerShell.Window.scope: "fenestra-osd"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom
    // Exclusive zone 0: the margin counts from the taskbar's top (the work area's bottom).
    LayerShell.Window.margins.bottom: Metrics.n("oem.samsung.osd.bottom", 75)
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    Component.onCompleted: ShellUtil.keepScene(this)

    function show(text, picture, glyph) {
        banner.text = text
        banner.picture = picture || ""
        banner.glyph = glyph || ""
        if (!visible) {
            if (targetScreen) ShellUtil.placeOnScreen(banner, targetScreen.name)
            visible = true
            backdrop.start()
        } else {
            backdrop.updateBlur()
        }
        hideTimer.restart()
    }
    onWidthChanged: if (visible) { backdrop.start() }
    Timer { id: hideTimer; interval: Metrics.n("oem.samsung.osd.timeout", 2400); onTriggered: { banner.visible = false; backdrop.stop() } }

    BackdropHost {
        id: backdrop
        window: banner
        acrylics: [material]
        blurRadius: material.radius
        area: banner.targetScreen ? Qt.rect(Math.round((banner.targetScreen.width - banner.width) / 2),
                                            banner.targetScreen.height - Metrics.taskbarHeight - Metrics.n("oem.samsung.osd.bottom", 75) - banner.height,
                                            banner.width, banner.height) : Qt.rect(0, 0, 0, 0)
        originOf: function (a) { return Qt.point(area.x, area.y) }
    }
    Acrylic {
        id: material
        anchors.fill: parent
        recipe: "samsung"
        radius: Metrics.n("oem.samsung.osd.radius", 8)
        shadow: false
        border: false
    }
    Image {
        visible: banner.picture !== ""
        x: banner.padX; y: banner.padY + Math.round((Math.max(banner.iconSize, Math.floor(label.implicitHeight)) - banner.iconSize) / 2)
        width: banner.iconSize; height: banner.iconSize
        sourceSize: Qt.size(90, 90)
        smooth: true; mipmap: true
        source: banner.picture
    }
    FluentGlyph {
        visible: banner.picture === "" && banner.glyph !== ""
        x: banner.padX; y: banner.padY
        size: banner.iconSize
        glyph: banner.glyph
        color: Metrics.col("oem.samsung.osd.text")
    }
    Text {
        id: label
        x: banner.padX + banner.iconSize + Metrics.n("oem.samsung.osd.icon.gap", 12); y: banner.padY
        text: banner.text
        // Plain Segoe UI (OSDHandler's CreateTextFormat), not the shell's Segoe UI Variable.
        font.family: "Segoe UI"; font.pixelSize: Metrics.n("oem.samsung.osd.font", 14)
        color: Metrics.col("oem.samsung.osd.text")
    }
}

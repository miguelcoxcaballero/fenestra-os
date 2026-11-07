// SPDX-License-Identifier: GPL-3.0-or-later
// Windows 11's volume / brightness banner (Q03) and the shell's banners built like it: microphone,
// keyboard backlight (laptops other than Galaxy Books, whose maker draws its own: OemBanner) and
// the power mode key (text, no slider). Geometry, glyph, slider, value and motion as measured on
// the Windows 11 reference VM (design/tokens.json osd.*, design/motion.json osd); material: the
// flyouts' acrylic (Acrylic "panel" with the popup shadow and light edge, as Quick settings),
// computed from what is behind (BackdropHost) with KWin's blur until it is ready.
// Never takes focus or input.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: osd
    property var targetScreen
    property string kind: "volume"   // volume | brightness | microphone | keyboard | performance
    property int value: 0            // 0–100, -1 = muted
    property string text             // text banners (performance)
    property string textGlyph
    readonly property bool textOnly: kind === "performance" || kind === "microphone"
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowTransparentForInput
    visible: false
    readonly property int margin: Metrics.tok("popup.shadow.margin", 28)
    readonly property int gap: Metrics.n("osd.gap", 24)
    readonly property int pillWidth: textOnly ? Math.max(Metrics.osdHeight, Metrics.n("osd.glyph.x", 16) + 16 + Metrics.n("osd.text.gap", 12)
                                                         + Math.ceil(label.implicitWidth) + Metrics.n("osd.glyph.x", 16))
                                              : Metrics.osdWidth
    // The surface: the pill with its shadow room at the sides and top, down to the taskbar's top
    // edge (the pill rises from behind it).
    width: pillWidth + 2 * margin
    height: margin + Metrics.osdHeight + gap
    LayerShell.Window.scope: "fenestra-osd"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom
    LayerShell.Window.margins.bottom: 0
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    Component.onCompleted: ShellUtil.keepScene(this)

    property bool shown: false
    function present() {
        if (!shown) {
            if (!visible && targetScreen) ShellUtil.placeOnScreen(osd, targetScreen.name)
            const wasVisible = visible
            shown = true
            visible = true
            osdMotion.enter()   // also brings it back up while it was going down
            if (!wasVisible) backdrop.start()
        }
        hideTimer.restart()
    }
    function show(k, v) {
        kind = k; value = v
        present()
    }
    function showText(k, t, glyph) {
        kind = k; text = t; textGlyph = glyph || ""
        present()
    }
    onPillWidthChanged: if (visible) backdrop.start()

    readonly property string glyph: {
        // Segoe Fluent Icons, as the Windows banner: Volume0-3 / Mute, Brightness, Microphone.
        if (kind === "brightness") return ""
        if (kind === "keyboard") return ""
        if (kind === "microphone") return value < 0 ? "" : ""
        if (kind === "performance") return textGlyph
        if (value < 0) return ""
        return value === 0 ? "" : value < 34 ? "" : value < 67 ? "" : ""
    }
    readonly property string fallback: {
        if (kind === "brightness") return Metrics.assets + "osd/brightness.svg"
        if (kind === "keyboard") return "keyboard-brightness-symbolic"
        if (kind === "microphone") return Metrics.assets + "osd/" + (value < 0 ? "mic" : "mic-off") + ".svg"
        if (kind === "performance") return "power-profile-performance-symbolic"
        if (value <= 0) return Metrics.assets + "osd/" + (value < 0 ? "speaker-mute" : "speaker-0") + ".svg"
        return Metrics.assets + "osd/" + (value < 34 ? "speaker-1" : value < 67 ? "speaker-2" : "speaker-3") + ".svg"
    }

    Timer { id: hideTimer; interval: Metrics.osdTimeout; onTriggered: { osd.shown = false; osdMotion.leave() } }
    PopupMotion {
        id: osdMotion
        kind: "taskbar"
        target: pill
        travel: Metrics.osdHeight + osd.gap
        onGone: { osd.visible = false; backdrop.stop() }
    }
    BackdropHost {
        id: backdrop
        window: osd
        acrylics: [material]
        shift: osdMotion.shift
        area: osd.targetScreen ? Qt.rect(Math.round((osd.targetScreen.width - osd.pillWidth) / 2),
                                         osd.targetScreen.height - Metrics.taskbarHeight - osd.gap - Metrics.osdHeight,
                                         osd.pillWidth, Metrics.osdHeight + osd.gap) : Qt.rect(0, 0, 0, 0)
        originOf: function (a) { return Qt.point(area.x, area.y) }
    }
    Connections { target: osdMotion.shift; function onYChanged() { if (!backdrop.acrylicOn) backdrop.updateBlur() } }

    Item {
        id: pill
        x: osd.margin; y: osd.margin
        width: osd.pillWidth; height: Metrics.osdHeight
        transform: osdMotion.shift
        Acrylic {
            id: material
            anchors.fill: parent
            recipe: "panel"
            radius: Metrics.n("osd.radius", 8)
        }
        FluentGlyph {
            x: Metrics.n("osd.glyph.x", 16); anchors.verticalCenter: parent.verticalCenter
            size: Metrics.n("osd.glyph.size", 16)
            glyph: osd.glyph; fallback: osd.fallback
        }
        Slider {
            visible: !osd.textOnly
            x: Metrics.n("osd.slider.x", 48) - thumb / 2; anchors.verticalCenter: parent.verticalCenter
            width: Metrics.n("osd.slider.width", 104) + thumb
            value: Math.max(0, osd.value); enabled_: false
        }
        Text {
            visible: !osd.textOnly
            anchors.right: parent.right; anchors.rightMargin: Metrics.n("osd.value.right", 16)
            anchors.verticalCenter: parent.verticalCenter
            text: Math.max(0, osd.value)
            color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.n("osd.value.font", 14)
        }
        Text {
            id: label
            visible: osd.textOnly
            x: Metrics.n("osd.glyph.x", 16) + 16 + Metrics.n("osd.text.gap", 12); anchors.verticalCenter: parent.verticalCenter
            text: osd.kind === "microphone" ? Strings.tr(osd.value < 0 ? "Microphone on" : "Microphone muted") : osd.text
            color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.n("osd.value.font", 14)
        }
        AcrylicOutline { acrylic: material }
    }
}

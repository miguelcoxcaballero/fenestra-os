// SPDX-License-Identifier: GPL-3.0-or-later
// Volume / brightness / microphone OSD (Q03, osdStyle.js): a 192 × 48 pill centred 24 px above the
// taskbar, glyph + slider + value; 1.5 s, fade 150 ms with an 8 px rise. Never takes focus.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: osd
    property var targetScreen
    property string kind: "volume"
    property int value: 0          // 0–100, -1 = muted
    color: "transparent"
    width: 192 + 32; height: 48 + 32
    visible: false
    LayerShell.Window.scope: "fenestra-osd"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom
    LayerShell.Window.margins.bottom: 24 - 16
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    function show(k, v) {
        kind = k; value = v
        if (!visible) {
            if (targetScreen) ShellUtil.placeOnScreen(osd, targetScreen.name)
            visible = true
            pill.opacity = 0; pill.y = 24
            fadeIn.restart()
        }
        hideTimer.restart()
    }
    readonly property string glyph: {
        if (kind === "brightness") return "brightness"
        if (kind === "microphone") return value < 0 ? "mic" : "mic-off"
        if (value < 0 || value === 0) return value < 0 ? "speaker-mute" : "speaker-0"
        return value < 34 ? "speaker-1" : value < 67 ? "speaker-2" : "speaker-3"
    }

    Timer { id: hideTimer; interval: 1500; onTriggered: fadeOut.restart() }
    ParallelAnimation {
        id: fadeIn
        NumberAnimation { target: pill; property: "opacity"; to: 1; duration: Motion.reduced ? 0 : 150; easing.type: Easing.OutCubic }
        NumberAnimation { target: pill; property: "y"; to: 16; duration: Motion.reduced ? 0 : 150; easing.type: Easing.OutCubic }
    }
    SequentialAnimation {
        id: fadeOut
        ParallelAnimation {
            NumberAnimation { target: pill; property: "opacity"; to: 0; duration: Motion.reduced ? 0 : 150; easing.type: Easing.InQuad }
            NumberAnimation { target: pill; property: "y"; to: 20; duration: Motion.reduced ? 0 : 150; easing.type: Easing.InQuad }
        }
        ScriptAction { script: osd.visible = false }
    }

    Rectangle {
        id: pill
        x: 16; y: 16; width: 192; height: 48; radius: 8
        color: Theme.dark ? Qt.rgba(32 / 255, 32 / 255, 32 / 255, 0.85) : Qt.rgba(249 / 255, 249 / 255, 249 / 255, 0.92)
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)
        Row {
            x: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 12
            SymbolicIcon { anchors.verticalCenter: parent.verticalCenter; src: Metrics.assets + "osd/" + osd.glyph + ".svg" }
            // Microphone without a level: text instead of the slider.
            Text {
                visible: osd.kind === "microphone"
                anchors.verticalCenter: parent.verticalCenter
                text: Strings.tr(osd.value < 0 ? "Microphone on" : "Microphone muted")
                color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14
            }
            Slider { visible: osd.kind !== "microphone"; anchors.verticalCenter: parent.verticalCenter; width: 104
                     value: Math.max(0, osd.value); enabled_: false }
            Text { visible: osd.kind !== "microphone"; anchors.verticalCenter: parent.verticalCenter; width: 24
                   horizontalAlignment: Text.AlignRight; text: Math.max(0, osd.value)
                   color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
        }
    }
}

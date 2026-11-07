// SPDX-License-Identifier: GPL-3.0-or-later
// Volume / brightness / microphone OSD (Q03, osdStyle.js): a 192 × 48 pill centred 24 px above the
// taskbar, glyph + slider + value; 1.5 s. Never takes focus. Motion: no OSD frames in the reference
// (no media keys in the VM), so it rises from behind the taskbar like Quick settings (PopupMotion
// "taskbar", design/motion.json): the surface reaches down to the taskbar's top edge.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: osd
    property var targetScreen
    property string kind: "volume"
    property int value: 0          // 0–100, -1 = muted
    color: "transparent"
    width: Metrics.osdWidth + 32; height: Metrics.osdHeight + 16 + Metrics.osdGap
    visible: false
    LayerShell.Window.scope: "fenestra-osd"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom
    LayerShell.Window.margins.bottom: 0
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    function show(k, v) {
        kind = k; value = v
        if (!visible) {
            if (targetScreen) ShellUtil.placeOnScreen(osd, targetScreen.name)
            visible = true
            osdMotion.enter()
        } else if (osdMotion.busy) {
            osdMotion.enter()   // shown again while going down: back up
        }
        hideTimer.restart()
    }
    readonly property string glyph: {
        if (kind === "brightness") return "brightness"
        if (kind === "microphone") return value < 0 ? "mic" : "mic-off"
        if (value < 0 || value === 0) return value < 0 ? "speaker-mute" : "speaker-0"
        return value < 34 ? "speaker-1" : value < 67 ? "speaker-2" : "speaker-3"
    }

    Timer { id: hideTimer; interval: Metrics.osdTimeout; onTriggered: osdMotion.leave() }
    PopupMotion {
        id: osdMotion
        kind: "taskbar"
        target: pill
        travel: osd.height - pill.y
        onGone: osd.visible = false
    }

    Rectangle {
        id: pill
        x: 16; y: 16; width: Metrics.osdWidth; height: Metrics.osdHeight; radius: 8
        transform: osdMotion.shift
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

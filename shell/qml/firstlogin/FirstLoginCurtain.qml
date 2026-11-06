// SPDX-License-Identifier: GPL-3.0-or-later
// First login (W05): the desktop is never seen half-built. Black from the shell's start until the
// setup window (org.fenestra.Oobe) appears; black again when it closes (continuing its black
// finale), fading out once the desktop has settled. Only while ~/.config/gnome-initial-setup-done
// does not exist (the setup writes it). A 90 s safety timeout always removes it.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: curtain
    color: "black"
    property bool active: !ShellUtil.configFileExists("gnome-initial-setup-done")
    property bool oobeSeen: false
    readonly property bool oobeOpen: {
        for (let i = 0; i < WindowsModel.count; ++i)
            if (WindowsModel.data(WindowsModel.index(i, 0), 258) === "org.fenestra.Oobe") return true   // AppIdRole
        return false
    }
    visible: active
    LayerShell.Window.scope: "fenestra-curtain"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    onOobeOpenChanged: {
        if (!active) return
        if (oobeOpen) { oobeSeen = true; fade.stop(); veil.opacity = 1; curtain.visible = false }
        else if (oobeSeen) { curtain.visible = true; veil.opacity = 1; settle.restart() }
    }
    // The setup did not start (or it is not installed): uncover once the desktop is up.
    Timer { interval: 8000; running: curtain.active && !curtain.oobeSeen; onTriggered: if (!curtain.oobeOpen) settle.restart() }
    Timer { id: settle; interval: 1500; onTriggered: fade.restart() }
    Timer { interval: 90000; running: curtain.active; onTriggered: { curtain.active = false; curtain.visible = false } }   // safety
    SequentialAnimation {
        id: fade
        NumberAnimation { target: veil; property: "opacity"; to: 0; duration: Motion.reduced ? 0 : 400; easing.type: Easing.OutQuad }
        ScriptAction { script: { curtain.active = false; curtain.visible = false } }
    }
    Rectangle { id: veil; anchors.fill: parent; color: "black" }
}

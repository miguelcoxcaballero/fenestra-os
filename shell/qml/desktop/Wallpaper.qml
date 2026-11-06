// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: win
    required property var targetScreen
    property url source: "file://" + ShellSettings.wallpaper

    color: "black"
    // Shown only once the screen is set: a layer surface binds to its output when it is created.
    visible: false
    Component.onCompleted: { ShellUtil.placeOnScreen(win, targetScreen.name); visible = true }
    LayerShell.Window.screenConfiguration: LayerShell.Window.ScreenFromQWindow
    LayerShell.Window.scope: "fenestra-wallpaper"
    LayerShell.Window.layer: LayerShell.Window.LayerBackground
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1   // cover the whole output, under the taskbar too
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    Image {
        anchors.fill: parent
        source: win.source
        fillMode: Image.PreserveAspectCrop   // background-size: cover, as on GNOME
        asynchronous: true
        // Decode at the output size only, not the full picture.
        sourceSize: Qt.size(win.width * Screen.devicePixelRatio, win.height * Screen.devicePixelRatio)
    }
}

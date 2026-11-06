// SPDX-License-Identifier: GPL-3.0-or-later
// Notification banners (N02): bottom-right, 12 px over the taskbar and 13 px from the edge,
// newest at the bottom; slide in from the right. Never take the keyboard focus.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: toasts
    property var targetScreen
    color: "transparent"
    width: Metrics.toastWidth + 2 * 8
    height: Math.max(1, stack.height + 16)
    visible: Notifications.popups.length > 0
    LayerShell.Window.scope: "fenestra-toasts"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorRight
    LayerShell.Window.margins.bottom: Metrics.flyoutGap - 8
    LayerShell.Window.margins.right: Metrics.flyoutEdge - 8
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    Component.onCompleted: if (targetScreen) ShellUtil.placeOnScreen(toasts, targetScreen.name)

    Column {
        id: stack
        x: 8; y: 8; width: Metrics.toastWidth
        spacing: 8
        Repeater {
            model: Notifications.popups.slice(-3)
            delegate: NotificationCard {
                required property var modelData
                n: modelData
                banner: true
                width: Metrics.toastWidth
                onCloseRequested: Notifications.hidePopup(modelData.notificationId)
                NumberAnimation on x { from: 380; to: 0; duration: 250; easing.type: Easing.OutCubic; running: !Motion.reduced }
            }
        }
    }
}

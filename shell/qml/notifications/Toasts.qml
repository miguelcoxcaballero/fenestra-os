// SPDX-License-Identifier: GPL-3.0-or-later
// Notification banners (N02): bottom-right, 13 px over the taskbar and 16 px from the edge
// (dark-100-17-toast: 364 px wide, radius 7), newest at the bottom; slide in from beyond the right
// edge like the Notification Center (PopupMotion "edge", design/motion.json), and back out when closed.
// The surface reaches the screen edge so that the banner is clipped there while it moves.
// Never take the keyboard focus.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: toasts
    property var targetScreen
    color: "transparent"
    width: Metrics.toastWidth + 8 + Metrics.n("toast.edge", 16)
    height: Math.max(1, stack.height + 16)
    visible: Notifications.popups.length > 0
    LayerShell.Window.scope: "fenestra-toasts"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorRight
    LayerShell.Window.margins.bottom: Metrics.n("toast.gap", 13) - 8
    LayerShell.Window.margins.right: 0
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
                id: toast
                required property var modelData
                n: modelData
                banner: true
                width: Metrics.toastWidth
                transform: toastMotion.shift
                onCloseRequested: toastMotion.leave()
                PopupMotion {
                    id: toastMotion
                    kind: "edge"
                    travel: Metrics.toastWidth + Metrics.n("toast.edge", 16)
                    onGone: Notifications.hidePopup(toast.modelData.notificationId)
                }
                Component.onCompleted: toastMotion.enter()
            }
        }
    }
}

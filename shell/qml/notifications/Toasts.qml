// SPDX-License-Identifier: GPL-3.0-or-later
// Notification banners (N02): bottom-right, 13 px over the taskbar and 16 px from the edge
// (dark-100-17-toast: 364 px wide, radius 7), newest at the bottom; slide in from beyond the right
// edge like the Notification Center (PopupMotion "edge", design/motion.json), and back out when closed.
// Material: acrylic (user-win11 160049: Start's header material and edge, with the popup shadow):
// KWin's blur under the fallback fill, then the real acrylic (core/backdrop.h, BackdropHost).
// The surface reaches the screen edge so that the banner is clipped there while it moves, and is
// larger than the banners by the shadow's margin; its input region is the banners only.
// Never take the keyboard focus.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: toasts
    property var targetScreen
    readonly property int edge: Metrics.n("toast.edge", 16)
    readonly property int gap: Metrics.n("toast.gap", 13)
    readonly property int margin: Metrics.tok("popup.shadow.margin", 28)
    color: "transparent"
    width: margin + Metrics.toastWidth + edge
    height: Math.max(1, margin + stack.height + gap)
    visible: Notifications.popups.length > 0
    LayerShell.Window.scope: "fenestra-toasts"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorRight
    LayerShell.Window.margins.bottom: 0
    LayerShell.Window.margins.right: 0
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    Component.onCompleted: { if (targetScreen) ShellUtil.placeOnScreen(toasts, targetScreen.name); ShellUtil.keepScene(this) }

    readonly property var cards: {
        const out = []
        for (let i = 0; i < repeater.count; ++i) { const c = repeater.itemAt(i); if (c) out.push(c) }
        return out
    }
    // Screen rectangle the banners cover, out to the screen's right edge (they slide in from there).
    readonly property rect screenArea: targetScreen ? Qt.rect(targetScreen.width - edge - Metrics.toastWidth,
                                                              targetScreen.height - Metrics.taskbarHeight - gap - stack.height,
                                                              Metrics.toastWidth + edge, stack.height) : Qt.rect(0, 0, 0, 0)
    function refresh() {
        ShellUtil.setInputItems(toasts, cards)
        backdrop.acrylics = cards.map(c => c.material)
        if (visible && cards.length) backdrop.start(); else backdrop.stop()
    }
    Timer { id: settle; interval: 0; onTriggered: toasts.refresh() }
    onVisibleChanged: settle.restart()
    onHeightChanged: settle.restart()

    BackdropHost {
        id: backdrop
        window: toasts
        blurRadius: Metrics.n("toast.radius", 7)
        area: toasts.screenArea
        // Where each banner rests on the screen; its slide is its own (PopupMotion per banner).
        originOf: function (a) {
            const p = a.mapToItem(stack, 0, 0)
            return Qt.point(toasts.screenArea.x, toasts.screenArea.y + p.y)
        }
    }

    Column {
        id: stack
        x: toasts.margin; y: toasts.margin; width: Metrics.toastWidth
        spacing: 8
        onHeightChanged: settle.restart()
        Repeater {
            id: repeater
            model: Notifications.popups.slice(-3)
            onCountChanged: settle.restart()
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
                    travel: Metrics.toastWidth + toasts.edge
                    onGone: Notifications.hidePopup(toast.modelData.notificationId)
                }
                Connections { target: toastMotion.shift; function onXChanged() { if (!backdrop.acrylicOn) backdrop.updateBlur() } }
                Component.onCompleted: { toastMotion.enter(); material.backdrop.shift = toastMotion.shift }
            }
        }
    }
}

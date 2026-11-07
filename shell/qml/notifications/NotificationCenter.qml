// SPDX-License-Identifier: GPL-3.0-or-later
// Notification Center + calendar (N01), as two separate cards 336 px wide, 12 px apart, 12 px over
// the taskbar and 12 px from the edge (dark-100-15-notifications*, dark-100-16-calendar*).
// Empty: a 232 px card with "No new notifications". With notifications the card reaches 8 px from
// the top of the screen; they are grouped by app (header row with icon and name), each group
// showing its newest notification and a "+ N notifications" button that unfolds the rest.
import QtQuick
import Fenestra.Shell

Flyout {
    id: center
    padding: 0
    background.visible: false
    recipe: "panel"
    blurItems: [notifCard.material, calendar.material]
    property alias calendar: calendar
    readonly property int topMargin: 8
    property int availableHeight: targetScreen ? targetScreen.height - Metrics.taskbarHeight - 2 * Metrics.flyoutGap - topMargin : 800
    property var groups: []           // [{appName, appIcon, items: [n, ...]}], newest first
    property var expanded: ({})       // appName -> true
    onDismissed: expanded = ({})

    function rebuild() {
        const out = [], byApp = {}
        for (let i = 0; i < Notifications.count; ++i) {
            const ix = Notifications.index(i, 0)
            const n = { notificationId: Notifications.data(ix, 257), appName: Notifications.data(ix, 258), appIcon: Notifications.data(ix, 259),
                        summary: Notifications.data(ix, 260), body: Notifications.data(ix, 261), actions: Notifications.data(ix, 262) || [],
                        image: Notifications.data(ix, 263) || "", time: Notifications.data(ix, 264),
                        value: Notifications.data(ix, 267) }
            if (!byApp[n.appName]) { byApp[n.appName] = { appName: n.appName, appIcon: n.appIcon, items: [] }; out.push(byApp[n.appName]) }
            byApp[n.appName].items.push(n)
        }
        groups = out
    }
    Component.onCompleted: rebuild()
    Connections {
        target: Notifications
        function onCountChanged() { center.rebuild() }
        function onDataChanged() { center.rebuild() }
    }

    component HeaderButton: Rectangle {
        id: hb
        property bool on: false
        height: Metrics.n("notifications.button.height", 24); radius: Metrics.controlRadius
        color: on ? Theme.accentFill : hm.pressed ? Theme.pressed : hm.containsMouse ? Qt.tint(Metrics.pcol("notifications.button"), Theme.hover)
                                                                : Metrics.pcol("notifications.button")
        border.color: on ? "transparent" : Metrics.pcol("notifications.button.border")
        signal clicked()
        MouseArea { id: hm; anchors.fill: parent; hoverEnabled: true; onClicked: hb.clicked() }
    }

    // Opening and closing: both cards slide in from the right screen edge (design/motion.json).
    motion: "edge"

    Column {
        spacing: Metrics.flyoutGap
        Card {
            id: notifCard
            width: Metrics.notificationsWidth
            // The darker acrylic (fallback #1c1c1c, panel.fill.alt).
            recipe: "base"
            readonly property int headerH: Metrics.n("notifications.header.height", 50)
            height: Notifications.count === 0 ? Metrics.n("notifications.empty.height", 232)
                                              : Math.max(Metrics.n("notifications.empty.height", 232), center.availableHeight - calendar.height)
            clip: true
            Text { x: 17; y: 15; text: Strings.tr("Notifications")
                   color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
            Row {
                anchors { right: parent.right; rightMargin: Notifications.count > 0 ? 17 : 16 }
                y: 12; spacing: 7; layoutDirection: Qt.RightToLeft
                HeaderButton {
                    visible: Notifications.count > 0
                    y: 1; width: clearLabel.implicitWidth + 20
                    Text { id: clearLabel; anchors.centerIn: parent; text: Strings.tr("Clear all"); color: Theme.text
                           font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                    onClicked: Notifications.clearAll()
                }
                // Do not disturb (bell with a z).
                HeaderButton {
                    width: Metrics.n("notifications.dnd", 26); height: width
                    on: Notifications.doNotDisturb
                    Accessible.name: Strings.tr("Do not disturb")
                    Accessible.checked: Notifications.doNotDisturb
                    // Bell with a «z» (dark-100-15-notifications-2), drawn thin and dimmed like the reference.
                    Image { anchors.centerIn: parent; width: 13; height: 13
                            sourceSize: Qt.size(13 * Screen.devicePixelRatio, 13 * Screen.devicePixelRatio)
                            opacity: Notifications.doNotDisturb ? 1 : 0.75
                            source: "image://tint/" + (Notifications.doNotDisturb ? Theme.accentOn : Theme.text).toString().slice(1, 7) + "/"
                                    + encodeURIComponent(Metrics.assets + "status/notifications-dnd.svg") }
                    onClicked: Notifications.doNotDisturb = !Notifications.doNotDisturb
                }
            }
            Text {
                visible: Notifications.count === 0
                y: notifCard.headerH; width: parent.width; height: parent.height - notifCard.headerH
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                text: Strings.tr("No new notifications"); color: Theme.text
                font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
            }
            Flickable {
                visible: Notifications.count > 0
                y: notifCard.headerH; width: parent.width; height: parent.height - notifCard.headerH - 1
                contentHeight: groupColumn.height; clip: true
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: groupColumn
                    width: parent.width
                    Repeater {
                        model: center.groups
                        delegate: Column {
                            id: group
                            required property var modelData
                            readonly property bool open: center.expanded[modelData.appName] === true
                            width: groupColumn.width
                            // App row: 16 px icon at x 17, name at x 40.
                            Item {
                                width: parent.width; height: 42
                                Image { x: 17; y: 11; width: 16; height: 16; sourceSize: Qt.size(32, 32)
                                        source: { const i = group.modelData.appIcon || "dialog-information"
                                                  return i.startsWith("/") ? "file://" + i : i.includes(":") ? i : "image://icon/" + i } }
                                Text { x: 40; y: 10; width: parent.width - 56; elide: Text.ElideRight; text: group.modelData.appName
                                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                            }
                            Column {
                                x: Metrics.n("notifications.card.inset", 6) - 1; width: parent.width - 2 * x; spacing: 8
                                Repeater {
                                    model: group.open ? group.modelData.items : group.modelData.items.slice(0, 1)
                                    delegate: NotificationCard {
                                        required property var modelData
                                        required property int index
                                        width: parent.width
                                        n: modelData
                                        more: !group.open && index === 0 ? group.modelData.items.length - 1 : 0
                                        onCloseRequested: Notifications.dismiss(modelData.notificationId)
                                        onExpandRequested: { const e = Object.assign({}, center.expanded); e[group.modelData.appName] = true; center.expanded = e }
                                    }
                                }
                            }
                            Item { width: 1; height: 12 }
                        }
                    }
                }
            }
        }
        CalendarCard { id: calendar }
    }
}

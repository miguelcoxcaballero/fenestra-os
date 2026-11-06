// SPDX-License-Identifier: GPL-3.0-or-later
// Notification centre + calendar (N01): two separate cards, 332 px wide, 12 px apart, 12 px over the
// taskbar, 13 px from the edge (calendarPanel.js). Notifications grouped by app, newest first.
import QtQuick
import Fenestra.Shell

Flyout {
    id: center
    padding: 0
    background.visible: false
    property int availableHeight: targetScreen ? targetScreen.height - Metrics.taskbarHeight - 3 * Metrics.flyoutGap : 800

    Column {
        spacing: 12
        Card {
            width: 332
            height: Math.min(Math.max(120, center.availableHeight - calendar.height), notifColumn.height)
            clip: true
            Column {
                id: notifColumn
                width: parent.width
                Item {
                    width: parent.width; height: 44
                    Text { x: 16; anchors.verticalCenter: parent.verticalCenter; text: Strings.tr("Notifications")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                    Row {
                        anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                        spacing: 8
                        Rectangle {
                            visible: Notifications.count > 0
                            width: clearLabel.implicitWidth + 20; height: 22; radius: 4
                            color: clm.containsMouse ? Qt.rgba(1, 1, 1, Theme.dark ? 0.10 : 0.9) : Qt.rgba(1, 1, 1, Theme.dark ? 0.06 : 0.7)
                            border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
                            Text { id: clearLabel; anchors.centerIn: parent; text: Strings.tr("Clear all"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                            MouseArea { id: clm; anchors.fill: parent; hoverEnabled: true; onClicked: Notifications.clearAll() }
                        }
                        // Do not disturb (bell with a z).
                        Rectangle {
                            width: 22; height: 22; radius: 4
                            color: Notifications.doNotDisturb ? Theme.accentFill : (dm.containsMouse ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(1, 1, 1, Theme.dark ? 0.06 : 0.7))
                            border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
                            Accessible.name: Strings.tr("Do not disturb")
                            Accessible.checked: Notifications.doNotDisturb
                            Image { anchors.centerIn: parent; width: 16; height: 16
                                    source: "image://tint/" + (Notifications.doNotDisturb ? Theme.accentOn : Theme.text).toString().slice(1, 7) + "/notifications-disabled-symbolic" }
                            MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true; onClicked: Notifications.doNotDisturb = !Notifications.doNotDisturb }
                        }
                    }
                }
                Column {
                    x: 8; width: parent.width - 16; spacing: 8; bottomPadding: 8
                    Repeater {
                        model: Notifications
                        delegate: NotificationCard {
                            required property var model
                            width: parent.width
                            n: ({ notificationId: model.notificationId, appName: model.appName, appIcon: model.appIcon, summary: model.summary,
                                  body: model.body, actions: model.actions, image: model.image, time: model.time })
                            onCloseRequested: Notifications.dismiss(model.notificationId)
                        }
                    }
                    Text {
                        visible: Notifications.count === 0
                        width: parent.width; horizontalAlignment: Text.AlignHCenter; topPadding: 16; bottomPadding: 28
                        text: Strings.tr("No new notifications"); color: Theme.dark ? "#c5c5c5" : "#5c5c5c"
                        font.family: Metrics.fontFamily; font.pixelSize: 14
                    }
                }
            }
        }
        CalendarCard { id: calendar }
    }
}

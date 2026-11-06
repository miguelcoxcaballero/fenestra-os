// SPDX-License-Identifier: GPL-3.0-or-later
// Calendar card (N01): long date header with collapse, month with ▲ ▼, weeks starting on the
// locale's first day, today in the accent, and the Focus footer (5–240 min, banners off meanwhile).
import QtQuick
import Fenestra.Shell

Card {
    id: cal
    width: 332
    height: header.height + (collapsed ? 0 : month.height) + focus.height
    color: Theme.dark ? Qt.rgba(36 / 255, 36 / 255, 36 / 255, 0.97) : Qt.rgba(249 / 255, 249 / 255, 249 / 255, 0.94)
    property bool collapsed: false
    property date shown: new Date()
    property int focusMinutes: 30
    readonly property date today: new Date()
    function capital(s) { return s.charAt(0).toUpperCase() + s.slice(1) }

    Rectangle {
        id: header
        width: parent.width; height: 48
        topLeftRadius: 7; topRightRadius: 7
        color: Theme.dark ? "#1c1c1c" : Qt.rgba(1, 1, 1, 0.6)
        Text { x: 16; anchors.verticalCenter: parent.verticalCenter
               text: cal.capital(cal.today.toLocaleDateString(Qt.locale(), "dddd, d MMMM"))
               color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
        Rectangle { anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
            width: 22; height: 22; radius: 4
                    color: col.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.centerIn: parent; text: cal.collapsed ? "⌃" : "⌄"; color: Theme.text; font.pixelSize: 12 }
                    MouseArea { id: col; anchors.fill: parent; hoverEnabled: true; onClicked: cal.collapsed = !cal.collapsed } }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.dark ? "#191919" : Qt.rgba(0, 0, 0, 0.06) }
    }
    Column {
        id: month
        visible: !cal.collapsed
        y: header.height; width: parent.width
        Item {
            width: parent.width; height: 56
            Text { x: 16; anchors.verticalCenter: parent.verticalCenter
                   text: cal.capital(cal.shown.toLocaleDateString(Qt.locale(), "MMMM yyyy"))
                   color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
            Row {
                anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                Repeater {
                    model: [["▲", -1], ["▼", 1]]
                    delegate: Rectangle {
                        required property var modelData
                        width: 39; height: 32; radius: 4; color: pm.containsMouse ? Theme.hover : "transparent"
                        Text { anchors.centerIn: parent; text: modelData[0]; color: "#9d9d9d"; font.pixelSize: 9 }
                        MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true
                            onClicked: cal.shown = new Date(cal.shown.getFullYear(), cal.shown.getMonth() + modelData[1], 1) }
                    }
                }
            }
        }
        Grid {
            x: 8; columns: 7; columnSpacing: 0
            // Weekday headings: first two letters of the locale's names.
            Repeater {
                model: 7
                delegate: Text {
                    required property int index
                    width: 45; height: 32; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    text: Qt.locale().dayName((Qt.locale().firstDayOfWeek + index) % 7, Locale.ShortFormat).slice(0, 2)
                    color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12
                }
            }
            Repeater {
                model: 42
                delegate: Item {
                    required property int index
                    readonly property date first: new Date(cal.shown.getFullYear(), cal.shown.getMonth(), 1)
                    readonly property int offset: (first.getDay() - Qt.locale().firstDayOfWeek + 7) % 7
                    readonly property date day: new Date(first.getFullYear(), first.getMonth(), 1 - offset + index)
                    readonly property bool isToday: day.toDateString() === cal.today.toDateString()
                    readonly property bool other: day.getMonth() !== cal.shown.getMonth()
                    width: 45; height: 42
                    Rectangle { anchors.centerIn: parent; width: 40; height: 40; radius: 20
                                color: parent.isToday ? Theme.accentFill : dm.containsMouse ? Theme.hover : "transparent" }
                    Text { anchors.centerIn: parent; text: parent.day.getDate(); font.family: Metrics.fontFamily; font.pixelSize: 14
                           font.features: { "tnum": 1 }
                           color: parent.isToday ? Theme.accentOn : parent.other ? "#7f7f7f" : Theme.text }
                    MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true }
                }
            }
        }
        Item { width: 1; height: 8 }
    }
    Rectangle {
        id: focus
        anchors.bottom: parent.bottom
        width: parent.width; height: 48
        bottomLeftRadius: 7; bottomRightRadius: 7
        color: "transparent"
        Rectangle { width: parent.width; height: 1; color: Theme.dark ? "#191919" : Qt.rgba(0, 0, 0, 0.06) }
        Row {
            x: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 8
            visible: Notifications.focusRemaining === 0
            Repeater {
                model: ["−", "+"]
                delegate: Rectangle {
                    required property string modelData
                    required property int index
                    width: 22; height: 22; radius: 4; color: fm.containsMouse ? Theme.hover : Qt.rgba(1, 1, 1, Theme.dark ? 0.06 : 0.7)
                    Text { anchors.centerIn: parent; text: modelData; color: Theme.text; font.pixelSize: 13 }
                    MouseArea { id: fm; anchors.fill: parent; hoverEnabled: true
                        onClicked: cal.focusMinutes = Math.max(5, Math.min(240, cal.focusMinutes + (index ? 5 : -5))) }
                }
            }
            Text { anchors.verticalCenter: parent.verticalCenter; text: cal.focusMinutes + " " + Strings.tr("mins")
                   color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
        }
        Text {
            x: 16; anchors.verticalCenter: parent.verticalCenter
            visible: Notifications.focusRemaining > 0
            text: Math.floor(Notifications.focusRemaining / 60) + ":" + String(Notifications.focusRemaining % 60).padStart(2, "0")
            color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold
        }
        Rectangle {
            anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
            width: focusLabel.implicitWidth + 24; height: 22; radius: 4
            color: fb.containsMouse ? Theme.accentHover : Theme.accentFill
            Text { id: focusLabel; anchors.centerIn: parent; text: Strings.tr(Notifications.focusRemaining > 0 ? "End session" : "Focus")
                   color: Theme.accentOn; font.family: Metrics.fontFamily; font.pixelSize: 12 }
            MouseArea { id: fb; anchors.fill: parent; hoverEnabled: true
                onClicked: Notifications.focusRemaining > 0 ? Notifications.endFocus() : Notifications.startFocus(cal.focusMinutes) }
        }
    }
}

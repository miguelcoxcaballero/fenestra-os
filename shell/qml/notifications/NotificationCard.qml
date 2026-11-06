// SPDX-License-Identifier: GPL-3.0-or-later
// One notification (centre row and banner): source line with icon, app and time, close button;
// 48 px app icon (or image thumbnail), title, body, action buttons (calendarPanel.js / stylesheet.css).
import QtQuick
import Fenestra.Shell

Rectangle {
    id: card
    property var n            // {notificationId, appName, appIcon, summary, body, actions, image, time}
    property bool banner: false
    signal closeRequested()
    width: parent ? parent.width : 332
    height: column.height + 14
    radius: 6
    color: Theme.dark ? (hover.containsMouse ? "#2a2a2a" : "#242424") : (hover.containsMouse ? Qt.rgba(1, 1, 1, 0.95) : Qt.rgba(1, 1, 1, 0.85))
    border.color: banner ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)) : "transparent"
    readonly property bool isImage: n && n.image && n.image !== "" && !n.image.startsWith("image://icon")
    function iconUrl(icon) {
        if (!icon) return "image://icon/dialog-information"
        if (icon.startsWith("/")) return "file://" + icon
        if (icon.startsWith("file:") || icon.startsWith("image:")) return icon
        return "image://icon/" + icon
    }
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: Notifications.invoke(card.n.notificationId, "default") }
    Column {
        id: column
        width: parent.width
        // Screenshot-style thumbnail on top (screenshotToast.js): up to 330 × 160.
        Rectangle {
            visible: card.isImage
            width: parent.width; height: visible ? Math.min(160, thumb.implicitHeight * (width - 32) / Math.max(1, thumb.implicitWidth)) + 24 : 0
            topLeftRadius: 6; topRightRadius: 6
            color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.04)
            Image { id: thumb; x: 16; y: 12; width: parent.width - 32; height: parent.height - 24; fillMode: Image.PreserveAspectFit
                    source: card.isImage ? card.n.image : ""; asynchronous: true }
        }
        Item {
            width: parent.width; height: 34
            Image { x: 12; y: 10; width: 16; height: 16; sourceSize: Qt.size(32, 32); source: card.iconUrl(card.n ? card.n.appIcon : "") }
            Text { x: 36; y: 10; width: parent.width - 110; elide: Text.ElideRight
                   text: card.n ? card.n.appName : ""; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
            Text { anchors { right: closeBtn.left; rightMargin: 6 }
            y: 10; visible: !card.banner && card.n && card.n.time !== undefined
                   text: card.n && card.n.time ? Qt.formatTime(card.n.time, Locale.ShortFormat) : ""
                   color: Theme.dark ? "#c5c5c5" : "#5c5c5c"; font.family: Metrics.fontFamily; font.pixelSize: 12 }
            Rectangle {
                id: closeBtn
                anchors { right: parent.right; rightMargin: 8 }
            y: 6; width: 24; height: 24; radius: 4
                visible: hover.containsMouse || cm.containsMouse || card.banner
                color: cm.containsMouse ? Theme.hover : "transparent"
                Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 11; color: Theme.text }
                Accessible.name: Strings.tr("Close")
                MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; onClicked: card.closeRequested() }
            }
        }
        Row {
            x: 12; spacing: 12; width: parent.width - 24
            Image { visible: !card.isImage && card.n && card.n.image !== ""; width: 48; height: 48; fillMode: Image.PreserveAspectFit
                    source: !card.isImage && card.n && card.n.image ? card.n.image : "" }
            Column {
                width: parent.width - (card.n && card.n.image && !card.isImage ? 60 : 0)
                spacing: 2
                Text { width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                       text: card.n ? card.n.summary : ""; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                Text { width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight; visible: text !== ""
                       text: card.n ? card.n.body : ""; color: Theme.dark ? "#c5c5c5" : "#5c5c5c"; font.family: Metrics.fontFamily; font.pixelSize: 14 }
            }
        }
        Row {
            visible: card.n && card.n.actions && card.n.actions.length > 0
            x: 12; topPadding: 12; spacing: 8
            Repeater {
                model: card.n ? card.n.actions.filter(a => a.key !== "default") : []
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: Math.max(96, label.implicitWidth + 24); height: 32; radius: 4
                    // First action on screenshots is the accent button (screenshotToast.js).
                    color: index === 0 && card.isImage ? (am.containsMouse ? Theme.accentHover : Theme.accentFill)
                           : (am.containsMouse ? Qt.rgba(1, 1, 1, Theme.dark ? 0.09 : 0.9) : Qt.rgba(1, 1, 1, Theme.dark ? 0.06 : 0.7))
                    border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
                    Text { id: label; anchors.centerIn: parent; text: modelData.label
                           color: index === 0 && card.isImage ? Theme.accentOn : Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                    MouseArea { id: am; anchors.fill: parent; hoverEnabled: true; onClicked: Notifications.invoke(card.n.notificationId, modelData.key) }
                }
            }
        }
    }
}

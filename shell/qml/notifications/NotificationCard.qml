// SPDX-License-Identifier: GPL-3.0-or-later
// One notification. Banner (toast, dark-100-17-toast): app line with icon, name, "…" and close;
// title and body below. Centre item (dark-100-15-notifications-2): time line, title, body; close on
// hover; the group's "+ N notifications" button under the newest one. Image notifications show
// the picture on top; action buttons go last. Positions in px from the card's outer edge.
import QtQuick
import Fenestra.Shell

Rectangle {
    id: card
    property var n            // {notificationId, appName, appIcon, summary, body, actions, image, time}
    property bool banner: false
    property int more: 0      // centre: other notifications of the same app, folded under this one
    signal closeRequested()
    signal expandRequested()
    width: parent ? parent.width : Metrics.toastWidth
    height: column.height
    radius: banner ? Metrics.n("toast.radius", 7) : Metrics.controlRadius
    color: banner ? Metrics.col("panel.fill.alt")
                  : hover.containsMouse ? Qt.tint(Metrics.col("notifications.card"), Theme.hover) : Metrics.col("notifications.card")
    border.color: banner ? Metrics.col("panel.border") : Metrics.col("notifications.card.border")
    border.width: 1
    readonly property bool isImage: n && n.image && n.image !== "" && !n.image.startsWith("image://icon")
    readonly property color secondary: Metrics.col("panel.text.secondary")
    function iconUrl(icon) {
        if (!icon) return "image://icon/dialog-information"
        if (icon.startsWith("/")) return "file://" + icon
        if (icon.startsWith("file:") || icon.startsWith("image:")) return icon
        return "image://icon/" + icon
    }
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: Notifications.invoke(card.n.notificationId, "default") }

    component Glyph: Rectangle {
        id: g
        property string glyph
        property int glyphSize: 12
        readonly property alias hovered: gm.containsMouse
        signal clicked()
        width: 24; height: 24; radius: Metrics.controlRadius
        color: gm.pressed ? Theme.pressed : gm.containsMouse ? Theme.hover : "transparent"
        SymbolicIcon { anchors.centerIn: parent; name: g.glyph; size: g.glyphSize; opacity: 0.75 }
        MouseArea { id: gm; anchors.fill: parent; hoverEnabled: true; onClicked: g.clicked() }
    }

    Column {
        id: column
        width: parent.width
        // Screenshot-style picture on top: up to 330 × 160.
        Item {
            visible: card.isImage
            width: parent.width; height: visible ? Math.min(160, thumb.implicitHeight * (width - 32) / Math.max(1, thumb.implicitWidth)) + 24 : 0
            Image { id: thumb; x: 16; y: 12; width: parent.width - 32; height: parent.height - 24; fillMode: Image.PreserveAspectFit
                    source: card.isImage ? card.n.image : ""; asynchronous: true }
        }
        // Banner: app line (icon 16 at 16,15; name at 40; "…" and close at the right).
        Item {
            visible: card.banner
            width: parent.width; height: visible ? 50 : 0
            Image { x: 16; y: 15; width: 16; height: 16; sourceSize: Qt.size(32, 32); source: card.iconUrl(card.n ? card.n.appIcon : "") }
            Text { x: 40; y: 13; width: parent.width - 120; elide: Text.ElideRight
                   text: card.n ? card.n.appName : ""; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            Glyph { x: 285; y: 11; Accessible.name: Strings.tr("More options")
                    Row { x: 6; y: 11; spacing: 3; Repeater { model: 3; Rectangle { width: 2; height: 2; radius: 1; color: Metrics.col("toast.glyph") } } } }
            Glyph { x: 325; y: 11; glyph: "window-close-symbolic"; glyphSize: 16; Accessible.name: Strings.tr("Close"); onClicked: card.closeRequested() }
        }
        // Centre: time line (and close on hover).
        Item {
            visible: !card.banner
            width: parent.width; height: visible ? 37 : 0
            Text { x: 12; y: 7; text: card.n && card.n.time ? Qt.formatTime(card.n.time, Qt.locale().timeFormat(Locale.ShortFormat).replace(/:ss/, "")) : ""
                   color: card.secondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            Glyph { x: parent.width - 32; y: 4; visible: hover.containsMouse || hovered; glyph: "window-close-symbolic"
                    Accessible.name: Strings.tr("Close"); onClicked: card.closeRequested() }
        }
        Row {
            x: card.banner ? 16 : 12; spacing: 12; width: parent.width - 2 * x
            Image { visible: !card.isImage && card.n && card.n.image !== ""; width: 48; height: 48; fillMode: Image.PreserveAspectFit
                    source: !card.isImage && card.n && card.n.image ? card.n.image : "" }
            Column {
                width: parent.width - (card.n && card.n.image && !card.isImage ? 60 : 0)
                Text { width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                       lineHeight: card.banner ? 18 : 19; lineHeightMode: Text.FixedHeight
                       text: card.n ? card.n.summary : ""; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                Text { width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight; visible: text !== ""
                       lineHeight: card.banner ? 18 : 19; lineHeightMode: Text.FixedHeight
                       text: card.n ? card.n.body : ""; color: card.secondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
            }
        }
        Row {
            visible: card.n && card.n.actions && card.n.actions.filter(a => a.key !== "default").length > 0
            x: card.banner ? 16 : 12; topPadding: 12; spacing: 8
            Repeater {
                model: card.n ? card.n.actions.filter(a => a.key !== "default") : []
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool accent: index === 0 && card.isImage
                    readonly property int count: card.n.actions.filter(a => a.key !== "default").length
                    width: card.isImage || count === 1 ? card.width - 32 : Math.max(96, (card.width - 32 - 8 * (count - 1)) / count)
                    height: 32; radius: Metrics.controlRadius
                    // First action on screenshots is the accent button.
                    color: accent ? (am.containsMouse ? Theme.accentHover : Theme.accentFill)
                                  : (am.pressed ? Theme.pressed : am.containsMouse ? Qt.tint(Metrics.col("notifications.button"), Theme.hover) : Metrics.col("notifications.button"))
                    border.color: accent ? "transparent" : Metrics.col("notifications.button.border")
                    Text { anchors.centerIn: parent; text: modelData.label
                           color: parent.accent ? Theme.accentOn : Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: am; anchors.fill: parent; hoverEnabled: true; onClicked: Notifications.invoke(card.n.notificationId, modelData.key) }
                }
            }
        }
        // Centre: "+ N notifications" (unfold the group).
        Item {
            visible: !card.banner && card.more > 0
            width: parent.width; height: visible ? 46 : 0
            Rectangle {
                // dark-100-15-notifications-2: 1589-1718 × 197-220, label 11 px from the left.
                x: 12; y: 22; width: moreLabel.implicitWidth + 20; height: Metrics.n("notifications.button.height", 24); radius: Metrics.controlRadius
                color: mm.pressed ? Theme.pressed : mm.containsMouse ? Qt.tint(Metrics.col("panel.control"), Theme.hover) : Metrics.col("panel.control")
                border.color: Metrics.col("notifications.button.border")
                Text { id: moreLabel; anchors.centerIn: parent; text: Strings.tr("+ %1 notifications").arg(card.more)
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                MouseArea { id: mm; anchors.fill: parent; hoverEnabled: true; onClicked: card.expandRequested() }
            }
        }
        Item { width: 1; height: card.banner ? 21 : 14 }
    }
}

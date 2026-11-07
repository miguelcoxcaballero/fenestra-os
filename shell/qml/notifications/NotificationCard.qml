// SPDX-License-Identifier: GPL-3.0-or-later
// One notification, laid out as a Windows 11 toast (positions in px from the card's outer edge).
// Banner (dark-100-17-toast; user-win11 160049 at 150 %, a Snipping Tool toast):
//   [hero picture: the full width, 2:1, cropped]
//   app line 50 px: 16 px icon at (16, 15), name (12 px) at x 40, "…" and close at the right;
//   title (14 px, 2 lines at most) and body (secondary, the toast's 4 lines minus the title's) at
//   x 16 (64 with an app-logo picture of 48 px at the left); an optional progress bar;
//   21 px, then the actions row (32 px buttons sharing the width, 16 px from the bottom) or the
//   end of the card.
// Centre item (dark-100-15-notifications-2): time line, title, body; close on hover; the group's
// "+ N notifications" button under the newest one.
// Banners are acrylic (Acrylic "base": Start's header and footer material on user-win11 160049),
// centre items overlays on the Notification Center's acrylic card.
import QtQuick
import QtQuick.Effects
import Fenestra.Shell

Item {
    id: card
    property var n            // {notificationId, appName, appIcon, summary, body, actions, image, time, value}
    property bool banner: false
    property int more: 0      // centre: other notifications of the same app, folded under this one
    // Inside the Notification Center's acrylic card: overlays on it.
    function c(key) { return banner ? Metrics.col(key) : Metrics.pcol(key) }
    signal closeRequested()
    signal expandRequested()
    property alias material: material
    width: parent ? parent.width : Metrics.toastWidth
    height: column.height
    readonly property int radius: banner ? Metrics.n("toast.radius", 7) : Metrics.controlRadius
    readonly property int pad: banner ? 16 : 12
    readonly property var buttons: n && n.actions ? n.actions.filter(a => a.key !== "default").slice(0, 5) : []
    readonly property string picture: n && n.image ? n.image : ""
    // The picture's role, by its shape: a wide one is the hero (screenshots, photos), a small or
    // square one the app-logo override at the left (avatars, album art).
    readonly property bool hero: picture !== "" && !picture.startsWith("image://icon") && probe.status === Image.Ready
                                 && probe.implicitWidth >= 160 && probe.implicitWidth >= 1.2 * probe.implicitHeight
    readonly property bool logo: picture !== "" && !hero && (probe.status === Image.Ready || picture.startsWith("image://icon"))
    readonly property color secondary: card.c("panel.text.secondary")
    readonly property int progress: n && n.value !== undefined && n.value >= 0 ? Math.min(100, n.value) : -1
    // Space under the text before the actions (or the end of a banner) and under an app logo.
    readonly property int after: banner || buttons.length > 0 ? 21 : 0
    readonly property int afterLogo: 16
    function iconUrl(icon) {
        if (!icon) return "image://icon/dialog-information"
        if (icon.startsWith("/")) return "file://" + icon
        if (icon.startsWith("file:") || icon.startsWith("image:")) return icon
        return "image://icon/" + icon
    }
    Image { id: probe; visible: false; source: card.picture; asynchronous: true }

    // ---- Material ---------------------------------------------------------------------------
    Acrylic {
        id: material
        visible: card.banner
        anchors.fill: parent
        recipe: "base"
        radius: card.radius
    }
    Rectangle {
        visible: !card.banner
        anchors.fill: parent
        radius: card.radius
        color: hover.containsMouse ? Qt.tint(card.c("notifications.card"), Theme.dark ? "#0affffff" : "#06000000") : card.c("notifications.card")
        border.color: card.c("notifications.card.border")
        border.width: 1
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
        // Hero: the card's full width at 2:1, cropped to fill, under the rounded top corners.
        Item {
            visible: card.hero
            width: parent.width; height: visible ? Math.round(width * Metrics.n("toast.hero.height", 180) / Metrics.toastWidth) : 0
            Image {
                id: heroImage
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                source: card.hero ? card.picture : ""
                asynchronous: true
                visible: false
            }
            MultiEffect {
                anchors.fill: heroImage
                source: heroImage
                maskEnabled: true
                maskSource: heroMask
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }
            Rectangle { id: heroMask; anchors.fill: parent; visible: false; layer.enabled: true; color: "black"
                        topLeftRadius: card.radius; topRightRadius: card.radius }
        }
        // Banner: app line (icon 16 at 16,15; name at 40; "…" (3 dots of 2 px, 2 apart, at 292) and
        // a 9 px close cross centred at (337, 23): dark-150-17-toast-case3).
        Item {
            visible: card.banner
            width: parent.width; height: visible ? 50 : 0
            Image { x: 16; y: 15; width: 16; height: 16; sourceSize: Qt.size(32, 32); source: card.iconUrl(card.n ? card.n.appIcon : "") }
            Text { x: 40; y: 14; width: parent.width - 40 - 88; elide: Text.ElideRight
                   text: card.n ? card.n.appName : ""; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            Glyph { x: parent.width - 79; y: 11; Accessible.name: Strings.tr("More options")
                    Row { x: 7; y: 11; spacing: 2; Repeater { model: 3; Rectangle { width: 2; height: 2; radius: 1; color: Metrics.col("toast.glyph") } } } }
            Glyph { x: parent.width - 39; y: 11; glyph: "window-close-symbolic"; glyphSize: 9; Accessible.name: Strings.tr("Close"); onClicked: card.closeRequested() }
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
        // Content: text (and the app-logo picture at the left, 60 px from 4 px above the title).
        Item {
            id: content
            x: card.pad; width: parent.width - 2 * card.pad
            readonly property real textBottom: texts.height
            // Windows: what follows starts 21 px under the text, or 16 under the logo (case6).
            height: card.logo ? Math.max(textBottom + card.after, 56 + card.afterLogo) : textBottom + card.after
            Image { visible: card.logo; x: 0; y: -4; width: 60; height: 60; fillMode: Image.PreserveAspectCrop
                    sourceSize: Qt.size(120, 120); source: card.logo ? card.picture : ""
                    layer.enabled: card.logo
                    layer.effect: MultiEffect { maskEnabled: true; maskSource: logoMask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 } }
            Rectangle { id: logoMask; width: 60; height: 60; radius: 30; visible: false; layer.enabled: true; color: "black" }
            Column {
                id: texts
                x: card.logo ? 76 : 0
                width: parent.width - x
                // Title: 2 lines at most; body: 4 (dark-150-17-toast-case3).
                Text { id: title; width: parent.width; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; maximumLineCount: 2
                       lineHeight: 18; lineHeightMode: Text.FixedHeight; visible: text !== ""
                       text: card.n ? card.n.summary : ""; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                Text { width: parent.width; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; elide: Text.ElideRight; visible: text !== ""
                       topPadding: title.visible ? 1 : 0
                       maximumLineCount: 4
                       lineHeight: 18; lineHeightMode: Text.FixedHeight
                       text: card.n ? card.n.body : ""; color: card.secondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                // Progress ("value" hint), Windows' toast progress bar (case4): 21 px under the text,
                // the 4 px bar (accent over a #494949 track, rounded) then the value at the right.
                Item {
                    visible: card.progress >= 0
                    width: parent.width; height: visible ? 21 + 9 + 4 + 7 + 18 : 0
                    Rectangle { y: 30; width: parent.width; height: 4; radius: 2; color: Metrics.col("toast.progress.track") }
                    Rectangle { y: 30; height: 4; radius: 2; color: Theme.accentFill; width: Math.max(height, parent.width * card.progress / 100) }
                    Text { anchors.right: parent.right; y: 41; height: 18; verticalAlignment: Text.AlignVCenter
                           text: card.progress + "%"
                           color: card.secondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                }
            }
        }
        // Actions: up to five sharing the width, 8 px apart; labels wrap to 2 lines (all buttons
        // then 51 px high) and are cut there (case3, case6).
        Row {
            id: actions
            visible: card.buttons.length > 0
            x: card.pad; spacing: 8
            readonly property int count: card.buttons.length
            readonly property real buttonWidth: Math.floor((card.width - 2 * card.pad - (count - 1) * spacing) / Math.max(1, count))
            property int lines: 1
            Repeater {
                id: buttonRepeater
                model: card.buttons
                delegate: Rectangle {
                    required property var modelData
                    width: actions.buttonWidth
                    height: actions.lines > 1 ? 51 : 32; radius: Metrics.controlRadius
                    color: am.pressed ? Theme.pressed : am.containsMouse ? Qt.tint(card.c("notifications.button"), Theme.hover) : card.c("notifications.button")
                    border.color: card.c("notifications.button.border")
                    clip: true
                    Text { id: buttonLabel; anchors.centerIn: parent; width: parent.width - 16; horizontalAlignment: Text.AlignHCenter
                           wrapMode: Text.WrapAtWordBoundaryOrAnywhere; maximumLineCount: 2; lineHeight: 18; lineHeightMode: Text.FixedHeight
                           text: modelData.label
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                           onLineCountChanged: actions.lines = Math.max(actions.lines, lineCount) }
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
                color: mm.pressed ? Theme.pressed : mm.containsMouse ? Qt.tint(card.c("panel.control"), Theme.hover) : card.c("panel.control")
                border.color: card.c("notifications.button.border")
                Text { id: moreLabel; anchors.centerIn: parent; text: Strings.tr("+ %1 notifications").arg(card.more)
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                MouseArea { id: mm; anchors.fill: parent; hoverEnabled: true; onClicked: card.expandRequested() }
            }
        }
        // 16 px under the actions row (user-win11 160049; the VM's case3-6); the text's 21 are in `content`.
        Item { width: 1; height: card.buttons.length > 0 ? 16 : card.banner ? 0 : 14 - card.after }
    }
    // The banner's edge: (79, 93, 89) over its fill (25, 41, 37) on user-win11 160049 = white 23.5 %
    // (Start's is 20.5 %).
    AcrylicOutline { acrylic: material; visible: card.banner
                     border.color: material.translucent ? Metrics.themed("toast.border") : material.borderColor }
}

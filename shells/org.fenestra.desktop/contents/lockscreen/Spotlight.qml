// SPDX-License-Identifier: GPL-3.0-or-later
// Windows Spotlight on the lock screen's clock view: "Learn more about this picture" at the top
// right (camera glyph E722 with the place; hovering shows the copyright) and the photo's hotspots
// (glyph E721) at a corner or at their point of the photo, each opening a card with Windows' text.
// Data: what Windows downloaded with the photo (Fenestra Shell reads ContentDeliveryManager's
// cache and writes it as "Spotlight" JSON). A click asks for the sign-in, as Windows does, and the
// link opens after unlocking (through the desktop portal, outside the lock screen's sandbox).
import QtQuick

Item {
    id: spot
    anchors.fill: parent
    readonly property var meta: { try { return JSON.parse(root.cfg("Spotlight", "{}")) } catch (e) { return {} } }
    readonly property bool has: meta.title !== undefined && meta.title !== ""
    visible: has
    signal open(string url)

    // ---- top right: the picture's info ----
    Item {
        id: info
        anchors { right: parent.right; top: parent.top; rightMargin: 24; topMargin: 24 }
        width: infoRow.width + 24; height: 40
        Rectangle { anchors.fill: parent; radius: 4; color: Qt.rgba(0, 0, 0, infoMouse.containsMouse ? 0.45 : 0.3) }
        Row {
            id: infoRow
            x: 12; anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            Glyph { anchors.verticalCenter: parent.verticalCenter; size: 16; glyph: ""; fallback: Qt.resolvedUrl("icons/camera.svg") }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.tr("Learn more about this picture", "Más información sobre esta imagen")
                color: "white"
                font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                renderType: Text.QtRendering
            }
        }
        MouseArea { id: infoMouse; anchors.fill: parent; hoverEnabled: true; onClicked: spot.open(spot.meta.url || "") }
    }
    Card {
        anchors { right: info.right; top: info.bottom; topMargin: 8 }
        shown: infoMouse.containsMouse
        title: spot.meta.title || ""
        body: spot.meta.copyright || ""
        url: spot.meta.url || ""
    }

    // ---- hotspots ----
    Repeater {
        model: spot.meta.hotspots || []
        Item {
            id: hs
            // "specific": the point of the photo (cover-cropped like the picture); "topLeft": the corner.
            readonly property bool corner: modelData.location !== "specific" || modelData.x === undefined
            readonly property real k: Math.max(root.width / 1920, root.height / 1080)
            x: corner ? 24 : (root.width - 1920 * k) / 2 + modelData.x * 1920 * k - width / 2
            y: corner ? 24 : (root.height - 1080 * k) / 2 + modelData.y * 1080 * k - height / 2
            width: 40; height: 40
            Rectangle { anchors.fill: parent; radius: width / 2; color: Qt.rgba(0, 0, 0, dot.containsMouse ? 0.5 : 0.3); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.4) }
            Glyph { anchors.centerIn: parent; size: 16; glyph: ""; fallback: Qt.resolvedUrl("icons/camera.svg") }
            MouseArea { id: dot; anchors.fill: parent; hoverEnabled: true; onClicked: spot.open(modelData.url || "") }
            Card {
                x: hs.corner ? 0 : Math.min(0, root.width - hs.x - width - 24)
                anchors.top: parent.bottom; anchors.topMargin: 8
                shown: dot.containsMouse
                title: modelData.title || ""
                body: modelData.action || ""
                url: modelData.url || ""
                bodyIsLink: true
            }
        }
    }

    component Card: Rectangle {
        id: c
        property bool shown: false
        property string title
        property string body
        property string url
        property bool bodyIsLink: false
        visible: shown
        width: 320; height: col.height + 24
        radius: 8
        color: Qt.rgba(0.17, 0.17, 0.17, 0.96)
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.08)
        Column {
            id: col
            x: 12; y: 12; width: parent.width - 24
            spacing: 6
            Text { width: parent.width; wrapMode: Text.Wrap; text: c.title; color: "white"
                   font.family: Fluent.text; font.pixelSize: 14; font.weight: Font.DemiBold; font.variableAxes: ({ "opsz": Fluent.opsz(14) }) }
            Text { width: parent.width; wrapMode: Text.Wrap; text: c.body; visible: text !== ""
                   color: c.bodyIsLink ? root.lightAccent : Qt.rgba(1, 1, 1, 0.786)
                   font.family: Fluent.text; font.pixelSize: 12; font.variableAxes: ({ "opsz": Fluent.opsz(12) }) }
        }
    }
}

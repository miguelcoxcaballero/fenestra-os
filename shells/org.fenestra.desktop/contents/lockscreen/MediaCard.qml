// SPDX-License-Identifier: GPL-3.0-or-later
// Media on the lock screen (Windows 11 shows the playing app's controls at the bottom centre):
// album art, title and artist, previous / play-pause / next, on an acrylic card.
import QtQuick
import org.kde.plasma.private.mpris as Mpris

Item {
    id: card
    width: 360; height: players.count > 0 ? 88 : 0
    visible: players.count > 0
    Repeater {
        id: players
        model: Mpris.MultiplexerModel { }
        Item {
            required property var model
            anchors.fill: parent
            Rectangle { anchors.fill: parent; radius: 8; color: Qt.rgba(0, 0, 0, 0.42); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.12) }
            Image {
                id: art
                x: 12; anchors.verticalCenter: parent.verticalCenter
                width: 64; height: 64
                source: model.artUrl || ""
                visible: status === Image.Ready
                fillMode: Image.PreserveAspectCrop
                sourceSize: Qt.size(64 * Screen.devicePixelRatio, 64 * Screen.devicePixelRatio)
            }
            Column {
                x: art.visible ? 88 : 16; y: 16
                width: parent.width - x - 16
                Text { width: parent.width; elide: Text.ElideRight; text: model.track || model.identity; color: "white"
                       font.family: Fluent.text; font.pixelSize: 14; font.weight: Font.DemiBold; font.variableAxes: ({ "opsz": Fluent.opsz(14) }) }
                Text { width: parent.width; elide: Text.ElideRight; text: model.artist || ""; color: Qt.rgba(1, 1, 1, 0.786)
                       font.family: Fluent.text; font.pixelSize: 12; font.variableAxes: ({ "opsz": Fluent.opsz(12) }) }
            }
            Row {
                anchors { right: parent.right; rightMargin: 8; bottom: parent.bottom; bottomMargin: 6 }
                CornerButton { width: 36; height: 32; glyph: "\uE892"; enabled: model.canGoPrevious; opacity: enabled ? 1 : 0.4; onClicked: model.container.Previous() }
                CornerButton { width: 36; height: 32; glyph: model.playbackStatus === Mpris.PlaybackStatus.Playing ? "\uE769" : "\uE768"; onClicked: model.container.PlayPause() }
                CornerButton { width: 36; height: 32; glyph: "\uE893"; enabled: model.canGoNext; opacity: enabled ? 1 : 0.4; onClicked: model.container.Next() }
            }
        }
    }
}

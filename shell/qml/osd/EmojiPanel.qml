// SPDX-License-Identifier: GPL-3.0-or-later
// The emoji panel (Win+. or Win+;), after Windows 11's: a search line, the categories, a grid of
// emoji with the recently used first. Typing filters; a click, or Enter on the first match, closes
// the panel and types the emoji where the text cursor was (Emoji.type). Windows opens it at the
// text cursor; a Wayland shell can't know where that is, so it opens over the middle of the taskbar.
// Sizes follow the shell's flyouts (40 px cells): Windows' own panel hasn't been measured.
import QtQuick
import Fenestra.Shell

Flyout {
    id: panel
    recipe: "panel"
    padding: 0
    anchorX: targetScreen ? targetScreen.width / 2 : 0
    property int group: -1            // -1 = recently used
    property string pending: ""
    readonly property var glyphs: ["\u{1F600}", "\u{1F9D1}", "\u{1F43B}", "\u{1F354}", "\u{1F697}", "\u{26BD}", "\u{1F4A1}", "\u{1F523}", "\u{1F6A9}"]
    readonly property var shown_: {
        if (search.text.trim() !== "") return Emoji.items(0, search.text)
        return group < 0 ? Emoji.recent : Emoji.items(group)
    }
    function present() {
        pending = ""
        search.text = ""
        group = Emoji.recent.length > 0 ? -1 : 0
        open()
        search.input.forceActiveFocus()
    }
    function pick(e) {
        pending = e
        close()
    }
    onDismissed: if (pending !== "") { Emoji.type(pending); pending = "" }

    Item {
        width: 352; height: 388
        SearchBox {
            id: search
            x: 12; y: 12; width: parent.width - 24
            editable: true
            placeholder: Strings.tr("Search emoji")
            onAccepted: if (grid.count > 0) panel.pick(panel.shown_[0].e)
            onEscapePressed: panel.close()
            onDownPressed: grid.forceActiveFocus()
        }
        Row {
            id: tabs
            x: 12; y: 54; height: 36
            Repeater {
                model: [-1].concat(Emoji.groups.map((_, i) => i))
                delegate: Rectangle {
                    required property int modelData
                    readonly property bool current: search.text.trim() === "" && panel.group === modelData
                    width: 32.8; height: 36; radius: Metrics.controlRadius
                    color: tabMouse.pressed ? Theme.pressed : tabMouse.containsMouse ? Theme.hover : "transparent"
                    FluentGlyph {
                        visible: parent.modelData < 0
                        anchors.centerIn: parent
                        glyph: "\ue81c"; fallback: "document-open-recent-symbolic"; size: 16
                    }
                    Text {
                        visible: parent.modelData >= 0
                        anchors.centerIn: parent
                        text: parent.modelData >= 0 ? panel.glyphs[parent.modelData] : ""
                        font.family: "Segoe UI Emoji"; font.pixelSize: 16
                    }
                    Rectangle {
                        visible: parent.current
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 2 }
                        width: 16; height: 3; radius: 1.5
                        color: Theme.accentFill
                    }
                    MouseArea { id: tabMouse; anchors.fill: parent; hoverEnabled: true
                                onClicked: { search.text = ""; panel.group = parent.modelData; grid.positionViewAtBeginning() } }
                }
            }
        }
        Rectangle { x: 0; y: 94; width: parent.width; height: 1; color: Metrics.pcol("panel.divider") }
        Text {
            x: 16; y: 104
            text: search.text.trim() !== "" ? Strings.tr("Results") : panel.group < 0 ? Strings.tr("Recently used") : Strings.emojiGroup(Emoji.groups[panel.group])
            color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
        }
        GridView {
            id: grid
            x: 12; y: 128; width: 328; height: parent.height - y - 8
            cellWidth: 41; cellHeight: 40
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: panel.shown_
            keyNavigationEnabled: true
            highlightFollowsCurrentItem: true
            Keys.onReturnPressed: if (currentIndex >= 0 && currentIndex < count) panel.pick(panel.shown_[currentIndex].e)
            Keys.onEscapePressed: panel.close()
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: 40; height: 40; radius: Metrics.controlRadius
                color: cellMouse.pressed ? Theme.pressed : cellMouse.containsMouse || (grid.activeFocus && grid.currentIndex === index) ? Theme.hover : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: parent.modelData.e
                    font.family: "Segoe UI Emoji"; font.pixelSize: 24
                }
                MouseArea { id: cellMouse; anchors.fill: parent; hoverEnabled: true; onClicked: panel.pick(parent.modelData.e) }
            }
            WheelHandler {
                onWheel: (e) => { grid.contentY = Math.max(0, Math.min(Math.max(0, grid.contentHeight - grid.height), grid.contentY - e.angleDelta.y / 120 * 3 * 40)) }
            }
        }
        Text {
            visible: grid.count === 0
            anchors.horizontalCenter: parent.horizontalCenter; y: 200
            text: search.text.trim() !== "" ? Strings.tr("No emoji found") : Strings.tr("The emoji you use will appear here")
            color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
        }
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// B05: condition icon, temperature and condition; opens the Widgets board (WidgetsBoard.qml):
// on hover after a delay, at once on click, as Windows 11 24H2 does.
import QtQuick
import Fenestra.Shell

Item {
    id: weather
    property var targetScreen
    readonly property bool available: Weather.available
    width: row.implicitWidth + 20; height: 40
    Accessible.role: Accessible.Button
    Accessible.name: Weather.temperature + " " + Weather.condition
    Rectangle { anchors.fill: parent; radius: Metrics.controlRadius; color: mouse.containsMouse ? Theme.hover : "transparent" }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 8
        Image {
            width: 28; height: 28
            anchors.verticalCenter: parent.verticalCenter
            sourceSize: Qt.size(28 * Screen.devicePixelRatio, 28 * Screen.devicePixelRatio)
            // Coloured icons are drawn for dark surfaces; light mode uses the symbolic ones.
            source: "image://icon/" + (Theme.dark && Weather.iconName ? Weather.iconName : Weather.symbolicIconName)
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: Weather.temperature; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold }
            Text { text: Weather.condition; visible: text !== ""; color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: {
            openTimer.stop(); closeTimer.stop()
            if (board.shown && board.pinned) board.close()
            else board.open(true)
        }
        onContainsMouseChanged: {
            if (containsMouse) {
                closeTimer.stop()
                if (!board.shown && ShellSettings.widgetsOnHover) openTimer.restart()
            } else {
                openTimer.stop()
                if (board.shown && !board.pinned) closeTimer.restart()
            }
        }
    }
    // Windows (VM, QMP-timed): the board starts sliding in ~600 ms after the pointer rests on the
    // weather; hover-opened, it closes ~850 ms after the pointer leaves the weather without entering
    // the board, ~270 ms after it leaves the board.
    Timer { id: openTimer; interval: Tokens.v("widgets.hover.delay", 600); onTriggered: if (mouse.containsMouse) board.open(false) }
    Timer {
        id: closeTimer
        interval: board.entered ? Tokens.v("widgets.leave.board", 270) : Tokens.v("widgets.leave.button", 850)
        onTriggered: if (!board.pinned && !board.hovered && !mouse.containsMouse) board.close()
    }
    Connections {
        target: board
        function onHoveredChanged() {
            if (board.hovered) closeTimer.stop()
            else if (board.shown && !board.pinned && !mouse.containsMouse) closeTimer.restart()
        }
    }
    WidgetsBoard { id: board; targetScreen: weather.targetScreen }
    function testOpenBoard(byClick) { board.open(byClick) }
    function testBoard() { return board }
}

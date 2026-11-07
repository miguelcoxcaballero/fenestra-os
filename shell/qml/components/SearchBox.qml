// SPDX-License-Identifier: GPL-3.0-or-later
// The search field of Start and Search (user-win11 160039 / 160049 / 160127 at 150 %): a 32 px
// pill, 16 px search icon at 16 px, text (14 px) from 45 px with its baseline 20 px down, the
// caret 44 px in. Fill: #1E1E1E at 70 % over the panel; border: white 6.6 %, 2 device px.
// Start's box is not editable (typing opens Search): it only shows a blinking caret.
import QtQuick
import Fenestra.Shell

Rectangle {
    id: box
    property string placeholder
    property bool caretVisible: false
    // Search: a real text field.
    property bool editable: false
    property alias input: entry
    property alias text: entry.text
    signal upPressed()
    signal downPressed()
    signal accepted()
    signal escapePressed()
    readonly property real dpr: Window.window ? ShellUtil.scaleOf(Window.window) : 1
    height: Metrics.tok("search.field.height", 32)
    radius: height / 2
    color: Metrics.themed("search.field.fill" + (ShellSettings.transparency ? "" : ".solid"))
    border.width: (dpr > 1 && dpr < 2 ? 2 : Math.max(1, Math.round(dpr))) / dpr
    border.color: Metrics.themed("search.field.border")
    readonly property real textX: Metrics.num("search.field.text.x", 45.33)
    readonly property real textBaseline: Metrics.num("search.field.baseline", 20)

    Image {
        x: Metrics.num("search.field.icon.x", 16); y: Metrics.num("search.field.icon.y", 8)
        width: 16; height: 16
        sourceSize: Qt.size(32, 32)
        source: ShellSettings.searchIcon !== "" ? ShellSettings.searchIcon : Metrics.assets + "search/search.svg"
    }
    Text {
        x: box.textX; y: box.textBaseline - baselineOffset
        visible: entry.text === ""
        text: box.placeholder
        color: Metrics.themed("search.field.placeholder")
        font.family: Metrics.fontFamily; font.variableAxes: Metrics.textAxes; font.pixelSize: Metrics.fontBody
    }
    TextInput {
        id: entry
        x: box.textX; y: box.textBaseline - baselineOffset
        width: parent.width - x - 16
        visible: box.editable
        enabled: box.editable
        color: Theme.text
        selectionColor: Theme.accentFill; selectedTextColor: Theme.accentOn
        font.family: Metrics.fontFamily; font.variableAxes: Metrics.textAxes; font.pixelSize: Metrics.fontBody
        clip: true
        Keys.onUpPressed: box.upPressed()
        Keys.onDownPressed: box.downPressed()
        Keys.onReturnPressed: box.accepted()
        Keys.onEnterPressed: box.accepted()
        Keys.onEscapePressed: box.escapePressed()
        cursorDelegate: Rectangle {
            width: 2 / box.dpr * (box.dpr < 2 ? 1 : 1); height: Metrics.num("search.field.caret.height", 18.67)
            y: (entry.height - height) / 2
            color: Metrics.themed("search.field.caret")
            visible: entry.cursorVisible && blinkOn
            property bool blinkOn: true
            Timer { interval: 530; repeat: true; running: entry.activeFocus && !Motion.reduced; onTriggered: parent.blinkOn = !parent.blinkOn }
        }
    }
    // Start: the caret of the focused box (it is not editable there).
    Rectangle {
        x: Metrics.num("search.field.caret.x", 44); y: Metrics.num("search.field.caret.y", 6.67)
        width: 2 / box.dpr; height: Metrics.num("search.field.caret.height", 18.67)
        color: Metrics.themed("search.field.caret")
        visible: !box.editable && box.caretVisible && blink.on
        Timer { id: blink; property bool on: true; interval: 530; repeat: true
                running: !box.editable && box.caretVisible && !Motion.reduced
                onRunningChanged: on = true; onTriggered: on = !on }
    }
}

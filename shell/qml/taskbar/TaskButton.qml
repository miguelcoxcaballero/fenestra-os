// SPDX-License-Identifier: GPL-3.0-or-later
// One taskbar button: pinned launcher and/or a group of windows of one app (B02, B04).
import QtQuick
import Fenestra.Shell

Item {
    id: button
    property url iconSource
    property string iconName
    // Bumped when apps are installed or removed: the icon is asked for again (QML keeps what it got).
    property int iconStamp: 0
    Connections { target: Apps; function onDatabaseChanged() { button.iconStamp += 1 } }
    property string label
    property int windowCount: 0
    // The group's windows ({uuid, title, row, width, height, ...}: TaskbarModel's "windows").
    property var windowList: []
    property bool focused: false
    property bool attention: false
    // Start / Search while their flyout is open.
    property bool checked: false
    // Extra width after the 44 px cell (Start) and a vertical nudge of the icon.
    property real trailing: 0
    property real iconDy: 0
    // Start's plate is wider than the others' (user-win11 160039: 62 device px, its ring at cell + 2).
    property real plateGrow: 0
    readonly property bool hovered: mouse.containsMouse
    signal clicked()
    signal rightClicked()
    signal middleClicked()

    // A 44 px cell (taskbar.button.pitch) with the 40 px plate centred in it (taskbar.button).
    width: Metrics.taskPitch + trailing; height: Metrics.taskbarHeight
    Accessible.role: Accessible.Button
    Accessible.name: label

    // One device pixel (geometry below is snapped to the output's pixels, as Windows lays it out).
    // The window's real scale (Taskbar.dpr: Screen.devicePixelRatio is the screen's integer one, 2 at 150 %).
    property real dpr: 1
    readonly property real px: 1 / dpr
    // n whole device pixels as a logical size, a hair under: Qt Quick's software renderer fills a
    // rectangle ending at 2.0000000001 device px over 3 rows.
    function dev(n) { return (n - 0.001) / dpr }
    // The plate (user-win11 163657 / 160039 / 160049 at 150 %): 40 x 39.33 (60 x 59 device px) from
    // y = 4, radius 4. Its fill is white over the acrylic: 6 % hovered or lit (#0F), 8 % hovered and lit
    // (#15); lit buttons (focused window, Start / Search open) also have a 1 px ring at 8 %; the top
    // 2 device px are 4.7 % lighter still (Windows' elevation highlight, also over the ring).
    Rectangle {
        id: plate
        x: (Metrics.taskPitch - width) / 2
        y: Metrics.tok("taskbar.plate.y", 4)
        width: Metrics.taskButton + button.plateGrow; height: button.dev(Math.round(Metrics.taskButton * button.dpr) - 1)
        radius: Metrics.controlRadius
        readonly property bool lit: button.focused || button.checked
        readonly property bool hot: mouse.containsMouse
        // A window asking for attention: red plate without border (dark-100-24-caption-buttons:
        // Explorer flashing), until it is focused.
        // As Windows: the button flashes ForegroundFlashCount times (7, the user's registry value, at the
        // caret blink rate, 530 ms) and then stays lit until the window is activated.
        readonly property bool asking: button.attention && !button.focused
        property int flashes: 0
        readonly property bool alert: asking && (flashes >= 14 || flashes % 2 === 0)
        onAskingChanged: { flashes = 0; if (asking) flashTimer.restart(); else flashTimer.stop() }
        Timer { id: flashTimer; interval: 530; repeat: true
                onTriggered: { plate.flashes++; if (plate.flashes >= 14) stop() } }
        // Shown as a whole (opacity) so that it fades in and out without passing through black.
        opacity: lit || hot || alert ? 1 : 0
        color: alert ? Metrics.themed("taskbar.plate.attention")
               : mouse.pressed ? Metrics.themed("taskbar.plate.pressed")
               : hot && lit ? Metrics.themed("taskbar.plate.hover.lit")
               : Metrics.themed("taskbar.plate")
        border.width: lit && !alert ? Math.ceil(button.dpr) * button.px : 0
        border.color: Metrics.themed("taskbar.plate.border")
        // Elevation highlight: the plate's top 2 device px (1 px at 100 %), following its corners.
        Item {
            visible: !plate.alert
            width: parent.width; height: button.dev(Math.ceil(button.dpr))
            clip: true
            Rectangle { width: plate.width; height: plate.height; radius: plate.radius; color: Metrics.themed("taskbar.plate.highlight") }
        }
        // Windows fades the plate in ~90 ms on hover and to the pressed fill in ~100 ms (motion.json,
        // observations_close_2026_11_07); the reference caught Notepad's plate half way from the
        // attention red to the hover grey (dark-100-02-taskbar-hover).
        Behavior on opacity { enabled: !Motion.reduced; NumberAnimation { duration: 90 } }
        Behavior on color { enabled: !Motion.reduced; ColorAnimation { duration: 90 } }
    }
    Image {
        x: (Metrics.taskPitch - width) / 2; y: (parent.height - height) / 2 + button.iconDy
        width: Metrics.taskIcon; height: Metrics.taskIcon
        sourceSize: Qt.size(Metrics.taskIcon * Screen.devicePixelRatio, Metrics.taskIcon * Screen.devicePixelRatio)
        source: button.iconSource.toString() !== "" ? button.iconSource
                : (button.iconName !== "" ? "image://icon/" + button.iconName + (button.iconStamp > 0 ? "?" + button.iconStamp : "") : "")
        // Press animation (pressAnimation.js): the icon shrinks while pressed.
        scale: mouse.pressed ? 0.82 : 1
        // ~150 ms to shrink on the reference recording (motion.json).
        Behavior on scale { enabled: !Motion.reduced; NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
    }
    // Running indicator (163657 at 150 %): unfocused 6 x 3 (9 x 4 device px: Windows rounds the height
    // to whole pixels), white at 55 % (#8B) over the acrylic, its top 40 below the bar's top edge;
    // focused 16 wide in the accent colour.
    Rectangle {
        visible: button.windowCount > 0
        // Centred on the cell and rounded up to a whole device pixel (Brave's dash at 1437, not 1436.5).
        x: Math.ceil((Metrics.taskPitch - width) / 2 * button.dpr) * button.px
        height: button.dev(Math.floor(Metrics.indicatorHeight * button.dpr))
        y: Metrics.tok("taskbar.indicator.y", 40)
        radius: height / 2
        // Attention: 32 px in the critical colour (dark-100-24-caption-buttons, light-100-24).
        width: plate.alert ? Metrics.tok("taskbar.indicator.attention", 32) : button.focused ? Metrics.indicatorFocused : Metrics.indicatorUnfocused
        color: plate.alert ? Metrics.themed("taskbar.indicator.attention") : button.focused ? Theme.accentFill : Metrics.themed("taskbar.indicator")
        Behavior on width { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        onClicked: (m) => {
            if (m.button === Qt.RightButton) button.rightClicked()
            else if (m.button === Qt.MiddleButton) button.middleClicked()
            else button.clicked()
        }
    }
}

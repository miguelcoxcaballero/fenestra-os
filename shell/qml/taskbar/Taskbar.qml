// SPDX-License-Identifier: GPL-3.0-or-later
// Values from the GNOME layer (dash-to-panel in desktop/dconf/local.d/00-fenestra):
// 48 px, background #000402 at 63 %, 1 px top border rgba(255,255,255,0.10), icons centred.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: bar
    required property var targetScreen
    readonly property int barHeight: 48

    screen: targetScreen
    height: barHeight
    color: "transparent"
    visible: true
    LayerShell.Window.scope: "fenestra-taskbar"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft
                               | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: barHeight   // maximized windows stop above the taskbar
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 4 / 255, 2 / 255, 0.63)
        Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.10) }
    }

    Row {
        id: tasks
        anchors.centerIn: parent
        height: parent.height
        spacing: 4

        TaskButton {
            id: start
            iconSource: "file:///usr/share/fenestra/assets/branding/start-button.svg"
            label: qsTr("Start")
        }
        Repeater {
            model: WindowsModel
            delegate: TaskButton {
                required property int index
                required property var model
                iconName: model.iconName || model.appId
                label: model.title
                running: true
                focused: model.active && !model.minimized
                onClicked: WindowsModel.activateOrMinimize(index)
            }
        }
    }

    Text {
        id: clock
        anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
        color: "white"
        horizontalAlignment: Text.AlignRight
        font.pixelSize: 12
        lineHeight: 1.15
        property date now: new Date()
        text: Qt.formatTime(now, Locale.ShortFormat) + "\n" + Qt.formatDate(now, Locale.ShortFormat)
        Timer {
            // Wake once a minute, on the minute (no polling between).
            interval: 60000 - (new Date().getSeconds() * 1000)
            running: true; repeat: true
            onTriggered: { clock.now = new Date(); interval = 60000 - clock.now.getSeconds() * 1000 }
        }
    }

    // "Show desktop" corner (B09).
    MouseArea {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: 8
        onClicked: WindowsModel.toggleShowDesktop()
    }
}

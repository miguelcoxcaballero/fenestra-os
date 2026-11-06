// SPDX-License-Identifier: GPL-3.0-or-later
// Right end of the taskbar (B08): overflow ^ (app tray icons), keyboard layout, the quick group
// (network, volume, battery; opens quick settings in H4) and the clock. Spacing from trayLayout.js.
import QtQuick
import Fenestra.Shell

Row {
    id: tray
    property var targetScreen
    signal quickSettingsRequested(real anchorX)
    signal calendarRequested(real anchorX)
    spacing: 0

    TrayButton {
        id: overflowButton
        anchors.verticalCenter: parent.verticalCenter
        hpad: 10
        visible: TrayItems.count > 0
        accessibleName: Strings.tr("Show hidden icons")
        SymbolicIcon { name: "pan-up-symbolic"; size: 12 }
        onClicked: { overflow.anchorX = overflowButton.mapToItem(null, overflowButton.width / 2, 0).x; overflow.toggle() }
    }
    // Privacy (B08): microphone and location in use, with the app names as tooltip.
    Row {
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8; rightPadding: 6; leftPadding: 4
        visible: Privacy.microphoneApps.length > 0 || Privacy.locationInUse
        SymbolicIcon { visible: Privacy.microphoneApps.length > 0; src: Metrics.assets + "privacy/mic.svg"
            Accessible.name: Privacy.microphoneApps.length === 1 ? Privacy.microphoneApps[0] + " " + Strings.tr("is using your microphone")
                             : Privacy.microphoneApps.length + " " + Strings.tr("apps are using your microphone") }
        SymbolicIcon { visible: Privacy.locationInUse; src: Metrics.assets + "privacy/location.svg"
            Accessible.name: Strings.tr("Your location is being used") }
    }
    TrayButton {
        anchors.verticalCenter: parent.verticalCenter
        visible: KeyboardStatus.count > 1
        accessibleName: KeyboardStatus.longName
        Text { text: KeyboardStatus.shortName; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
        onClicked: KeyboardStatus.next()
    }
    TrayButton {
        id: quick
        anchors.verticalCenter: parent.verticalCenter
        hpad: 3 + 4
        accessibleName: [NetworkStatus.name, AudioStatus.volume + " %", PowerStatus.hasBattery ? PowerStatus.percentage + " %" : ""].join(" ")
        SymbolicIcon { name: NetworkStatus.iconName }
        SymbolicIcon { name: AudioStatus.iconName }
        SymbolicIcon { src: PowerStatus.iconSource }
        onClicked: tray.quickSettingsRequested(quick.mapToItem(null, quick.width / 2, 0).x)
        onWheel: (delta) => { if (AudioStatus.available) AudioStatus.volume = Math.max(0, Math.min(100, AudioStatus.volume + (delta > 0 ? 2 : -2))) }
    }
    Clock {
        id: clock
        anchors.verticalCenter: parent.verticalCenter
        onClicked: tray.calendarRequested(clock.mapToItem(null, clock.width / 2, 0).x)
    }

    // Overflow flyout: the apps' StatusNotifierItems in a grid of 40 px cells.
    Flyout {
        id: overflow
        targetScreen: tray.targetScreen
        Grid {
            columns: Math.min(5, Math.max(1, TrayItems.count))
            spacing: 0
            Repeater {
                model: TrayItems
                delegate: Item {
                    id: cell
                    required property int index
                    required property var model
                    width: 40; height: 40
                    Rectangle { anchors.fill: parent; radius: Metrics.controlRadius; color: m.containsMouse ? Theme.hover : "transparent" }
                    Image {
                        anchors.centerIn: parent
                        width: 16; height: 16
                        sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
                        source: cell.model.iconUrl
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: cell.model.toolTip
                    MouseArea {
                        id: m
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                        onClicked: (e) => {
                            const p = cell.mapToGlobal(width / 2, height / 2)
                            if (e.button === Qt.MiddleButton) TrayItems.secondaryActivate(cell.index, p.x, p.y)
                            else if (e.button === Qt.RightButton) {
                                if (cell.model.hasMenu) { itemMenu.row = cell.index; itemMenu.anchorX = cell.mapToItem(null, width / 2, 0).x; TrayItems.requestMenu(cell.index) }
                                else TrayItems.contextMenu(cell.index, p.x, p.y)
                            } else TrayItems.activate(cell.index, p.x, p.y)
                        }
                        onWheel: (w) => TrayItems.scroll(cell.index, w.angleDelta.y)
                    }
                }
            }
        }
    }
    ContextMenu {
        id: itemMenu
        property int row: -1
        targetScreen: tray.targetScreen
    }
    Connections {
        target: TrayItems
        function onMenuReady(row, entries) {
            if (row !== itemMenu.row) return
            itemMenu.items = entries.map(e => e.separator ? "-" : ({
                text: (e.depth > 0 ? "    " : "") + e.text + (e.checked ? "  ✓" : ""),
                icon: e.icon, action: () => TrayItems.triggerMenuItem(row, e.id) }))
            itemMenu.open()
        }
    }

    function testCloseFlyouts() { overflow.close(); itemMenu.close() }
    function testMenu(row) { itemMenu.row = row; itemMenu.anchorX = overflowButton.mapToItem(null, 0, 0).x; TrayItems.requestMenu(row) }
    function testOverflow() { overflow.anchorX = overflowButton.mapToItem(null, overflowButton.width / 2, 0).x; overflow.open() }
}

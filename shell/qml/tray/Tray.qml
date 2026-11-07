// SPDX-License-Identifier: GPL-3.0-or-later
// Right end of the taskbar (B08): overflow ^ (app tray icons), keyboard layout, the quick group
// (network, volume, battery; opens quick settings in H4) and the clock.
// Glyph positions measured on user-win11 163657 at 150 % (device px, screen 2880 wide): chevron
// 2509-2524 x 1759-1767, "ENG"/"ES" centred on 2574.5, wifi 2619-2642, volume 2661-2684, battery
// 2703-2732 x 1752-1771, clock text right edge 2850 (Clock.qml). The cells' paddings below put the
// glyphs there (logical px); the hover plates themselves are not in any capture.
import QtQuick
import Fenestra.Shell

Row {
    id: tray
    property var targetScreen
    signal quickSettingsRequested(real anchorX)
    signal calendarRequested(real anchorX)
    // Tests (tests/shell-kwin): {network, audio, battery} drawn instead of the live status (the bench
    // has no NetworkManager, sound server or battery).
    property var testStatus: null
    spacing: 0

    TrayButton {
        id: overflowButton
        anchors.verticalCenter: parent.verticalCenter
        lpad: Tokens.v("tray.overflow.lpad", 7.67)
        rpad: Tokens.v("tray.overflow.rpad", 5.67)
        visible: TrayItems.count > 0
        accessibleName: Strings.tr("Show hidden icons")
        // 16 x 9 device px at 150 %: the 0.75-wide chevron of a 14 px box.
        SymbolicIcon { name: "pan-up-symbolic"; size: Metrics.tok("tray.overflow.icon", 14) }
        onClicked: { overflow.anchorX = overflowButton.mapToItem(null, overflowButton.width / 2, 0).x; overflow.toggle() }
    }
    // Privacy (B08): microphone and location in use, with the app names as tooltip.
    Row {
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8; rightPadding: 6; leftPadding: 4
        visible: Privacy.microphoneApps.length > 0 || Privacy.locationInUse || CameraWatch.inUse
        SymbolicIcon { visible: Privacy.microphoneApps.length > 0; src: Metrics.assets + "privacy/mic.svg"
            Accessible.name: Privacy.microphoneApps.length === 1 ? Privacy.microphoneApps[0] + " " + Strings.tr("is using your microphone")
                             : Privacy.microphoneApps.length + " " + Strings.tr("apps are using your microphone") }
        SymbolicIcon { visible: CameraWatch.inUse; src: Metrics.assets + "privacy/camera.svg"
            Accessible.name: Strings.tr("Your camera is being used") }
        SymbolicIcon { visible: Privacy.locationInUse; src: Metrics.assets + "privacy/location.svg"
            Accessible.name: Strings.tr("Your location is being used") }
    }
    // Input indicator, shown with more than one keyboard layout: "ENG" over "ES" as Windows draws it
    // (user-win11 163657: both lines centred, in the clock's font and line positions).
    TrayButton {
        anchors.verticalCenter: parent.verticalCenter
        visible: KeyboardStatus.count > 1
        lpad: Tokens.v("tray.input.lpad", 12)
        rpad: Tokens.v("tray.input.rpad", 13.33)
        accessibleName: KeyboardStatus.longName
        Item {
            width: lang.textWidth; height: 40
            // Drawn like the clock (Clock.qml), centred.
            ShadowLabel {
                id: lang
                anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: parent.verticalCenter }
                width: 80
                pad: 0
                maxLines: 2
                shadowStrength: 0
                gamma: Tokens.v("clock.gamma", 1)
                color: Theme.text
                lineHeight: Metrics.tok("clock.line", 16)
                font.family: Metrics.fontFamily
                font.pixelSize: 12
                font.variableAxes: ({ "opsz": Tokens.v("clock.font.opsz", 8) })
                font.hintingPreference: Font.PreferFullHinting
                text: KeyboardStatus.language + "\n" + KeyboardStatus.region
            }
        }
        onClicked: KeyboardStatus.next()
    }
    TrayButton {
        id: quick
        anchors.verticalCenter: parent.verticalCenter
        lpad: Metrics.tok("tray.quick.lpad", 6)
        rpad: Tokens.v("tray.quick.rpad", 8.67)
        spacing: Metrics.tok("tray.quick.spacing", 12)   // wifi, volume, battery boxes 28 px apart
        accessibleName: [NetworkStatus.name, AudioStatus.volume + " %", PowerStatus.hasBattery ? PowerStatus.percentage + " %" : ""].join(" ")
        SymbolicIcon { anchors.verticalCenter: parent.verticalCenter; name: tray.testStatus ? tray.testStatus.network : NetworkStatus.iconName }
        // Volume: Windows draws the waves the level does not reach dimmed (the full glyph under the level's).
        Item {
            anchors.verticalCenter: parent.verticalCenter
            width: volume.width; height: volume.height
            visible: level !== ""
            readonly property string level: tray.testStatus ? tray.testStatus.audio : AudioStatus.iconName
            SymbolicIcon {
                visible: parent.level.indexOf("-low-") >= 0 || parent.level.indexOf("-medium-") >= 0
                name: "audio-volume-high-symbolic"
                opacity: Tokens.v("tray.volume.ghost", 0.2)
            }
            SymbolicIcon { id: volume; name: parent.level }
        }
        // Battery: 30 x 20 device px at 150 % (a 20 px box), 2 device px above the row's centre.
        SymbolicIcon {
            anchors.verticalCenter: parent.verticalCenter
            src: tray.testStatus ? tray.testStatus.battery : PowerStatus.iconSource
            size: Metrics.tok("tray.battery.size", 20)
            transform: Translate { y: -Tokens.v("tray.battery.dy", 1.33) }
        }
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
        motion: "taskbar"
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
    function testSetTime(ms) { clock.now = new Date(ms) }
    function testMenu(row) { itemMenu.row = row; itemMenu.anchorX = overflowButton.mapToItem(null, 0, 0).x; TrayItems.requestMenu(row) }
    function testOverflow() { overflow.anchorX = overflowButton.mapToItem(null, overflowButton.width / 2, 0).x; overflow.open() }
}

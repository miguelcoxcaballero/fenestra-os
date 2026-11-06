// SPDX-License-Identifier: GPL-3.0-or-later
// Ctrl+Alt+Del (Q05, securityScreen.js): black full-screen overlay with Lock, Switch user, Sign out,
// Change a password, Task Manager and Cancel; Network, Accessibility and Power in the corner.
// Geometry relative to the screen centre (from a 1920 × 1080 reference); always dark.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: sec
    property var targetScreen
    color: "black"
    visible: false
    LayerShell.Window.scope: "fenestra-security"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityExclusive

    property int focusIndex: 0
    property string menu: ""   // "" | network | accessibility | power
    readonly property var items: [
        { text: "Lock", action: () => { close(); Session.lock() } },
        { text: "Switch user", action: () => { close(); Session.switchUser() } },
        { text: "Sign out", action: () => { close(); Session.logout() } },
        { text: "Change a password", action: () => { close(); Apps.runCommand("fenestra-settings --page signin") } },
        { text: "Task Manager", action: () => { close(); Apps.runCommand("fenestra-taskmgr") } },
    ]

    function open() {
        if (targetScreen) ShellUtil.placeOnScreen(sec, targetScreen.name)
        focusIndex = 0; menu = ""
        visible = true
        requestActivate()
        keys.forceActiveFocus()
    }
    function close() { visible = false; menu = "" }

    Item {
        id: keys
        anchors.fill: parent
        focus: true
        Keys.onPressed: (e) => {
            const n = sec.items.length + 1   // + Cancel
            if (e.key === Qt.Key_Escape) { if (sec.menu) sec.menu = ""; else sec.close() }
            else if (e.key === Qt.Key_Down || e.key === Qt.Key_Tab) sec.focusIndex = (sec.focusIndex + 1) % n
            else if (e.key === Qt.Key_Up || e.key === Qt.Key_Backtab) sec.focusIndex = (sec.focusIndex + n - 1) % n
            else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space)
                sec.focusIndex < sec.items.length ? sec.items[sec.focusIndex].action() : sec.close()
            e.accepted = true   // everything else is swallowed
        }
    }

    // dark-100-20-secure-attention: options as one column 87 px left of the centre, all as wide as
    // the longest (+ 19 px), 44 px rows; the focus frame is 2 px white, 3 px above and below the row.
    // Cancel 120 × 32, 78 px left of the centre.
    Column {
        id: options
        x: sec.width / 2 - 87; y: sec.height / 2 - 177
        property real widest: 120
        Repeater {
            model: sec.items
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: options.widest + 19; height: 44
                color: im.pressed ? Qt.rgba(1, 1, 1, 0.04) : im.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                Rectangle { visible: sec.focusIndex === index; y: -3; width: parent.width; height: parent.height + 6
                            color: "transparent"; border.color: "white"; border.width: 2 }
                Text { id: label; x: 10; anchors.verticalCenter: parent.verticalCenter; text: Strings.tr(modelData.text)
                       color: "white"; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                       onImplicitWidthChanged: options.widest = Math.max(options.widest, implicitWidth)
                       Component.onCompleted: options.widest = Math.max(options.widest, implicitWidth) }
                MouseArea { id: im; anchors.fill: parent; hoverEnabled: true; onClicked: modelData.action() }
            }
        }
    }
    Rectangle {
        x: sec.width / 2 - 78; y: sec.height / 2 + 83; width: 120; height: 32; radius: 4
        color: cm.pressed ? "#2b2b2b" : cm.containsMouse ? "#3b3b3b" : "#333333"
        border.color: sec.focusIndex === sec.items.length ? "white" : "transparent"; border.width: 2
        Text { anchors.centerIn: parent; text: Strings.tr("Cancel"); color: "white"; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
        MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; onClicked: sec.close() }
    }
    // Corner buttons: 40 × 40 at 168 / 120 / 72 px from the right, icons centred 42 px over the bottom.
    Repeater {
        model: [["network", NetworkStatus.kind === "wifi" ? "network-wifi" : NetworkStatus.connected ? "network-wired" : "network-offline", 168, "Network"],
                ["accessibility", "accessibility", 120, "Accessibility"],
                ["power", "power", 72, "Power"]]
        delegate: Rectangle {
            required property var modelData
            x: sec.width - modelData[2]; y: sec.height - 62; width: 40; height: 40; radius: 4
            color: bm.pressed ? Qt.rgba(1, 1, 1, 0.04) : bm.containsMouse || sec.menu === modelData[0] ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
            Accessible.name: Strings.tr(modelData[3])
            Image { anchors.centerIn: parent; width: 16; height: 16; source: Metrics.assets + "security/" + modelData[1] + ".svg"
                    sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio) }
            MouseArea { id: bm; anchors.fill: parent; hoverEnabled: true; onClicked: sec.menu = sec.menu === modelData[0] ? "" : modelData[0] }
        }
    }
    // Corner menus: 12 px from the screen edge, 8 px above their button.
    Rectangle {
        visible: sec.menu !== ""
        x: sec.width - width - 12; y: sec.height - 62 - 8 - height
        width: 220; height: menuCol.height + 8; radius: 8
        color: "#2c2c2c"; border.color: Qt.rgba(1, 1, 1, 0.08)
        Column {
            id: menuCol
            x: 4; y: 4; width: parent.width - 8
            Column {
                visible: sec.menu === "network"
                width: parent.width; leftPadding: 12; topPadding: 8; bottomPadding: 10
                Text { text: NetworkStatus.name || Strings.tr("Network"); color: "white"; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                Text { text: Strings.tr(NetworkStatus.limited ? "No internet access" : NetworkStatus.connected ? "Connected" : "Not connected")
                       color: Qt.rgba(1, 1, 1, 0.79); font.family: Metrics.fontFamily; font.pixelSize: 12 }
            }
            Repeater {
                model: sec.menu === "network" ? [{ text: Strings.tr("Wi-Fi") + (WifiNetworks.enabled ? ": " + Strings.tr("On") : ": " + Strings.tr("Off")), action: () => WifiNetworks.enabled = !WifiNetworks.enabled }]
                     : sec.menu === "accessibility" ? [{ text: Strings.tr("Accessibility settings"), action: () => { sec.close(); Apps.runCommand("fenestra-settings --page accessibility") } }]
                     : sec.menu === "power" ? [{ text: Strings.tr("Sleep"), icon: "sleep", action: () => { sec.close(); Session.suspend() } },
                                               { text: Strings.tr("Shut down"), icon: "shutdown", action: () => { sec.close(); Session.powerOff() } },
                                               { text: Strings.tr("Restart"), icon: "restart", action: () => { sec.close(); Session.reboot() } }]
                     : []
                delegate: Rectangle {
                    required property var modelData
                    width: menuCol.width; height: 36; radius: 4
                    color: mm.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                    Image { visible: modelData.icon !== undefined; x: 12; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
                            source: modelData.icon ? Metrics.assets + "security/" + modelData.icon + ".svg" : "" }
                    Text { x: modelData.icon ? 40 : 12; anchors.verticalCenter: parent.verticalCenter; text: modelData.text
                           color: "white"; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                    MouseArea { id: mm; anchors.fill: parent; hoverEnabled: true; onClicked: modelData.action() }
                }
            }
        }
    }
}

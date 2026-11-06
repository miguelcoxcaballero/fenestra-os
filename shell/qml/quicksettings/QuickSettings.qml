// SPDX-License-Identifier: GPL-3.0-or-later
// Quick settings (Q01) with the media card above it (Q02): two cards, 12 px apart, 12 px over the
// taskbar and 13 px from the screen edge. Layout of quickPanel.js: 3 columns of 104 px tiles,
// brightness then volume sliders, footer with battery, Edit and Settings.
import QtQuick
import org.kde.bluezqt as BluezQt
import Fenestra.Shell

Flyout {
    id: qs
    padding: 0
    background.visible: false
    property string page: ""            // "" | "wifi" | "bluetooth" | "output"
    onDismissed: page = ""

    Column {
        spacing: 12
        // ---- Media card (Q02, mediaPanel.js: 350 px, padding 22 24) ----
        Card {
            visible: Media.available
            width: Metrics.quickWidth; height: mediaRow.height + 44
            Row {
                id: mediaRow
                x: 24; y: 22; spacing: 16; width: parent.width - 48
                Rectangle {
                    width: 64; height: 64; radius: 4; clip: true
                    color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.05)
                    Image { anchors.fill: parent; source: Media.artUrl; fillMode: Image.PreserveAspectCrop; visible: Media.artUrl !== ""; asynchronous: true }
                    Image { anchors.centerIn: parent; width: 32; height: 32; source: "image://icon/audio-x-generic"; visible: Media.artUrl === "" }
                }
                Column {
                    width: parent.width - 80; spacing: 2
                    Row { spacing: 6
                        Image { width: 16; height: 16; source: "image://icon/" + Media.appIcon; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: Media.appName; color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 13 } }
                    Text { width: parent.width; elide: Text.ElideRight; text: Media.title || Strings.tr("Playing")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 15; font.weight: Font.DemiBold }
                    Text { width: parent.width; elide: Text.ElideRight; text: Media.artist; visible: text !== ""
                           color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 13 }
                    Row {
                        spacing: 24; topPadding: 8
                        Repeater {
                            model: [["media-skip-backward-symbolic", "Previous", () => Media.previous(), Media.canGoPrevious],
                                    [Media.playing ? "media-playback-pause-symbolic" : "media-playback-start-symbolic", Media.playing ? "Pause" : "Play", () => Media.playPause(), true],
                                    ["media-skip-forward-symbolic", "Next", () => Media.next(), Media.canGoNext]]
                            delegate: Rectangle {
                                required property var modelData
                                width: 34; height: 34; radius: 4
                                opacity: modelData[3] ? 1 : 0.4
                                color: mm.containsMouse ? Theme.hover : "transparent"
                                Accessible.name: Strings.tr(modelData[1])
                                SymbolicIcon { anchors.centerIn: parent; name: modelData[0]; size: 22 }
                                MouseArea { id: mm; anchors.fill: parent; hoverEnabled: true; enabled: modelData[3]; onClicked: modelData[2]() }
                            }
                        }
                    }
                }
            }
        }

        // ---- Quick settings card ----
        Card {
            width: Metrics.quickWidth; height: (qs.page === "" ? main.height : sub.height) + footer.height
            Column {
                id: main
                visible: qs.page === ""
                width: parent.width
                Grid {
                    x: 20; topPadding: 20; columns: 3; columnSpacing: 24; rowSpacing: 18
                    QuickTile {
                        visible: WifiNetworks.hasWifi
                        label: NetworkStatus.kind === "wifi" ? NetworkStatus.name : Strings.tr("Wi-Fi")
                        iconName: WifiNetworks.enabled ? "network-wireless-signal-excellent-symbolic" : "network-wireless-disabled-symbolic"
                        checked: WifiNetworks.enabled; hasPage: true
                        onToggled: WifiNetworks.enabled = !WifiNetworks.enabled
                        onPageRequested: { WifiNetworks.scan(); qs.page = "wifi" }
                    }
                    QuickTile {
                        visible: BluezQt.Manager.adapters.length > 0
                        label: Strings.tr("Bluetooth")
                        iconName: "bluetooth-active-symbolic"
                        checked: BluezQt.Manager.bluetoothOperational
                        hasPage: true
                        onToggled: {
                            const on = !BluezQt.Manager.bluetoothOperational
                            BluezQt.Manager.bluetoothBlocked = !on
                            for (const a of BluezQt.Manager.adapters) a.powered = on
                        }
                        onPageRequested: qs.page = "bluetooth"
                    }
                    QuickTile {
                        label: Strings.tr("Airplane mode"); iconName: "airplane-mode-symbolic"
                        checked: WifiNetworks.airplaneMode
                        onToggled: {
                            const on = !WifiNetworks.airplaneMode
                            WifiNetworks.airplaneMode = on
                            BluezQt.Manager.bluetoothBlocked = on
                        }
                    }
                    QuickTile {
                        visible: PowerProfiles.available
                        label: Strings.tr("Battery saver"); iconName: "battery-level-50-symbolic"
                        checked: PowerProfiles.active === "power-saver"
                        onToggled: PowerProfiles.active = checked ? "balanced" : "power-saver"
                    }
                    QuickTile {
                        label: Strings.tr("Night light"); iconName: "night-light-symbolic"
                        checked: NightLight.active
                        onToggled: NightLight.active = !NightLight.active
                    }
                    QuickTile {
                        label: Strings.tr("Accessibility"); iconName: "preferences-desktop-accessibility-symbolic"
                        onToggled: { qs.close(); Apps.runCommand("fenestra-settings --page accessibility") }
                    }
                }
                // Sliders: brightness then volume (quickPanel.js), full width.
                Column {
                    x: 20; width: parent.width - 40; topPadding: 22; bottomPadding: 20; spacing: 14
                    Row {
                        visible: Brightness.available
                        width: parent.width; spacing: 12
                        SymbolicIcon { name: "display-brightness-symbolic"; anchors.verticalCenter: parent.verticalCenter }
                        Slider { width: parent.width - 28; value: Brightness.percent; onMoved: (v) => Brightness.percent = v }
                    }
                    Row {
                        visible: AudioStatus.available
                        width: parent.width; spacing: 12
                        Item { width: 16; height: 16; anchors.verticalCenter: parent.verticalCenter
                               SymbolicIcon { name: AudioStatus.iconName }
                               MouseArea { anchors.fill: parent; onClicked: AudioStatus.muted = !AudioStatus.muted } }
                        Slider { width: parent.width - 28 - 40; value: AudioStatus.volume; onMoved: (v) => AudioStatus.volume = v }
                        Rectangle {
                            width: 28; height: 28; radius: 4; anchors.verticalCenter: parent.verticalCenter
                            color: om.containsMouse ? Theme.hover : "transparent"
                            Text { anchors.centerIn: parent; text: "›"; font.pixelSize: 16; color: Theme.text }
                            Accessible.name: Strings.tr("Sound output")
                            MouseArea { id: om; anchors.fill: parent; hoverEnabled: true; onClicked: qs.page = "output" }
                        }
                    }
                }
            }
            // ---- Subpages ----
            Column {
                id: sub
                visible: qs.page !== ""
                width: parent.width
                Item {
                    width: parent.width; height: 56
                    Rectangle { x: 12; anchors.verticalCenter: parent.verticalCenter; width: 32; height: 32; radius: 4
                                color: back.containsMouse ? Theme.hover : "transparent"
                                Text { anchors.centerIn: parent; text: "‹"; font.pixelSize: 18; color: Theme.text }
                                MouseArea { id: back; anchors.fill: parent; hoverEnabled: true; onClicked: qs.page = "" } }
                    Text { x: 52; anchors.verticalCenter: parent.verticalCenter
                           text: Strings.tr(qs.page === "wifi" ? "Wi-Fi" : qs.page === "bluetooth" ? "Bluetooth" : "Sound output")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                }
                Loader {
                    width: parent.width
                    sourceComponent: qs.page === "wifi" ? wifiPage : qs.page === "bluetooth" ? btPage : qs.page === "output" ? outputPage : null
                }
                Item { width: 1; height: 12 }
            }
            // ---- Footer ----
            Rectangle {
                id: footer
                anchors.bottom: parent.bottom
                width: parent.width; height: Metrics.quickFooterHeight
                bottomLeftRadius: Metrics.flyoutRadius; bottomRightRadius: Metrics.flyoutRadius
                color: Theme.dark ? Qt.rgba(0, 0, 0, 0.14) : Qt.rgba(0, 0, 0, 0.03)
                Rectangle { width: parent.width; height: 1; color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06) }
                Row {
                    x: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    visible: PowerStatus.hasBattery
                    SymbolicIcon { src: PowerStatus.iconSource; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: PowerStatus.percentage + " %"; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12
                           anchors.verticalCenter: parent.verticalCenter }
                }
                Rectangle {
                    anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                    width: 28; height: 28; radius: 4
                    color: sm.containsMouse ? Theme.hover : "transparent"
                    Accessible.name: Strings.tr("All settings")
                    SymbolicIcon { anchors.centerIn: parent; name: "emblem-system-symbolic" }
                    MouseArea { id: sm; anchors.fill: parent; hoverEnabled: true; onClicked: { qs.close(); Apps.runCommand("fenestra-settings") } }
                }
            }
        }
    }

    Component {
        id: wifiPage
        Column {
            width: 400
            Repeater {
                model: WifiNetworks
                delegate: Rectangle {
                    required property int index
                    required property var model
                    property bool asking: false
                    x: 8; width: 384; height: asking ? 96 : 48; radius: 4
                    color: wm.containsMouse || asking ? Theme.hover : "transparent"
                    SymbolicIcon { x: 12; y: 16; name: "network-wireless-signal-" + ["none", "weak", "ok", "good", "excellent"][Math.min(4, Math.floor(model.signal / 20))] + "-symbolic" }
                    Column { x: 40; y: 8
                        Text { text: model.ssid; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                        Text { text: Strings.tr(model.active ? "Connected" : model.secured ? "Secured" : "Open"); color: Theme.textSecondary
                               font.family: Metrics.fontFamily; font.pixelSize: 12 } }
                    MouseArea { id: wm; anchors.fill: parent; hoverEnabled: true
                        onClicked: model.active ? WifiNetworks.disconnectFrom(index)
                                   : WifiNetworks.needsPassword(index) ? (parent.asking = true, pw.forceActiveFocus()) : WifiNetworks.connectTo(index) }
                    Rectangle {
                        visible: parent.asking
                        x: 40; y: 52; width: parent.width - 52; height: 32; radius: 4
                        color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : "white"
                        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.1)
                        TextInput { id: pw; x: 10; width: parent.width - 20; anchors.verticalCenter: parent.verticalCenter
                                    echoMode: TextInput.Password; color: Theme.text; font.pixelSize: 13
                                    onAccepted: { WifiNetworks.connectTo(index, text); parent.parent.asking = false } }
                    }
                }
            }
            Text { visible: WifiNetworks.rowCount() === 0; x: 20; text: Strings.tr("No networks found"); color: Theme.textSecondary
                   font.family: Metrics.fontFamily; font.pixelSize: 12 }
        }
    }
    Component {
        id: btPage
        Column {
            width: 400
            Repeater {
                model: BluezQt.DevicesModel { }
                delegate: Rectangle {
                    required property var model
                    visible: model.Paired || model.Connected
                    x: 8; width: 384; height: visible ? 48 : 0; radius: 4
                    color: bm2.containsMouse ? Theme.hover : "transparent"
                    Image { x: 12; y: 12; width: 24; height: 24; source: "image://icon/" + (model.Icon || "bluetooth-active") }
                    Column { x: 48; y: 6
                        Text { text: model.Name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                        Text { text: Strings.tr(model.Connected ? "Connected" : "Paired"); color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 } }
                    MouseArea { id: bm2; anchors.fill: parent; hoverEnabled: true
                        onClicked: model.Connected ? model.Device.disconnectFromDevice() : model.Device.connectToDevice() }
                }
            }
            Rectangle {
                x: 20; width: 160; height: 32; radius: 4
                color: am.containsMouse ? Theme.hover : (Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : "white")
                border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.1)
                Text { anchors.centerIn: parent; text: Strings.tr("Add a device"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 13 }
                MouseArea { id: am; anchors.fill: parent; hoverEnabled: true; onClicked: { qs.close(); Apps.runCommand("fenestra-settings --page bluetooth") } }
            }
        }
    }
    Component {
        id: outputPage
        Column {
            width: 400
            Repeater {
                model: AudioStatus.outputs
                delegate: Rectangle {
                    required property var modelData
                    x: 8; width: 384; height: 44; radius: 4
                    color: om2.containsMouse ? Theme.hover : modelData.isDefault ? Theme.pressed : "transparent"
                    Rectangle { visible: modelData.isDefault; x: 0; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 16; radius: 2; color: Theme.accentFill }
                    Text { x: 16; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 32; elide: Text.ElideRight
                           text: modelData.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                    MouseArea { id: om2; anchors.fill: parent; hoverEnabled: true; onClicked: AudioStatus.setDefaultOutput(modelData.id) }
                }
            }
        }
    }
}

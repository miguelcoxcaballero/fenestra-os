// SPDX-License-Identifier: GPL-3.0-or-later
// Quick settings (Q01) with the media card above it (Q02): two separate cards, 12 px apart, 12 px
// over the taskbar and 12 px from the screen edge, 360 px wide (dark-100-14-quick-media). Quick
// settings: 3 columns of 96 × 48 tiles, a divider, the volume (and brightness) sliders and the
// footer with battery and All settings. Card-relative positions come from quick.* tokens.
import QtQuick
import org.kde.bluezqt as BluezQt
import Fenestra.Shell

Flyout {
    id: qs
    padding: 0
    background.visible: false
    property string page: ""            // "" | "wifi" | "bluetooth" | "output"
    onDismissed: page = ""

    component GlyphButton: Rectangle {
        id: gb
        property string glyph
        property url glyphSource
        property bool active: true
        signal clicked()
        width: 32; height: 32; radius: Metrics.controlRadius
        color: gm.pressed ? Theme.pressed : gm.containsMouse ? Theme.hover : "transparent"
        SymbolicIcon { monochrome: true; anchors.centerIn: parent; name: gb.glyphSource.toString() === "" ? gb.glyph : ""; src: gb.glyphSource
                       opacity: gb.active ? 1 : 0.4 }
        MouseArea { id: gm; anchors.fill: parent; hoverEnabled: true; enabled: gb.active; onClicked: gb.clicked() }
    }

    // Opening and closing: Flyout's taskbar motion (rises from behind the taskbar, design/motion.json).
    // Subpages slide in from the right, the main page back from the left (PopupMotion "page").
    onPageChanged: {
        if (!visible) return pageMotion.reset()
        pageMotion.target = page === "" ? main : sub
        pageMotion.kind = page === "" ? "page-back" : "page-forward"
        pageMotion.enter()
    }
    PopupMotion { id: pageMotion }

    Column {
        spacing: Metrics.flyoutGap
        // ---- Media card (Q02): app line, title / artist, art on the right, transport centred ----
        Card {
            visible: Media.available
            width: Metrics.quickWidth; height: Metrics.quickMediaHeight
            Image { x: 25; y: 18; width: 16; height: 16; sourceSize: Qt.size(32, 32); source: "image://icon/" + Media.appIcon }
            Text { x: 50; y: 16; text: Media.appName; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            Column {
                x: 24; y: 58; width: 240; spacing: 2
                Text { width: parent.width; elide: Text.ElideRight; text: Media.title || Strings.tr("Playing")
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
                Text { width: parent.width; elide: Text.ElideRight; text: Media.artist; visible: text !== ""
                       color: Metrics.col("panel.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
            }
            Rectangle {
                readonly property int art: Metrics.n("quick.media.art", 58)
                x: parent.width - 25 - art; y: 46; width: art; height: art; radius: 4; clip: true
                color: Metrics.col("panel.control")
                Image { anchors.fill: parent; source: Media.artUrl; fillMode: Image.PreserveAspectCrop; visible: Media.artUrl !== ""; asynchronous: true }
                Image { anchors.centerIn: parent; width: 32; height: 32; source: "image://icon/" + Media.appIcon; visible: Media.artUrl === "" }
            }
            Repeater {
                // Filled 14 px transport glyphs as on dark-100-14-quick-media (status/media-*.svg).
                model: [["media-previous", "Previous", () => Media.previous(), Media.canGoPrevious],
                        [Media.playing ? "media-pause" : "media-play", Media.playing ? "Pause" : "Play", () => Media.playPause(), true],
                        ["media-next", "Next", () => Media.next(), Media.canGoNext]]
                delegate: GlyphButton {
                    required property var modelData
                    required property int index
                    x: Metrics.quickWidth / 2 + (index - 1) * Metrics.n("quick.media.controls.pitch", 66) - width / 2
                    y: Metrics.n("quick.media.controls.y", 137) - height / 2
                    glyphSource: Metrics.assets + "status/" + modelData[0] + ".svg"; active: modelData[3]
                    Accessible.name: Strings.tr(modelData[1])
                    onClicked: modelData[2]()
                }
            }
        }

        // ---- Quick settings card ----
        Card {
            id: card
            width: Metrics.quickWidth
            clip: pageMotion.busy
            readonly property int footerH: Metrics.quickFooterHeight
            height: (qs.page === "" ? main.height : sub.height) + footerH + 2
            Item {
                id: main
                visible: qs.page === ""
                transform: pageMotion.target === main ? pageMotion.shift : []
                width: parent.width
                // a page holds two rows of tiles, as on the reference (quick.rows.min)
                readonly property int rows: Math.max(Metrics.n("quick.rows.min", 2), Math.ceil(tiles.visibleCount / 3))
                readonly property int dividerY: Metrics.n("quick.grid.y", 23) + rows * Metrics.n("quick.tile.pitch.y", 96) - 2
                height: dividerY + 1 + sliders.height
                Grid {
                    id: tiles
                    readonly property int visibleCount: { let n = 0; for (let i = 0; i < children.length; ++i) if (children[i].visible) ++n; return n }
                    x: Metrics.n("quick.grid.x", 24); y: Metrics.n("quick.grid.y", 23)
                    columns: 3; columnSpacing: Metrics.n("quick.tile.gap", 12); rowSpacing: 0
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
                Rectangle { x: 1; y: main.dividerY; width: parent.width - 2; height: 1; color: Metrics.col("quick.separator") }
                // Sliders: brightness then volume, 48 px rows; one row is centred at quick.slider.y.
                Column {
                    id: sliders
                    y: main.dividerY + 1
                    width: parent.width
                    readonly property int rowH: 48
                    topPadding: Metrics.n("quick.slider.y", 251) - Metrics.n("quick.separator.y", 213) - 1 - rowH / 2
                    bottomPadding: 72 - topPadding - rowH
                    Item {
                        visible: Brightness.available
                        width: parent.width; height: sliders.rowH
                        SymbolicIcon { monochrome: true; x: 25; anchors.verticalCenter: parent.verticalCenter; name: "display-brightness-symbolic" }
                        Slider { x: Metrics.n("quick.slider.x", 57) - thumb / 2; width: Metrics.n("quick.slider.width", 244) + thumb
                                 anchors.verticalCenter: parent.verticalCenter
                                 value: Brightness.percent; onMoved: (v) => Brightness.percent = v }
                    }
                    // Volume: always there; without an output device it shows muted and disabled.
                    Item {
                        width: parent.width; height: sliders.rowH
                        Item { x: 25; width: 16; height: 16; anchors.verticalCenter: parent.verticalCenter
                               SymbolicIcon { monochrome: true; name: AudioStatus.available ? AudioStatus.iconName : "audio-volume-muted-symbolic" }
                               MouseArea { anchors.fill: parent; enabled: AudioStatus.available; onClicked: AudioStatus.muted = !AudioStatus.muted } }
                        Slider { x: Metrics.n("quick.slider.x", 57) - thumb / 2; width: Metrics.n("quick.slider.width", 244) + thumb
                                 anchors.verticalCenter: parent.verticalCenter; enabled_: AudioStatus.available; dimmed: !AudioStatus.available
                                 value: AudioStatus.available ? AudioStatus.volume : 0; onMoved: (v) => AudioStatus.volume = v }
                        Rectangle {
                            x: 307; width: 34; height: 32; radius: Metrics.controlRadius; anchors.verticalCenter: parent.verticalCenter
                            color: om.pressed ? Theme.pressed : om.containsMouse ? Theme.hover : "transparent"
                            Row { anchors.centerIn: parent; spacing: 2
                                  SymbolicIcon { monochrome: true; name: "audio-card-symbolic"; anchors.verticalCenter: parent.verticalCenter }
                                  SymbolicIcon { monochrome: true; name: "go-next-symbolic"; size: 10; anchors.verticalCenter: parent.verticalCenter } }
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
                transform: pageMotion.target === sub ? pageMotion.shift : []
                width: parent.width
                Item {
                    width: parent.width; height: 56
                    GlyphButton { x: 12; anchors.verticalCenter: parent.verticalCenter; glyph: "go-previous-symbolic"; onClicked: qs.page = "" }
                    Text { x: 52; anchors.verticalCenter: parent.verticalCenter
                           text: Strings.tr(qs.page === "wifi" ? "Wi-Fi" : qs.page === "bluetooth" ? "Bluetooth" : "Sound output")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
                }
                Loader {
                    width: parent.width
                    sourceComponent: qs.page === "wifi" ? wifiPage : qs.page === "bluetooth" ? btPage : qs.page === "output" ? outputPage : null
                }
                Item { width: 1; height: 12 }
            }
            // ---- Footer: divider, 47 px band, battery left, All settings right ----
            Rectangle {
                x: 1; y: parent.height - 1 - card.footerH - 1; width: parent.width - 2; height: 1
                color: Metrics.col("panel.divider")
            }
            Rectangle {
                id: footer
                x: 1; y: parent.height - 1 - card.footerH
                width: parent.width - 2; height: card.footerH
                bottomLeftRadius: Metrics.flyoutRadius - 1; bottomRightRadius: Metrics.flyoutRadius - 1
                color: Metrics.col("panel.fill.alt")
                Row {
                    x: 19; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    visible: PowerStatus.hasBattery
                    SymbolicIcon { monochrome: true; src: PowerStatus.iconSource; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: PowerStatus.percentage + " %"; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
                           anchors.verticalCenter: parent.verticalCenter }
                }
                GlyphButton {
                    // the gear's centre is 31 px from the card's right edge (dark-100-12-quick element 26)
                    x: parent.width + 1 - 31 - width / 2; anchors.verticalCenter: parent.verticalCenter
                    glyph: "emblem-system-symbolic"
                    Accessible.name: Strings.tr("All settings")
                    onClicked: { qs.close(); Apps.runCommand("fenestra-settings") }
                }
            }
        }
    }

    Component {
        id: wifiPage
        Column {
            width: Metrics.quickWidth
            Repeater {
                model: WifiNetworks
                delegate: Rectangle {
                    required property int index
                    required property var model
                    property bool asking: false
                    x: 8; width: Metrics.quickWidth - 16; height: asking ? 96 : 48; radius: 4
                    color: wm.containsMouse || asking ? Theme.hover : "transparent"
                    SymbolicIcon { monochrome: true; x: 12; y: 16; name: "network-wireless-signal-" + ["none", "weak", "ok", "good", "excellent"][Math.min(4, Math.floor(model.signal / 20))] + "-symbolic" }
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
            width: Metrics.quickWidth
            Repeater {
                model: BluezQt.DevicesModel { }
                delegate: Rectangle {
                    required property var model
                    visible: model.Paired || model.Connected
                    x: 8; width: Metrics.quickWidth - 16; height: visible ? 48 : 0; radius: 4
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
            width: Metrics.quickWidth
            Repeater {
                model: AudioStatus.outputs
                delegate: Rectangle {
                    required property var modelData
                    x: 8; width: Metrics.quickWidth - 16; height: 44; radius: 4
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

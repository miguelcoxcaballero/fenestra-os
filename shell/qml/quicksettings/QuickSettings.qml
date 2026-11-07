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
    recipe: "panel"
    blurItems: [mediaCard.material, card.material]
    property string page: ""            // "" | "wifi" | "bluetooth" | "output"
    onDismissed: page = ""
    // Test hooks (tests/shell-kwin): fake Wi-Fi networks and Bluetooth devices.
    property ListModel testWifi: ListModel {}
    property ListModel testDevices: ListModel {}
    function testFill(networks, devices) {
        testWifi.clear(); testDevices.clear()
        for (let i = 0; i < networks; ++i)
            testWifi.append({ ssid: "Network " + (i + 1), signal: 100 - (i * 7) % 90, active: i === 0, secured: i % 3 !== 2 })
        for (let i = 0; i < devices; ++i)
            testDevices.append({ Name: "Device " + (i + 1), Paired: true, Connected: i === 0, Icon: "audio-headphones" })
    }

    component GlyphButton: Rectangle {
        id: gb
        property string glyph
        property url glyphSource
        property string fluent          // Segoe Fluent Icons code point, used when the font is there
        property bool active: true
        signal clicked()
        width: 32; height: 32; radius: Metrics.controlRadius
        color: gm.pressed ? Theme.pressed : gm.containsMouse ? Theme.hover : "transparent"
        SymbolicIcon { monochrome: true; anchors.centerIn: parent; name: gb.glyphSource.toString() === "" ? gb.glyph : ""; src: gb.glyphSource
                       visible: !(FluentFont.available && gb.fluent !== ""); opacity: gb.active ? 1 : 0.4 }
        FluentGlyph { anchors.centerIn: parent; glyph: gb.fluent; visible: FluentFont.available && gb.fluent !== ""; opacity: gb.active ? 1 : 0.4 }
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
            id: mediaCard
            visible: Media.available
            width: Metrics.quickWidth; height: Metrics.quickMediaHeight
            Image { x: 25; y: 18; width: 16; height: 16; sourceSize: Qt.size(32, 32); source: "image://icon/" + Media.appIcon }
            Text { x: 50; y: 16; text: Media.appName; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            Column {
                x: 24; y: 58; width: 240; spacing: 2
                Text { width: parent.width; elide: Text.ElideRight; text: Media.title || Strings.tr("Playing")
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
                Text { width: parent.width; elide: Text.ElideRight; text: Media.artist; visible: text !== ""
                       color: Metrics.pcol("panel.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
            }
            Rectangle {
                readonly property int art: Metrics.n("quick.media.art", 58)
                x: parent.width - 25 - art; y: 46; width: art; height: art; radius: 4; clip: true
                color: Metrics.pcol("panel.control")
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
            clipContent: pageMotion.busy
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
                        glyph: "\ue701"
                        checked: WifiNetworks.enabled; hasPage: true
                        onToggled: WifiNetworks.enabled = !WifiNetworks.enabled
                        onPageRequested: { WifiNetworks.scan(); qs.page = "wifi" }
                    }
                    QuickTile {
                        visible: BluezQt.Manager.adapters.length > 0
                        label: Strings.tr("Bluetooth")
                        iconName: "bluetooth-active-symbolic"; glyph: "\ue702"
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
                        label: Strings.tr("Airplane mode"); iconName: "airplane-mode-symbolic"; glyph: "\ue709"
                        checked: WifiNetworks.airplaneMode
                        onToggled: {
                            const on = !WifiNetworks.airplaneMode
                            WifiNetworks.airplaneMode = on
                            BluezQt.Manager.bluetoothBlocked = on
                        }
                    }
                    QuickTile {
                        visible: PowerProfiles.available
                        label: Strings.tr("Battery saver"); iconName: "battery-level-50-symbolic"; glyph: "\uec0a"
                        checked: PowerProfiles.active === "power-saver"
                        onToggled: PowerProfiles.active = checked ? "balanced" : "power-saver"
                    }
                    QuickTile {
                        label: Strings.tr("Night light"); iconName: "night-light-symbolic"; glyph: "\uf08c"
                        checked: NightLight.active
                        onToggled: NightLight.active = !NightLight.active
                    }
                    QuickTile {
                        label: Strings.tr("Accessibility"); iconName: "preferences-desktop-accessibility-symbolic"; glyph: "\ue776"
                        onToggled: { qs.close(); Apps.runCommand("fenestra-settings --page accessibility") }
                    }
                }
                Rectangle { x: 1; y: main.dividerY; width: parent.width - 2; height: 1; color: Metrics.pcol("quick.separator") }
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
                        FluentGlyph { x: 25; anchors.verticalCenter: parent.verticalCenter; glyph: "\ue706"; fallback: "display-brightness-symbolic" }
                        Slider { x: Metrics.n("quick.slider.x", 57) - thumb / 2; width: Metrics.n("quick.slider.width", 244) + thumb
                                 anchors.verticalCenter: parent.verticalCenter
                                 value: Brightness.percent; onMoved: (v) => Brightness.percent = v }
                    }
                    // Keyboard backlight (any laptop with a kbd_backlight LED): not in Windows' own
                    // Quick settings, which leaves it to the maker's app (Samsung Settings › Keyboard,
                    // a 4-step level bar); here a row like brightness's, snapping to the device's levels.
                    Item {
                        visible: KbdBacklight.available
                        width: parent.width; height: visible ? sliders.rowH : 0
                        FluentGlyph { x: 25; anchors.verticalCenter: parent.verticalCenter; glyph: ""; fallback: "keyboard-brightness-symbolic" }
                        Slider { x: Metrics.n("quick.slider.x", 57) - thumb / 2; width: Metrics.n("quick.slider.width", 244) + thumb
                                 anchors.verticalCenter: parent.verticalCenter
                                 Accessible.name: Strings.tr("Keyboard backlight")
                                 value: KbdBacklight.percent; onMoved: (v) => KbdBacklight.percent = v }
                    }
                    // Volume: always there; without an output device it shows muted and disabled.
                    Item {
                        width: parent.width; height: sliders.rowH
                        Item { x: 25; width: 16; height: 16; anchors.verticalCenter: parent.verticalCenter
                               FluentGlyph { fallback: AudioStatus.available ? AudioStatus.iconName : "audio-volume-muted-symbolic"
                                              glyph: !AudioStatus.available || AudioStatus.muted ? "\ue74f" : AudioStatus.volume <= 0 ? "\ue992"
                                                     : AudioStatus.volume < 34 ? "\ue993" : AudioStatus.volume < 67 ? "\ue994" : "\ue995" }
                               MouseArea { anchors.fill: parent; enabled: AudioStatus.available; onClicked: AudioStatus.muted = !AudioStatus.muted } }
                        Slider { x: Metrics.n("quick.slider.x", 57) - thumb / 2; width: Metrics.n("quick.slider.width", 244) + thumb
                                 anchors.verticalCenter: parent.verticalCenter; enabled_: AudioStatus.available; dimmed: !AudioStatus.available
                                 value: AudioStatus.available ? AudioStatus.volume : 0; onMoved: (v) => AudioStatus.volume = v }
                        Rectangle {
                            x: 307; width: 34; height: 32; radius: Metrics.controlRadius; anchors.verticalCenter: parent.verticalCenter
                            color: om.pressed ? Theme.pressed : om.containsMouse ? Theme.hover : "transparent"
                            Row { anchors.centerIn: parent; spacing: 2
                                  FluentGlyph { glyph: "\uf4c3"; fallback: "audio-card-symbolic"; anchors.verticalCenter: parent.verticalCenter }
                                  FluentGlyph { glyph: "\ue974"; fallback: "go-next-symbolic"; size: FluentFont.available ? 12 : 10; anchors.verticalCenter: parent.verticalCenter } }
                            Accessible.name: Strings.tr("Sound output")
                            MouseArea { id: om; anchors.fill: parent; hoverEnabled: true; onClicked: qs.page = "output" }
                        }
                    }
                }
            }
            // ---- Subpages ----
            // As Windows' L2 pages (Windows.UI.ShellCommon.pri, ControlCenterView: the L2 frame's
            // MinHeight is the main page's height; the page is a ScrollingPageTemplate): the page
            // keeps the main page's height, its header ("‹ Wi-Fi") and footer link stay put and
            // the list scrolls under an overlay scroll bar (OverlayScrollBar).
            Item {
                id: sub
                visible: qs.page !== ""
                transform: pageMotion.target === sub ? pageMotion.shift : []
                width: parent.width
                readonly property int headerH: Metrics.n("quick.page.header", 56)
                readonly property int footerH: qs.page === "output" ? 12 : Metrics.n("quick.page.footer", 52)
                height: Math.max(main.height, qs.page === "output" ? headerH + listView.contentHeight + footerH : 0)
                Item {
                    width: parent.width; height: sub.headerH
                    GlyphButton { x: 12; anchors.verticalCenter: parent.verticalCenter; glyph: "go-previous-symbolic"; fluent: "\ue72b"; onClicked: qs.page = "" }
                    Text { x: 52; anchors.verticalCenter: parent.verticalCenter
                           text: Strings.tr(qs.page === "wifi" ? "Wi-Fi" : qs.page === "bluetooth" ? "Bluetooth" : "Sound output")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
                }
                Flickable {
                    id: listView
                    y: sub.headerH; width: parent.width; height: sub.height - sub.headerH - sub.footerH
                    contentHeight: pageLoader.height
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick
                    HoverHandler { id: listHover }
                    Loader {
                        id: pageLoader
                        width: parent.width
                        sourceComponent: qs.page === "wifi" ? wifiPage : qs.page === "bluetooth" ? btPage : qs.page === "output" ? outputPage : null
                    }
                    WheelHandler {
                        // Windows scrolls 3 rows (48 px each) per notch; Qt's default is slower.
                        onWheel: (e) => { listView.contentY = Math.max(0, Math.min(listView.contentHeight - listView.height,
                                                                                    listView.contentY - e.angleDelta.y / 120 * 3 * 48)) }
                    }
                }
                OverlayScrollBar {
                    flickable: listView; areaHovered: listHover.hovered
                    x: parent.width - width - 1; y: listView.y + 2; height: listView.height - 4
                }
                Rectangle {
                    // Footer link ("More Wi-Fi settings"), 1 px rule above it.
                    visible: qs.page === "wifi" || qs.page === "bluetooth"
                    x: 8; y: sub.height - sub.footerH + 8; width: footLink.implicitWidth + 24; height: 32
                    radius: Metrics.controlRadius
                    color: flm.pressed ? Theme.pressed : flm.containsMouse ? Theme.hover : "transparent"
                    Text { id: footLink; x: 12; anchors.verticalCenter: parent.verticalCenter
                           text: Strings.tr(qs.page === "wifi" ? "More Wi-Fi settings" : "More Bluetooth settings")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: flm; anchors.fill: parent; hoverEnabled: true
                                onClicked: { qs.close(); Apps.runCommand("fenestra-settings --page " + (qs.page === "wifi" ? "wifi" : "bluetooth")) } }
                }
            }
            // ---- Footer: divider, 47 px band, battery left, All settings right ----
            Rectangle {
                x: 1; y: parent.height - 1 - card.footerH - 1; width: parent.width - 2; height: 1
                color: Metrics.pcol("panel.divider")
            }
            Rectangle {
                id: footer
                x: 1; y: parent.height - 1 - card.footerH
                width: parent.width - 2; height: card.footerH
                bottomLeftRadius: Metrics.flyoutRadius - 1; bottomRightRadius: Metrics.flyoutRadius - 1
                color: Metrics.pcol("panel.fill.alt")
                Row {
                    x: 19; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    visible: PowerStatus.hasBattery
                    SymbolicIcon { monochrome: true; src: PowerStatus.iconSource; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: PowerStatus.percentage + (Strings.es ? " %" : "%"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
                           anchors.verticalCenter: parent.verticalCenter }
                }
                GlyphButton {
                    // the gear's centre is 31 px from the card's right edge (dark-100-12-quick element 26)
                    x: parent.width + 1 - 31 - width / 2; anchors.verticalCenter: parent.verticalCenter
                    glyph: "emblem-system-symbolic"; fluent: "\ue713"
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
                model: qs.testWifi.count > 0 ? qs.testWifi : WifiNetworks
                delegate: Rectangle {
                    required property int index
                    required property var model
                    property bool asking: false
                    x: 8; width: Metrics.quickWidth - 16; height: asking ? 96 : 48; radius: 4
                    color: wm.containsMouse || asking ? Theme.hover : "transparent"
                    SymbolicIcon { monochrome: true; x: 12; y: 16; name: "network-wireless-signal-" + ["none", "weak", "ok", "good", "excellent"][Math.min(4, Math.floor(model.signal / 20))] + "-symbolic" }
                    Column { x: 40; y: 8
                        Text { text: model.ssid; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                        Text { text: model.status; color: Theme.textSecondary
                               font.family: Metrics.fontFamily; font.pixelSize: 12 } }
                    MouseArea { id: wm; anchors.fill: parent; hoverEnabled: true
                        onClicked: model.active ? WifiNetworks.disconnectFrom(index)
                                   : model.connecting ? WifiNetworks.cancel(index)
                                   : WifiNetworks.needsPassword(index) ? (parent.asking = true, pw.forceActiveFocus()) : WifiNetworks.connectTo(index) }
                    Connections { target: WifiNetworks
                        // wrong key: the password field comes back, the status shows Windows' message
                        function onKeyRejected(ssid) { if (ssid === model.ssid) { pw.parent.parent.asking = true; pw.text = ""; pw.forceActiveFocus() } } }
                    Rectangle {
                        visible: parent.asking
                        x: 40; y: 52; width: parent.width - 52; height: 32; radius: 4
                        color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : "white"
                        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.1)
                        TextInput { id: pw; x: 10; width: parent.width - 20; anchors.verticalCenter: parent.verticalCenter
                                    echoMode: TextInput.Password; color: Theme.text; font.pixelSize: 13
                                    onAccepted: { if (text.length > 0) { WifiNetworks.connectTo(index, text); text = ""; parent.parent.asking = false } }
                                    Keys.onEscapePressed: { text = ""; parent.parent.asking = false } }
                    }
                }
            }
            Text { visible: qs.testWifi.count === 0 && WifiNetworks.count === 0; x: 20; text: Strings.tr("No networks found"); color: Theme.textSecondary
                   font.family: Metrics.fontFamily; font.pixelSize: 12 }
        }
    }
    BluezQt.DevicesModel { id: btModel }
    Component {
        id: btPage
        Column {
            width: Metrics.quickWidth
            Repeater {
                model: qs.testDevices.count > 0 ? qs.testDevices : btModel
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
                        onClicked: if (model.Device) model.Connected ? model.Device.disconnectFromDevice() : model.Device.connectToDevice() }
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

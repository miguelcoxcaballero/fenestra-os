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
    property string page: ""            // "" | "wifi" | "bluetooth" | "output" | "project" | "cast"
    onDismissed: { page = ""; batteryOpen = false; tilePage = 0 }
    // Win+P / Win+K open Quick settings straight on that page; the same key again closes it.
    function openPage(name) {
        if (shown && page === name) { close(); return }
        page = name
        if (!shown) open()
    }
    // Tiles come six to a page (3 × 2) with Windows' pager on the right (dark-100 Q, page 2 of 2).
    property int tilePage: 0
    // The battery details above the footer (click on the battery; a second click hides them).
    property bool batteryOpen: false
    // Test hook (tests/shell-kwin): the bench has no battery.
    property var testBattery: null
    readonly property var bat: testBattery || PowerStatus
    function watts(v) { return v.toFixed(1).replace(".", Strings.es ? "," : ".") }
    function duration(s) {
        const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60)
        return (h > 0 ? h + " h " : "") + m + " min"
    }
    // Test hooks (tests/shell-kwin): fake Wi-Fi networks and Bluetooth devices.
    property ListModel testWifi: ListModel {}
    property ListModel testDevices: ListModel {}
    property int testAsk: -1
    property string wifiExpanded: ""     // the network whose row is open (one at a time, as in Windows)
    onVisibleChanged: if (!visible) wifiExpanded = ""
    // BlueZ's device icon (freedesktop name) -> Segoe Fluent Icons glyph, as Windows' Bluetooth list
    function btGlyph(icon) {
        if (icon.startsWith("audio-headset") || icon.startsWith("audio-headphones")) return "\ue7f6"   // Headphone
        if (icon.startsWith("audio")) return "\ue7f5"             // Speakers
        if (icon === "input-mouse") return "\ue962"               // Mouse
        if (icon === "input-keyboard") return "\ue765"            // Keyboard
        if (icon === "input-gaming") return "\ue7fc"              // Game
        if (icon === "input-tablet") return "\uedc6"              // Pen
        if (icon === "phone") return "\ue8ea"                     // CellPhone
        if (icon === "computer") return "\ue7f8"                  // DeviceLaptopNoPic
        if (icon.startsWith("camera")) return "\ue722"            // Camera
        if (icon === "printer") return "\ue749"                   // Print
        return "\ue702"                                           // Bluetooth
    }
    function testFill(networks, devices, portal) {
        testWifi.clear(); testDevices.clear()
        for (let i = 0; i < networks; ++i)
            testWifi.append({ ssid: "Network " + (i + 1), signal: 100 - (i * 7) % 90, active: i === 0, secured: i % 3 !== 2, enterprise: i === 1,
                              connecting: false, portal: i === 0 && !!portal, saved: i < 2, autoConnect: true,
                              identity: i === 1 ? "usuario@alumno.upv.es" : "",
                              status: i === 0 ? (portal ? "Action needed, secured" : "Connected") : i % 3 !== 2 ? "Secured" : "Open" })
        for (let i = 0; i < devices; ++i)
            testDevices.append({ Name: "Device " + (i + 1), Paired: true, Connected: i === 0, Icon: "audio-headphones" })
    }

    // Windows' standard and accent buttons, and its check box, at the network list's size.
    component WifiButton: Rectangle {
        id: wbtn
        property string text
        property bool accent: false
        signal clicked()
        width: Math.max(96, wbl.implicitWidth + 24); height: 32; radius: 4
        color: accent ? (wbm.pressed ? Theme.accentPress : wbm.containsMouse ? Theme.accentHover : Theme.accentFill)
                      : (wbm.pressed ? Theme.pressed : wbm.containsMouse ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(0.98, 0.98, 0.98, 1))
                                                       : (Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : "white"))
        border.color: accent ? "transparent" : Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.1)
        Text { id: wbl; anchors.centerIn: parent; text: wbtn.text; color: wbtn.accent ? Theme.accentOn : Theme.text
               font.family: Metrics.fontFamily; font.pixelSize: 13 }
        MouseArea { id: wbm; anchors.fill: parent; hoverEnabled: true; onClicked: wbtn.clicked() }
    }
    component WifiCheck: Item {
        id: wck
        property string text
        property bool checked: true
        signal toggled()
        width: wckl.x + wckl.implicitWidth; height: 24
        Rectangle {
            width: 20; height: 20; radius: 4; anchors.verticalCenter: parent.verticalCenter
            color: wck.checked ? Theme.accentFill : "transparent"
            border.color: wck.checked ? "transparent" : Theme.textSecondary
            Text { anchors.centerIn: parent; visible: wck.checked; text: "\u2713"; color: Theme.accentOn; font.pixelSize: 13; font.bold: true }
        }
        Text { id: wckl; x: 28; anchors.verticalCenter: parent.verticalCenter; text: wck.text; color: Theme.text
               font.family: Metrics.fontFamily; font.pixelSize: 13 }
        MouseArea { anchors.fill: parent; onClicked: { wck.checked = !wck.checked; wck.toggled() } }
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
        if (page === "cast") Cast.start(); else Cast.stop()
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
            height: (qs.page === "" ? main.height : sub.height) + footerH + 2 + batteryDetails.height
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
                    readonly property int availCount: { let n = 0; for (let i = 0; i < children.length; ++i) if (children[i].avail) ++n; return n }
                    readonly property int pages: Math.max(1, Math.ceil(availCount / 6))
                    onPagesChanged: if (qs.tilePage >= pages) qs.tilePage = pages - 1
                    // a tile is shown when it is available and on the current page
                    function onPage(t) {
                        let k = 0
                        for (let i = 0; i < children.length; ++i) {
                            if (children[i] === t) return Math.floor(k / 6) === qs.tilePage
                            if (children[i].avail) ++k
                        }
                        return false
                    }
                    x: Metrics.n("quick.grid.x", 24); y: Metrics.n("quick.grid.y", 23)
                    columns: 3; columnSpacing: Metrics.n("quick.tile.gap", 12); rowSpacing: 0
                    QuickTile {
                        avail: WifiNetworks.hasWifi || qs.testWifi.count > 0
                        label: NetworkStatus.kind === "wifi" ? NetworkStatus.name : Strings.tr("Wi-Fi")
                        iconName: WifiNetworks.enabled ? "network-wireless-signal-excellent-symbolic" : "network-wireless-disabled-symbolic"
                        glyph: "\ue701"
                        checked: WifiNetworks.enabled; hasPage: true
                        onToggled: WifiNetworks.enabled = !WifiNetworks.enabled
                        onPageRequested: { WifiNetworks.scan(); qs.page = "wifi" }
                    }
                    QuickTile {
                        avail: BluezQt.Manager.adapters.length > 0 || qs.testDevices.count > 0
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
                        avail: PowerProfiles.available || qs.testBattery !== null
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
                    // Cast (Win+K) and Project (Win+P): on every PC, as in Windows; the pages say
                    // what this one can do.
                    QuickTile {
                        // es-ES: the tile says «Proyección inalámbrica», its page «Transmitir»
                        label: Strings.es ? "Proyección inalámbrica" : "Cast"; iconName: "video-display-symbolic"; glyph: "\uec15"
                        link: true; hasPage: true; checked: Cast.active !== "" || (Cast.searching && qs.page === "cast")
                        onPageRequested: qs.page = "cast"
                    }
                    QuickTile {
                        label: Strings.tr("Project"); iconName: "video-display-symbolic"; glyph: "\uebc6"
                        link: true; hasPage: true
                        onPageRequested: { Projection.refresh(); qs.page = "project" }
                    }
                }
                // Windows' pager: ▲ on later pages, a dot per page (the current one larger), ▼ before
                // the last; centred on the tiles, 14.5 px from the right edge (dark-100 Q pages 1 and 2).
                Item {
                    id: pager
                    visible: tiles.pages > 1
                    readonly property color ink: Theme.dark ? Qt.rgba(1, 1, 1, 0.545) : Qt.rgba(0, 0, 0, 0.447)
                    readonly property real cx: parent.width - 12.5
                    readonly property real cy: (main.dividerY - 1) / 2
                    readonly property real dotsTop: cy - (tiles.pages - 1) * 6
                    Canvas {
                        id: upArrow
                        visible: qs.tilePage > 0
                        x: pager.cx - 4; y: pager.dotsTop - 16 - 3; width: 8; height: 6
                        onPaint: { const c = getContext("2d"); c.reset(); c.fillStyle = pager.ink; c.beginPath(); c.moveTo(0, 6); c.lineTo(4, 0); c.lineTo(8, 6); c.closePath(); c.fill() }
                        Connections { target: Theme; function onDarkChanged() { upArrow.requestPaint() } }
                        MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: qs.tilePage = Math.max(0, qs.tilePage - 1) }
                    }
                    Repeater {
                        model: tiles.pages
                        delegate: Rectangle {
                            required property int index
                            readonly property int d: index === qs.tilePage ? 6 : 4
                            x: pager.cx - d / 2; y: pager.dotsTop + index * 12 - d / 2
                            width: d; height: d; radius: d / 2; color: pager.ink
                            MouseArea { anchors.fill: parent; anchors.margins: -4; onClicked: qs.tilePage = index }
                        }
                    }
                    Canvas {
                        id: downArrow
                        visible: qs.tilePage < tiles.pages - 1
                        x: pager.cx - 4; y: pager.dotsTop + (tiles.pages - 1) * 12 + 16 - 3; width: 8; height: 6
                        onPaint: { const c = getContext("2d"); c.reset(); c.fillStyle = pager.ink; c.beginPath(); c.moveTo(0, 0); c.lineTo(8, 0); c.lineTo(4, 6); c.closePath(); c.fill() }
                        Connections { target: Theme; function onDarkChanged() { downArrow.requestPaint() } }
                        MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: qs.tilePage = Math.min(tiles.pages - 1, qs.tilePage + 1) }
                    }
                }
                // The wheel (one notch) or a two-finger scroll on the touchpad over the tiles turns
                // the pages, as in Windows: one page per gesture. A touchpad sends many small
                // deltas, then momentum; they add up to a notch, and after a turn the rest of that
                // gesture is ignored until the events pause.
                WheelHandler {
                    id: tileWheel
                    target: null
                    enabled: tiles.pages > 1
                    property real acc: 0
                    property bool spent: false
                    onWheel: (e) => {
                        const dy = e.angleDelta.y !== 0 ? e.angleDelta.y : e.pixelDelta.y * 2
                        if (tileWheel.point.position.y > main.dividerY) return   // the sliders below
                        if (spent) { gesturePause.restart(); return }
                        if (dy === 0) return
                        if (acc !== 0 && (acc > 0) !== (dy > 0)) acc = 0
                        acc += dy
                        gesturePause.restart(); wheelIdle.restart()
                        if (Math.abs(acc) < 120) return
                        const next = Math.max(0, Math.min(tiles.pages - 1, qs.tilePage + (acc < 0 ? 1 : -1)))
                        acc = 0
                        if (next !== qs.tilePage) { qs.tilePage = next; spent = true }
                    }
                }
                Timer { id: gesturePause; interval: 220; onTriggered: tileWheel.spent = false }
                // a slow high-resolution wheel still adds up to a notch; a long pause starts afresh
                Timer { id: wheelIdle; interval: 1000; onTriggered: tileWheel.acc = 0 }
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
                    Text { id: subTitle; x: 52; anchors.verticalCenter: parent.verticalCenter
                           text: Strings.tr(qs.page === "wifi" ? "Wi-Fi" : qs.page === "bluetooth" ? "Bluetooth" : qs.page === "project" ? "Project"
                                            : qs.page === "cast" ? "Cast" : "Sound output")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
                    // The page's shortcut as key caps (⊞ P, ⊞ K): 16 px squares, 1 px border, 4 px
                    // apart, 8 px after the title (dark-100 Q Cast page).
                    Row {
                        visible: qs.page === "project" || qs.page === "cast"
                        x: subTitle.x + subTitle.implicitWidth + 8; anchors.verticalCenter: parent.verticalCenter
                        spacing: 4
                        component KeyCap: Rectangle {
                            property string label
                            property bool winKey: false
                            width: 16; height: 16; radius: 2; color: "transparent"
                            border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.21) : Qt.rgba(0, 0, 0, 0.204)
                            readonly property color ink: Theme.dark ? Qt.rgba(1, 1, 1, 0.64) : Qt.rgba(0, 0, 0, 0.6)
                            Grid { visible: winKey; x: 3; y: 3; columns: 2; spacing: 1
                                   Repeater { model: 4; Rectangle { width: 4; height: 4; color: parent.parent.ink } } }
                            Text { visible: !winKey; anchors.centerIn: parent; text: label; color: parent.ink
                                   font.family: Metrics.fontFamily; font.pixelSize: 10 }
                        }
                        KeyCap { winKey: true }
                        KeyCap { label: qs.page === "project" ? "P" : "K" }
                    }
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
                        sourceComponent: qs.page === "wifi" ? wifiPage : qs.page === "bluetooth" ? btPage : qs.page === "output" ? outputPage
                                         : qs.page === "project" ? projectPage : qs.page === "cast" ? castPage : null
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
                    visible: qs.page === "wifi" || qs.page === "bluetooth" || qs.page === "project" || qs.page === "cast"
                    x: 8; y: sub.height - sub.footerH + 8; width: footLink.implicitWidth + 24; height: 32
                    radius: Metrics.controlRadius
                    color: flm.pressed ? Theme.pressed : flm.containsMouse ? Theme.hover : "transparent"
                    Text { id: footLink; x: 12; anchors.verticalCenter: parent.verticalCenter
                           text: Strings.tr(qs.page === "wifi" ? "More Wi-Fi settings" : qs.page === "bluetooth" ? "More Bluetooth settings"
                                            : qs.page === "project" ? "More display settings" : "More cast settings")
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: flm; anchors.fill: parent; hoverEnabled: true
                                onClicked: { const target = qs.page === "wifi" ? "wifi" : qs.page === "bluetooth" ? "bluetooth" : "display"
                                             qs.close(); Apps.runCommand("fenestra-settings --page " + target) } }
                }
                // Windows' refresh button at the end of the footer: scans now. The list also rescans by
                // itself every 15 s while this page is open (NetworkManager alone scans only now and then).
                GlyphButton {
                    id: wifiRefresh
                    visible: qs.page === "wifi"
                    x: parent.width - width - 12; y: sub.height - sub.footerH + 8
                    glyph: "view-refresh-symbolic"; fluent: "\ue72c"
                    active: !WifiNetworks.scanning && WifiNetworks.enabled
                    onClicked: WifiNetworks.scan()
                    RotationAnimation on rotation { running: WifiNetworks.scanning && wifiRefresh.visible; from: 0; to: 360; duration: 1000; loops: Animation.Infinite
                                                    onRunningChanged: if (!running) wifiRefresh.rotation = 0 }
                }
                Timer { interval: 15000; repeat: true; running: qs.page === "wifi" && qs.shown && WifiNetworks.enabled; onTriggered: WifiNetworks.scan() }
            }
            // ---- Battery details: same band as the footer, opens upwards from it ----
            Item {
                id: batteryDetails
                x: 1; y: parent.height - 1 - card.footerH - 1 - height
                width: parent.width - 2
                height: qs.batteryOpen && qs.bat.hasBattery ? batteryRows.height + 1 : 0
                clip: true
                Behavior on height { NumberAnimation { duration: 167; easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] } }
                Rectangle { width: parent.width; height: 1; color: Metrics.pcol("panel.divider") }
                Rectangle {
                    y: 1; width: parent.width; height: batteryRows.height
                    color: Metrics.pcol("panel.fill.alt")
                    Column {
                        id: batteryRows
                        width: parent.width
                        topPadding: 8; bottomPadding: 8
                        Repeater {
                            model: {
                                const b = qs.bat, rows = []
                                const rate = qs.watts(b.energyRate)
                                if (b.pluggedIn) {
                                    // No laptop has a meter on the cable: "≈" (PowerStatus.inputWattsEstimate).
                                    const max = b.chargerMaxWatts > 0 ? " / " + Math.round(b.chargerMaxWatts) : ""
                                    if (b.inputWattsEstimate > 0)
                                        rows.push([Strings.tr("Power from the cable"), "≈ " + qs.watts(b.inputWattsEstimate) + max + " W"])
                                    else if (max !== "")
                                        rows.push([Strings.tr("Charger maximum"), Math.round(b.chargerMaxWatts) + " W"])
                                    if (b.charging)
                                        rows.push([Strings.tr("Into the battery"), rate + " W"])
                                } else {
                                    rows.push([Strings.tr("Power use"), rate + " W"])
                                }
                                if (b.charging && b.timeToFull > 0)
                                    rows.push([Strings.tr("Time to full charge"), qs.duration(b.timeToFull)])
                                else if (!b.pluggedIn && b.timeToEmpty > 0)
                                    rows.push([Strings.tr("Time remaining"), qs.duration(b.timeToEmpty)])
                                if (b.healthPercent > 0)
                                    rows.push([Strings.tr("Battery health"), b.healthPercent + (Strings.es ? " %" : "%")])
                                return rows
                            }
                            delegate: Item {
                                required property var modelData
                                width: batteryRows.width; height: 28
                                Text { x: 19; anchors.verticalCenter: parent.verticalCenter; text: parent.modelData[0]
                                       color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                                Text { anchors { right: parent.right; rightMargin: 19; verticalCenter: parent.verticalCenter }
                                       text: parent.modelData[1]
                                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                            }
                        }
                    }
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
                Rectangle {
                    // Hover and press as the footer's other buttons; the icon stays where it was.
                    id: batteryButton
                    x: 11; anchors.verticalCenter: parent.verticalCenter
                    width: batteryRow.width + 16; height: 32
                    radius: Metrics.controlRadius
                    visible: qs.bat.hasBattery
                    color: batteryMouse.pressed ? Theme.pressed : batteryMouse.containsMouse ? Theme.hover : "transparent"
                    Accessible.role: Accessible.Button
                    Accessible.name: Strings.tr("Battery details")
                    Row {
                        id: batteryRow
                        x: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                        // Green while charging, as Windows draws it: the glyph's own fill in dark
                        // mode, the theme's success green over a recoloured glyph in light mode.
                        SymbolicIcon {
                            monochrome: !(qs.bat.charging && Theme.dark)
                            tint: qs.bat.charging ? "#0f7b0f" : Theme.text
                            src: qs.bat.iconSource
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text { text: qs.bat.percentage + (Strings.es ? " %" : "%"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
                               anchors.verticalCenter: parent.verticalCenter }
                        FluentGlyph { glyph: "\ue70e"; fallback: "go-up-symbolic"; size: FluentFont.available ? 10 : 8
                                      rotation: qs.batteryOpen ? 180 : 0; anchors.verticalCenter: parent.verticalCenter
                                      Behavior on rotation { NumberAnimation { duration: 167 } } }
                    }
                    MouseArea { id: batteryMouse; anchors.fill: parent; hoverEnabled: true; onClicked: qs.batteryOpen = !qs.batteryOpen }
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
                // Windows 11: clicking a network only expands it; Connect / Disconnect / Forget are
                // buttons in the expanded row, with "Connect automatically" above Connect.
                delegate: Rectangle {
                    id: row
                    required property int index
                    required property var model
                    readonly property bool expanded: qs.wifiExpanded === model.ssid
                    property bool asking: qs.testAsk === index
                    property bool autoConnect: model.autoConnect !== false
                    readonly property bool saved: !!model.saved
                    readonly property bool signIn: !!model.portal && !asking
                    readonly property int formTop: 52
                    readonly property int buttonsTop: asking ? formTop + (model.enterprise ? 80 : 40)
                                                    : !expanded ? 0
                                                    : model.active || model.connecting ? formTop + (signIn ? 40 : 0)
                                                    : formTop + 36
                    x: 8; width: Metrics.quickWidth - 16; radius: 4
                    height: !expanded && !asking ? (signIn ? 92 : 48) : buttonsTop + 44 + (asking && model.enterprise ? 26 : 0)
                    color: wm.containsMouse || expanded || asking ? Theme.hover : "transparent"
                    Behavior on height { enabled: !Motion.reduced; NumberAnimation { duration: Motion.fadeOpen; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.decelerate } }
                    clip: true
                    SymbolicIcon { monochrome: true; x: 12; y: 16; name: "network-wireless-signal-" + ["none", "weak", "ok", "good", "excellent"][Math.min(4, Math.floor(model.signal / 20))] + "-symbolic" }
                    Column { x: 40; y: 8
                        Text { text: model.ssid; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                        Text { text: model.status; color: Theme.textSecondary
                               font.family: Metrics.fontFamily; font.pixelSize: 12 } }
                    MouseArea { id: wm; width: parent.width; height: 48; hoverEnabled: true
                        onClicked: { if (row.asking) return; qs.wifiExpanded = row.expanded ? "" : model.ssid } }

                    function ask() {
                        qs.wifiExpanded = model.ssid
                        asking = true
                        if (model.enterprise && !user.text && model.identity) user.text = model.identity
                        ;(model.enterprise && !user.text ? user : pw).forceActiveFocus()
                    }
                    function connectNow() {
                        if (WifiNetworks.needsPassword(index)) return ask()
                        WifiNetworks.connectTo(index, "", "", autoConnect)
                    }
                    function submit() {
                        if (pw.text.length === 0 || (model.enterprise && user.text.length === 0)) return
                        WifiNetworks.connectTo(index, pw.text, user.text, autoConnect)
                        pw.text = ""; asking = false
                    }
                    Connections { target: WifiNetworks
                        // wrong key: the password field comes back, the status shows Windows' message
                        function onKeyRejected(ssid) { if (ssid === model.ssid) { pw.text = ""; row.ask() } } }

                    // captive portal: Windows' button under the connected network
                    WifiButton {
                        visible: row.signIn; x: 40; y: 52; accent: true
                        text: Strings.tr("Open browser and connect")
                        onClicked: { qs.close(); WifiNetworks.openPortal() }
                    }
                    // Connect automatically (networks not connected)
                    WifiCheck {
                        visible: row.expanded && !row.asking && !model.active && !model.connecting
                        x: 40; y: row.formTop; checked: row.autoConnect
                        text: Strings.tr("Connect automatically")
                        onToggled: row.autoConnect = checked
                    }
                    // user name and password (enterprise) or the network key
                    Rectangle {
                        visible: row.asking && model.enterprise
                        x: 40; y: row.formTop; width: parent.width - 52; height: 32; radius: 4
                        color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : "white"
                        border.color: user.activeFocus ? Theme.accent : Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.1)
                        TextInput { id: user; x: 10; width: parent.width - 20; anchors.verticalCenter: parent.verticalCenter
                                    color: Theme.text; font.pixelSize: 13; clip: true
                                    Text { visible: !parent.text; text: Strings.tr("User name"); color: Theme.textSecondary; font.pixelSize: 13 }
                                    onAccepted: pw.forceActiveFocus()
                                    KeyNavigation.tab: pw
                                    Keys.onEscapePressed: { pw.text = ""; row.asking = false } }
                    }
                    Rectangle {
                        visible: row.asking
                        x: 40; y: row.formTop + (model.enterprise ? 40 : 0); width: parent.width - 52; height: 32; radius: 4
                        color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : "white"
                        border.color: pw.activeFocus ? Theme.accent : Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.1)
                        TextInput { id: pw; x: 10; width: parent.width - 20; anchors.verticalCenter: parent.verticalCenter
                                    echoMode: TextInput.Password; color: Theme.text; font.pixelSize: 13; clip: true
                                    Text { visible: !parent.text; text: Strings.tr(model.enterprise ? "Password" : "Enter the network security key")
                                           color: Theme.textSecondary; font.pixelSize: 13 }
                                    onAccepted: row.submit()
                                    Keys.onEscapePressed: { text = ""; row.asking = false } }
                    }
                    // the row of buttons, right aligned as in Windows
                    Item {
                        visible: row.expanded || row.asking
                        x: 40; y: row.buttonsTop; width: parent.width - 52; height: 32
                        Text {
                            visible: model.active && !row.asking
                            anchors.verticalCenter: parent.verticalCenter
                            text: Strings.tr("Properties"); color: Theme.accentText; font.family: Metrics.fontFamily; font.pixelSize: 13
                            MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                                        onClicked: { qs.close(); Apps.runCommand("fenestra-settings --page wifi") } }
                        }
                        Text {
                            visible: row.asking && model.enterprise
                            y: 42
                            text: Strings.tr("Advanced options"); color: Theme.accentText; font.family: Metrics.fontFamily; font.pixelSize: 12
                            MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                                        onClicked: { qs.close(); Apps.runCommand("fenestra-settings --page wifi") } }
                        }
                        Row {
                            anchors.right: parent.right; spacing: 8
                            WifiButton {   // forget: saved networks, not while asking for a key
                                visible: row.saved && !row.asking && !model.connecting
                                text: Strings.tr("Forget")
                                onClicked: { WifiNetworks.forget(index); qs.wifiExpanded = "" }
                            }
                            WifiButton {
                                visible: !row.asking
                                accent: !model.active && !model.connecting
                                text: Strings.tr(model.active ? "Disconnect" : model.connecting ? "Cancel" : "Connect")
                                onClicked: model.active ? WifiNetworks.disconnectFrom(index)
                                           : model.connecting ? WifiNetworks.cancel(index) : row.connectNow()
                            }
                            WifiButton { visible: row.asking; accent: true; text: Strings.tr("Next"); onClicked: row.submit() }
                            WifiButton { visible: row.asking; text: Strings.tr("Cancel"); onClicked: { pw.text = ""; row.asking = false } }
                        }
                    }
                }
            }
            Text { visible: qs.testWifi.count === 0 && WifiNetworks.count === 0; x: 20; text: Strings.tr("No networks found"); color: Theme.textSecondary
                   font.family: Metrics.fontFamily; font.pixelSize: 12 }
        }
    }
    // ---- Project (Win+P): the four display modes, the current one selected ----
    Component {
        id: projectPage
        Column {
            width: Metrics.quickWidth
            Repeater {
                model: [["pc", "PC screen only"], ["duplicate", "Duplicate"], ["extend", "Extend"], ["second", "Second screen only"]]
                delegate: Rectangle {
                    id: prow
                    required property var modelData
                    readonly property bool current: Projection.mode === modelData[0]
                    x: 8; width: Metrics.quickWidth - 16; height: 48; radius: 4
                    color: pm.pressed ? Theme.pressed : pm.containsMouse || current ? Theme.hover : "transparent"
                    // the selected mode: Fluent's selection pill
                    Rectangle { visible: prow.current; x: 0; width: 3; height: 16; radius: 1.5; anchors.verticalCenter: parent.verticalCenter
                                color: Theme.accentFill }
                    // two screens drawn as Windows' projection pictograms: filled = showing the desktop
                    Item {
                        x: 12; width: 20; height: 16; anchors.verticalCenter: parent.verticalCenter
                        readonly property color ink: Theme.text
                        readonly property string m: prow.modelData[0]
                        component Screen: Rectangle { property bool lit; width: 9; height: 7; radius: 1; border.width: 1; border.color: parent.ink
                                                      color: lit ? parent.ink : "transparent" }
                        Screen { visible: parent.m !== "extend"; x: 0; y: 4; lit: parent.m !== "second" }
                        Screen { visible: parent.m !== "extend"; x: 11; y: 4; lit: parent.m !== "pc" }
                        Rectangle { visible: parent.m === "extend"; x: 0; y: 4; width: 20; height: 7; radius: 1; color: parent.ink }
                        Rectangle { visible: parent.m === "extend"; x: 9.5; y: 4; width: 1; height: 7; color: Theme.dark ? "#2c2c2c" : "#f3f3f3" }
                        Rectangle { x: 3; y: 12; width: 3; height: 1; color: parent.ink }
                        Rectangle { x: 14; y: 12; width: 3; height: 1; color: parent.ink }
                    }
                    Text { x: 44; anchors.verticalCenter: parent.verticalCenter; text: Strings.tr(prow.modelData[1])
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true; enabled: !Projection.busy
                                onClicked: Projection.setMode(prow.modelData[0]) }
                }
            }
        }
    }
    // ---- Cast (Win+K): wireless displays nearby, or what Windows says on a PC that cannot cast ----
    Component {
        id: castPage
        Item {
            width: Metrics.quickWidth
            height: Cast.supported ? castList.height : noCast.height
            // No Miracast (no Wi-Fi Direct) and no Avahi: Windows' "Connect a cable" text
            // (dark-100 Q Cast page: 20 px semibold title 51 px under the header, then the body).
            Column {
                id: noCast
                visible: !Cast.supported
                x: 24; y: 51 - 56 + 6; width: Metrics.quickWidth - 48; spacing: 12
                Text { width: parent.width; wrapMode: Text.WordWrap; text: Strings.tr("Connect a cable to cast")
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold }
                Text { width: parent.width; wrapMode: Text.WordWrap; lineHeight: 19; lineHeightMode: Text.FixedHeight
                       text: Strings.tr("This device doesn't support Miracast, so you'll need to connect an external display with a cable.")
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
            }
            Column {
                id: castList
                visible: Cast.supported
                width: Metrics.quickWidth
                Repeater {
                    model: Cast.devices
                    // a display being cast to grows a second line with Disconnect, as in Windows
                    delegate: Rectangle {
                        id: crow
                        required property var modelData
                        readonly property bool current: modelData.id === Cast.active
                        x: 8; width: Metrics.quickWidth - 16; height: current ? 92 : 48; radius: 4
                        color: current ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.037))
                             : cm2.pressed ? Theme.pressed : cm2.containsMouse ? Theme.hover : "transparent"
                        FluentGlyph { x: 12; y: 24 - height / 2; glyph: modelData.kind === "chromecast" ? "\uec15" : "\ue7f4"
                                      fallback: "video-display-symbolic" }
                        Column { x: 40; y: 24 - height / 2; width: parent.width - 52
                            Text { width: parent.width; elide: Text.ElideRight; text: modelData.name
                                   color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                            Text { width: parent.width; elide: Text.ElideRight
                                   text: !crow.current ? Strings.tr(modelData.kind === "chromecast" ? "Chromecast" : "Wireless display")
                                       : Cast.activeState === "connected" ? Strings.tr("Connected")
                                       : Cast.activeState === "error" ? Strings.tr("Couldn't connect")
                                       : Strings.tr("Connecting") + ".".repeat(dots.n)
                                   color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 } }
                        MouseArea { id: cm2; anchors.fill: parent; hoverEnabled: true; enabled: !crow.current
                                    onClicked: Cast.connectTo(crow.modelData.id) }
                        WifiButton {
                            visible: crow.current
                            anchors.right: parent.right; anchors.rightMargin: 12; y: 48
                            text: Strings.tr("Disconnect"); onClicked: Cast.disconnect()
                        }
                    }
                }
                // while nothing is found: Windows' "Searching for devices" line
                Item {
                    visible: Cast.devices.length === 0
                    width: parent.width; height: 48
                    Text { id: searching; x: 20; anchors.verticalCenter: parent.verticalCenter
                           text: Strings.tr("Searching for devices") + ".".repeat(dots.n)
                           color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    Timer { id: dots; property int n: 0; interval: 500; repeat: true
                            running: (parent.visible || Cast.activeState === "connecting") && qs.shown
                            onTriggered: n = (n + 1) % 4 }
                }
            }
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
                    // Windows draws each kind with its Fluent glyph, in the text colour
                    FluentGlyph { x: 12; anchors.verticalCenter: parent.verticalCenter
                                  glyph: qs.btGlyph(model.Icon || ""); fallback: model.Icon || "bluetooth-active-symbolic" }
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

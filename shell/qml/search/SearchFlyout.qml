// SPDX-License-Identifier: GPL-3.0-or-later
// Search, the 2025 layout of the user's Windows 11 (reference-shots/user-win11 160049 and 160127
// at 150 %; logical px from the panel's outer top-left, search.* tokens): the same 834 x 866
// panel as Start (no header band), the search field on top.
// Empty query: "Recent searches", the apps opened from Search (40 px tile with the 24 px icon,
// name, "App", how long ago, right-aligned), 60 px apart; account and settings buttons on the right.
// Typing: back button and filter chips (All in the accent colour), "Best match" (56 px row, selected,
// accent bar) and the other sections (40 px tiles, 62 px rows) in a 328.67 px column, and the
// preview pane (424 x 720): name, kind, a card with the 64 px icon, Open and Options ˅, Details
// (Location, Last modified).
import QtQuick
import Fenestra.Shell

ShellPopup {
    id: search
    panelWidth: Metrics.searchWidth
    panelHeight: targetScreen ? Math.min(Metrics.searchHeight, targetScreen.height - Metrics.taskbarHeight - Metrics.flyoutGap
                                                               - Metrics.tok("start.margin.top", 47)) : Metrics.searchHeight
    // Opened from the taskbar's icon (or Start), Search sits where Start does; with the taskbar's
    // search box, at the box.
    useAnchor: ShellSettings.searchMode === "box"
    property int selected: 0
    readonly property var flat: {
        const out = []
        for (const s of Search.sections) for (const i of s.items) out.push(i)
        return out
    }
    readonly property var current: flat.length ? flat[Math.min(selected, flat.length - 1)] : null
    readonly property bool typing: field.text.trim() !== ""
    readonly property real fieldX: Metrics.num("search.field.x", 33.33)

    function openWith(text) {
        Search.filter = "all"
        Search.text = text
        field.text = text
        selected = 0
        open()
        Search.prepare()
        field.input.forceActiveFocus()
        field.input.cursorPosition = field.text.length
    }
    onClosed: { Usage.rememberQuery(field.text); field.text = ""; Search.text = "" }
    Connections { target: Search; function onActivated() { search.close() } }

    component Label: Text {
        property real bl
        y: bl - baselineOffset
        color: Theme.text
        font.family: Metrics.fontFamily; font.variableAxes: Metrics.textAxes; font.pixelSize: Metrics.fontCaption
    }
    component Secondary: Label { color: Metrics.themed("popup.text.secondary") }
    component GlyphButton: Rectangle {
        id: gb
        property string glyph
        property string fallback
        property real glyphSize: 16
        signal clicked()
        width: 32; height: 32; radius: Metrics.controlRadius
        color: gbm.pressed ? Metrics.themed("popup.pressed") : gbm.containsMouse ? Metrics.themed("popup.hover") : "transparent"
        FluentGlyph { anchors.centerIn: parent; size: gb.glyphSize; glyph: gb.glyph; fallback: gb.fallback }
        MouseArea { id: gbm; anchors.fill: parent; hoverEnabled: true; onClicked: gb.clicked() }
    }
    // 40 px tile: white 7 %, the 24 px icon (or a glyph) centred.
    component Tile: Rectangle {
        id: tile
        property string icon
        property string iconSource
        property string glyph
        width: 40; height: 40; radius: Metrics.controlRadius
        color: Metrics.themed("search.tile.fill")
        Image { visible: tile.glyph === ""; anchors.centerIn: parent; width: 24; height: 24; sourceSize: Qt.size(48, 48)
                fillMode: Image.PreserveAspectFit
                source: tile.glyph !== "" ? "" : tile.iconSource !== "" ? tile.iconSource : "image://icon/" + tile.icon }
        FluentGlyph { visible: tile.glyph !== ""; anchors.centerIn: parent; size: 20; glyph: tile.glyph
                      fallback: Metrics.assets + "search/search-glyph.svg" }
    }

    SearchBox {
        id: field
        x: search.fieldX; y: Metrics.num("search.field.y", 17.33)
        width: search.panelWidth - 2 * search.fieldX
        editable: true
        onTextChanged: { Search.text = field.text; search.selected = 0 }
        onDownPressed: search.selected = Math.min(search.selected + 1, search.flat.length - 1)
        onUpPressed: search.selected = Math.max(search.selected - 1, 0)
        onAccepted: if (search.current) Search.activate(search.current)
        onEscapePressed: search.close()
    }
    // Account and Search settings, top right on both pages.
    GlyphButton {
        x: Metrics.num("search.button1.x", 747.33) - width / 2; y: Metrics.num("search.buttons.y", 82.67) - height / 2
        glyph: "\ued15"; fallback: Metrics.assets + "power/7.svg"
        Accessible.name: Strings.tr("Change account settings")
        onClicked: { search.close(); Apps.runCommand("fenestra-settings --page yourinfo") }
    }
    GlyphButton {
        x: Metrics.num("search.button2.x", 791.33) - width / 2; y: Metrics.num("search.buttons.y", 82.67) - height / 2
        glyph: "\ue713"; fallback: Metrics.assets + "menu-icons/win11-settings.svg"
        Accessible.name: Strings.tr("Search settings")
        onClicked: { search.close(); Apps.runCommand("fenestra-settings --page fx-search") }
    }

    // ---- Empty query: Recent searches ---------------------------------------------------------
    Item {
        id: home
        visible: !search.typing
        anchors.fill: parent
        readonly property var entries: Usage.recentSearches.filter(e => e.kind === "app")
        Label { x: Metrics.num("search.title.x", 35.33) - 1; bl: Metrics.num("search.title.baseline", 87.67)
                text: Strings.tr("Recent searches"); font.pixelSize: Metrics.tok("search.title.size", 18); font.weight: Font.DemiBold }
        Secondary {
            visible: home.entries.length === 0
            x: Metrics.num("search.title.x", 35.33); bl: Metrics.num("search.recent.name.baseline", 134.67)
            text: Strings.tr("Your recent searches will appear here."); font.pixelSize: Metrics.fontBody
        }
        Flickable {
            x: Metrics.num("search.recent.x", 34.67) - 8
            y: Metrics.num("search.recent.y", 116.67) - 10
            width: Metrics.num("search.field.right", 801.33) - x + 8
            height: search.panelHeight - y - 16
            contentHeight: recentColumn.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: recentColumn
                width: parent.width
                Repeater {
                    model: home.entries
                    delegate: Item {
                        id: rr
                        required property var modelData
                        width: recentColumn.width; height: Metrics.num("search.recent.pitch", 60)
                        Rectangle { anchors.fill: parent; anchors.topMargin: 2; anchors.bottomMargin: 2; radius: Metrics.controlRadius
                                    color: rrm.pressed ? Metrics.themed("popup.pressed") : rrm.containsMouse ? Metrics.themed("popup.hover") : "transparent" }
                        Tile { x: 8; y: 10; icon: rr.modelData.icon }
                        Label { x: 8 + Metrics.num("search.recent.text.x", 86.67) - Metrics.num("search.recent.x", 34.67) - 1
                                bl: 10 + Metrics.num("search.recent.name.baseline", 134.67) - Metrics.num("search.recent.y", 116.67)
                                width: parent.width - x - 120; elide: Text.ElideRight
                                text: rr.modelData.name; font.pixelSize: Metrics.fontBody }
                        Secondary { x: 8 + Metrics.num("search.recent.text.x", 86.67) - Metrics.num("search.recent.x", 34.67) - 1
                                    bl: 10 + Metrics.num("search.recent.kind.baseline", 151.33) - Metrics.num("search.recent.y", 116.67)
                                    text: Strings.tr(rr.modelData.system ? "System" : "App") }
                        Secondary { x: parent.width - 8 - width
                                    bl: 10 + Metrics.num("search.recent.age.baseline", 140.67) - Metrics.num("search.recent.y", 116.67)
                                    text: rr.modelData.age }
                        MouseArea { id: rrm; anchors.fill: parent; hoverEnabled: true
                                    // rememberApp reorders the list and this row goes away with its scope: close first.
                                    onClicked: { const app = rr.modelData.value; search.close(); Apps.launch(app); Usage.rememberApp(app) } }
                    }
                }
            }
        }
    }

    // ---- Typing: chips, results, preview -------------------------------------------------------
    Item {
        id: query
        visible: search.typing
        anchors.fill: parent
        GlyphButton {
            x: Metrics.num("search.back.x", 39.33) - width / 2; y: Metrics.num("search.buttons.y", 82.67) - height / 2
            glyph: "\ue830"; fallback: Metrics.assets + "menu-icons/win11-explorer-back.svg"
            Accessible.name: Strings.tr("Back")
            onClicked: { field.text = ""; field.input.forceActiveFocus() }
        }
        Row {
            id: chips
            x: Metrics.num("search.chips.x", 64.67); y: Metrics.num("search.chips.y", 67.33)
            spacing: Metrics.num("search.chips.gap", 4)
            Repeater {
                model: [["all", "All"], ["web", "Web"], ["apps", "Apps"], ["files", "Documents"], ["settings", "Settings"], ["folders", "Folders"], ["photos", "Photos"]]
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool on: Search.filter === modelData[0]
                    width: chipText.implicitWidth + 2 * Metrics.num("search.chip.padding", 11.67); height: Metrics.num("search.chip.height", 31.33)
                    radius: height / 2
                    color: on ? Theme.accentFill : chipMouse.pressed ? Metrics.themed("popup.pressed")
                         : chipMouse.containsMouse ? Metrics.themed("search.chip.hover") : Metrics.themed("search.chip.fill")
                    border.width: on ? 0 : field.border.width
                    border.color: Metrics.themed("search.chip.border")
                    Text { id: chipText; anchors.horizontalCenter: parent.horizontalCenter
                           y: Metrics.num("search.chip.baseline", 20.67) - baselineOffset
                           text: Strings.tr(modelData[1]); color: parent.on ? Theme.accentOn : Theme.text
                           font.family: Metrics.fontFamily; font.variableAxes: Metrics.textAxes; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: chipMouse; anchors.fill: parent; hoverEnabled: true
                                onClicked: { Search.filter = modelData[0]; search.selected = 0; field.input.forceActiveFocus() } }
                }
            }
        }
        // More filters (Windows' ▶): the next filter.
        GlyphButton {
            x: chips.x + chips.width + Metrics.num("search.chips.more.gap", 27.33) - 11.67
            y: Metrics.num("search.buttons.y", 82.67) - height / 2; width: 24
            glyphSize: Metrics.num("search.chips.more.size", 10.67); glyph: "\uedda"; fallback: Metrics.assets + "menu-icons/win11-chevron-right.svg"
            onClicked: {
                const f = ["all", "web", "apps", "files", "settings", "folders", "photos"]
                Search.filter = f[(f.indexOf(Search.filter) + 1) % f.length]; field.input.forceActiveFocus()
            }
        }

        Flickable {
            id: results
            x: Metrics.num("search.results.x", 26.67); y: Metrics.num("search.results.y", 112)
            width: Metrics.num("search.results.width", 328.67); height: search.panelHeight - y - 16
            contentHeight: resultColumn.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // Panel coordinates -> this column's.
            function rx(v) { return v - x }
            function ry(v) { return v - y }
            Column {
                id: resultColumn
                width: parent.width
                Repeater {
                    model: Search.sections
                    delegate: Column {
                        id: section
                        required property var modelData
                        required property int index
                        readonly property bool best: index === 0 && Search.best && Object.keys(Search.best).length > 0
                        width: parent.width
                        // Title row: "Best match" (bl 34.67 below the column's top), others
                        // 28.67 below the previous row, with a › on the right.
                        Item {
                            width: parent.width
                            height: section.best ? Metrics.num("search.best.y", 162.67) - Metrics.num("search.results.y", 112)
                                                 : Metrics.num("search.section.height", 48)
                            Label { x: results.rx(section.best ? Metrics.num("search.best.title.x", 32) : Metrics.num("search.section.title.x", 35.33)) - 1
                                    bl: section.best ? Metrics.num("search.best.title.baseline", 146.67) - Metrics.num("search.results.y", 112)
                                                           : Metrics.num("search.section.baseline", 28.67)
                                    text: section.modelData.title; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
                            FluentGlyph { visible: !section.best; x: results.rx(Metrics.num("search.section.chevron.x", 336)); size: 12
                                          y: Metrics.num("search.section.baseline", 28.67) - 10
                                          glyph: "\ue76c"; fallback: Metrics.assets + "menu-icons/win11-chevron-right.svg" }
                        }
                        Repeater {
                            model: section.modelData.items
                            delegate: Item {
                                id: row
                                required property var modelData
                                readonly property bool isCurrent: search.current && JSON.stringify(search.current) === JSON.stringify(modelData)
                                readonly property bool web: modelData.kind === "web"
                                width: parent.width
                                height: section.best ? Metrics.num("search.best.height", 56) : Metrics.num("search.row.pitch", 62)
                                Rectangle {
                                    // Best match: the whole 56 px row; other rows: 4 px around the tile row.
                                    y: section.best ? 0 : Metrics.num("search.row.tile.y", 8) - 8
                                    width: parent.width; height: section.best ? parent.height : 56
                                    radius: Metrics.controlRadius
                                    color: row.isCurrent ? Metrics.themed("search.result.selected")
                                         : rmouse.pressed ? Metrics.themed("popup.pressed")
                                         : rmouse.containsMouse ? Metrics.themed("popup.hover") : "transparent"
                                    Rectangle { visible: row.isCurrent; y: (parent.height - height) / 2; width: Metrics.num("search.indicator.width", 2.67)
                                                height: 16; radius: width / 2; color: Theme.accentFill }
                                }
                                Tile {
                                    x: section.best ? 8 : Metrics.num("search.row.tile.x", 36.67) - results.x
                                    y: 8
                                    icon: row.modelData.icon || ""; iconSource: row.modelData.iconSource || ""
                                    glyph: row.web ? "\ue721" : ""
                                }
                                Label { x: Metrics.num("search.row.text.x", 89.33) - results.x - 1; width: parent.width - x - 12; elide: Text.ElideRight
                                        bl: 8 + (section.best ? Metrics.num("search.best.name.baseline", 16) : Metrics.num("search.row.name.baseline", 18))
                                        text: search.displayTitle(row.modelData); font.pixelSize: Metrics.fontBody }
                                Secondary { x: Metrics.num("search.row.text.x", 89.33) - results.x - 1; width: parent.width - x - 12; elide: Text.ElideRight
                                            bl: 8 + (section.best ? Metrics.num("search.best.sub.baseline", 35.33) : Metrics.num("search.row.sub.baseline", 34.67))
                                            text: search.subtitle(row.modelData, section.best) }
                                MouseArea { id: rmouse; anchors.fill: parent; hoverEnabled: true
                                    onClicked: { search.selected = search.flat.findIndex(i => JSON.stringify(i) === JSON.stringify(row.modelData)); Search.activate(row.modelData) } }
                            }
                        }
                    }
                }
                Secondary {
                    visible: Search.sections.length === 0
                    x: 6; bl: 34.67
                    text: Search.indexing ? Strings.tr("Searching…") : Strings.tr("No results"); font.pixelSize: Metrics.fontBody
                }
            }
        }

        // Preview pane.
        Rectangle {
            id: pane
            visible: search.current !== null
            x: Metrics.num("search.preview.x", 376.67); y: Metrics.num("search.preview.y", 120.67)
            width: search.panelWidth - Metrics.num("search.preview.right", 33.33) - x
            height: search.panelHeight - Metrics.num("search.preview.bottom", 25.33) - y
            radius: Metrics.flyoutRadius
            color: Metrics.themed("search.preview.fill")
            readonly property real pad: Metrics.num("search.preview.padding", 24.67)
            readonly property var item: search.current
            Label { x: pane.pad - 1; width: parent.width - 2 * pane.pad; elide: Text.ElideRight
                    bl: Metrics.num("search.preview.name.baseline", 39.33)
                    text: pane.item ? search.displayTitle(pane.item) : ""
                    font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
            Secondary { x: pane.pad - 1; bl: Metrics.num("search.preview.kind.baseline", 58.67)
                        text: pane.item ? search.kindName(pane.item) : "" }
            Rectangle {
                id: card
                x: Metrics.num("search.preview.card.x", 24); y: Metrics.num("search.preview.card.y", 76)
                width: parent.width - 2 * x; height: Metrics.num("search.preview.card.height", 109.33)
                radius: Metrics.controlRadius
                color: Metrics.themed("search.preview.card.fill")
                border.width: field.border.width; border.color: Metrics.themed("search.preview.card.border")
                Image {
                    anchors.centerIn: parent
                    width: 64; height: 64
                    sourceSize: Qt.size(128, 128)
                    fillMode: pane.item && pane.item.kind === "photo" ? Image.PreserveAspectCrop : Image.PreserveAspectFit
                    source: pane.item ? (pane.item.iconSource ? pane.item.iconSource : "image://icon/" + pane.item.icon) : ""
                }
            }
            // Open | Options ˅
            Row {
                x: Metrics.num("search.preview.buttons.x", 22.67); y: Metrics.num("search.preview.buttons.y", 200)
                spacing: Metrics.num("search.preview.buttons.gap", 3.33)
                PaneButton { text: Strings.tr(pane.item && pane.item.kind === "web" ? "Open results in browser" : "Open")
                             onClicked: if (pane.item) Search.activate(pane.item) }
                PaneButton { id: optionsButton; text: Strings.tr("Options"); chevron: true
                             onClicked: search.openOptions(optionsButton) }
            }
            Item {
                id: details
                visible: pane.item && pane.item.path !== undefined
                x: pane.pad - 1; width: parent.width - 2 * pane.pad; height: 1
                Label { bl: Metrics.num("search.preview.details.baseline", 265.33); text: Strings.tr("Details")
                        font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
            }
            Repeater {
                model: details.visible ? [["Location", pane.item.path ? pane.item.path.replace(/\/[^\/]*$/, "") : (pane.item.subtitle || "")],
                                          ["Last modified", pane.item.modified ? Qt.formatDateTime(pane.item.modified, "dd/MM/yyyy, HH:mm") : ""]] : []
                delegate: Item {
                    required property var modelData
                    required property int index
                    width: pane.width; height: 1
                    Secondary { x: pane.pad - 1; bl: Metrics.num("search.preview.row.baseline", 301.33) + index * Metrics.num("search.preview.row.pitch", 40)
                                text: Strings.tr(modelData[0]); font.pixelSize: Metrics.fontBody }
                    Label { x: Metrics.num("search.preview.value.x", 148) - 1; width: pane.width - x - pane.pad; elide: Text.ElideMiddle
                            bl: Metrics.num("search.preview.row.baseline", 301.33) + index * Metrics.num("search.preview.row.pitch", 40)
                            text: modelData[1]; font.pixelSize: Metrics.fontBody }
                }
            }
        }
    }
    // Open / Options: 120 x 32 subtle buttons (white 6 % with a lighter edge).
    component PaneButton: Rectangle {
        id: pb
        property string text
        property bool chevron: false
        signal clicked()
        width: Metrics.num("search.preview.button.width", 122.67); height: Metrics.num("search.preview.button.height", 34.67)
        radius: Metrics.controlRadius
        color: pbm.pressed ? Metrics.themed("search.button.pressed") : pbm.containsMouse ? Metrics.themed("search.button.hover") : Metrics.themed("search.button.fill")
        border.width: field.border.width; border.color: Metrics.themed("search.button.border")
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 10
            Text { id: pbText; y: Metrics.num("search.preview.button.baseline", 23.33) - baselineOffset; text: pb.text; color: Theme.text
                   font.family: Metrics.fontFamily; font.variableAxes: Metrics.textAxes; font.pixelSize: Metrics.fontBody }
            FluentGlyph { visible: pb.chevron; size: 12; y: pbText.y + pbText.baselineOffset - 10
                          glyph: "\ue70d"; fallback: Metrics.assets + "menu-icons/win11-chevron-down.svg" }
        }
        MouseArea { id: pbm; anchors.fill: parent; hoverEnabled: true; onClicked: pb.clicked() }
    }
    function openOptions(button) {
        const it = current
        if (!it) return
        optionsMenu.items = actionsFor(it).slice(1)
        const p = button.mapToItem(search.panel, 0, button.height)
        optionsMenu.anchorLeft = search.screenX + p.x
        optionsMenu.gap = Metrics.flyoutGap + search.panelHeight - p.y - optionsMenu.sheetHeight - 4
        optionsMenu.open()
    }
    ContextMenu { id: optionsMenu; targetScreen: search.targetScreen; overPanel: true; overWindow: search; overRect: search.screenRect; onDismissed: search.requestActivate() }

    // Files as Explorer names them with known extensions hidden.
    function extension(item) {
        const m = (item.kind === "file" || item.kind === "photo") && item.title ? item.title.match(/\.([^.\/]+)$/) : null
        return m ? m[1] : ""
    }
    function displayTitle(item) { return item.title }
    function kindName(item) {
        const ext = extension(item).toLowerCase()
        if (ext === "txt") return Strings.tr("Text Document")
        if (ext) return ext.toUpperCase()
        const kind = item.kind
        return Strings.tr({ app: "App", setting: "System settings", file: "Document", folder: "File folder", photo: "Photo", web: "Web" }[kind] || "")
    }
    // Best match: "<kind> · Last modified <age>"; other rows: their subtitle.
    function subtitle(item, best) {
        if (item.kind === "web") return item.subtitle
        if (!best || !item.modified) return item.kind === "app" ? Strings.tr("App") : item.subtitle
        const ext = extension(item).toUpperCase()
        const kind = ext ? Strings.tr("%1 File").arg(ext) : kindName(item)
        return kind + " · " + Strings.tr("Last modified") + " " + Usage.ageText(new Date(item.modified).getTime())
    }
    function actionsFor(item) {
        const a = [{ text: Strings.tr(item.kind === "web" ? "Open results in browser" : "Open"), iconSource: Metrics.assets + "menu-icons/win11-menu-openinnewwindow.svg", action: () => Search.activate(item) }]
        if (item.kind === "app") {
            const pinned = StartPins.isPinned(item.id)
            a.push({ text: Strings.tr(pinned ? "Unpin from Start" : "Pin to Start"), iconSource: Metrics.assets + "menu-icons/win11-explorer-pin.svg",
                     action: () => pinned ? StartPins.unpin(item.id) : StartPins.pin(item.id) })
        }
        if (item.path !== undefined) {
            a.push({ text: Strings.tr("Open file location"), iconSource: Metrics.assets + "menu-icons/win11-menu-folderopen.svg", action: () => Search.activate(item, "location") })
            a.push({ text: Strings.tr("Copy full path"), iconSource: Metrics.assets + "menu-icons/win11-menu-copypath.svg", action: () => Search.copyPath(item) })
        }
        return a
    }
}

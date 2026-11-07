// SPDX-License-Identifier: GPL-3.0-or-later
// Search (S04, S05) as measured on the reference (search.* in design/tokens.json, scale 1):
// 776 × 726, left edge on the taskbar's search box. With the box on the taskbar the box is the
// entry (the text typed here shows there); otherwise an entry heads the flyout.
// Home: Suggested (46 px rows) | Quick searches (chips of Settings pages) and Top apps (3 × 2 tiles).
// Typing: back button and filter chips, results (325 px) with a preview pane (386 px).
import QtQuick
import Fenestra.Shell

ShellPopup {
    id: search
    width: Metrics.searchWidth; height: Metrics.searchHeight
    openOffset: 0; openDuration: Motion.searchFade
    property int selected: 0
    readonly property var flat: {
        const out = []
        for (const s of Search.sections) for (const i of s.items) out.push(i)
        return out
    }
    readonly property var current: flat.length ? flat[Math.min(selected, flat.length - 1)] : null
    readonly property bool typing: entry.text.trim() !== ""
    // The flyout's own entry when the taskbar has no search box.
    readonly property bool ownEntry: ShellSettings.searchMode !== "box"
    readonly property int top: ownEntry ? 56 : 0
    readonly property int colX: Metrics.tok("search.column.x", 26)
    readonly property int rightX: Metrics.tok("search.right.x", 330)
    readonly property int rightWidth: width - rightX - 25

    function openWith(text) {
        Search.filter = "all"
        Search.text = text
        entry.text = text
        selected = 0
        open()
        Search.prepare()
        entry.forceActiveFocus()
        entry.cursorPosition = entry.text.length
    }
    onClosed: { Usage.rememberQuery(entry.text); entry.text = ""; Search.text = "" }
    Connections { target: Search; function onActivated() { search.close() } }

    // ---- Entry (shown only without the taskbar's box) -------------------------------------------
    Rectangle {
        id: entryBox
        x: 24; y: 16; width: parent.width - 48; height: 32
        // Kept (transparent) without its box: the entry still takes the keys.
        opacity: search.ownEntry ? 1 : 0
        radius: 16
        color: Metrics.themed("start.search.fill")
        border.color: Metrics.themed("start.search.border")
        Image { x: 16; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
                sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
                source: ShellSettings.searchIcon !== "" ? ShellSettings.searchIcon : Metrics.assets + "search/search.svg" }
        TextInput {
            id: entry
            x: 44; width: parent.width - 58
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.text
            selectionColor: Theme.accentFill; selectedTextColor: Theme.accentOn
            font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
            clip: true
            onTextChanged: { Search.text = text; search.selected = 0 }
            Keys.onDownPressed: search.selected = Math.min(search.selected + 1, search.flat.length - 1)
            Keys.onUpPressed: search.selected = Math.max(search.selected - 1, 0)
            Keys.onReturnPressed: if (search.current) Search.activate(search.current)
            Keys.onEnterPressed: if (search.current) Search.activate(search.current)
            Keys.onEscapePressed: search.close()
        }
    }

    component Heading: Text {
        color: Theme.text
        font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold
    }
    // "…" (more options) at the top right of both pages.
    component MoreButton: Rectangle {
        width: 32; height: 32; radius: Metrics.controlRadius
        color: moreMouse.containsMouse ? Metrics.themed("start.hover") : "transparent"
        Row {
            anchors.centerIn: parent; spacing: 2.5
            Repeater { model: 3; Rectangle { width: 3; height: 3; radius: 1.5; color: Theme.text } }
        }
        MouseArea { id: moreMouse; anchors.fill: parent; hoverEnabled: true; onClicked: Apps.runCommand("fenestra-settings --page fx-search") }
    }

    // ---- Home: Suggested | Quick searches, Top apps ---------------------------------------------
    Item {
        id: home
        visible: !search.typing
        y: search.top; width: parent.width; height: parent.height - y
        readonly property int headY: Metrics.tok("search.header.y", 29)
        readonly property var topApps: Usage.topApps(6)
        readonly property var suggested: {
            const out = Usage.recentSearches.slice(0, 11)
            const seen = topApps.map(a => a.storageId)
            for (const a of Usage.topApps(17))
                if (out.length < 11 && seen.indexOf(a.storageId) < 0)
                    out.push({ kind: "app", value: a.storageId, name: a.name, icon: a.icon })
            return out
        }
        Heading { x: search.colX; y: home.headY; text: Strings.tr("Suggested") }
        Column {
            x: search.colX; y: Metrics.tok("search.rows.y", 59)
            width: search.rightX - search.colX - 16
            Repeater {
                model: home.suggested
                delegate: Rectangle {
                    required property var modelData
                    width: parent.width; height: Metrics.tok("search.row", 46); radius: Metrics.controlRadius
                    color: hm.containsMouse ? Metrics.themed("start.hover") : "transparent"
                    readonly property int iconSize: Metrics.tok("search.row.icon", 24)
                    Image { x: 10; anchors.verticalCenter: parent.verticalCenter; width: parent.iconSize; height: width
                            sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                            source: modelData.kind === "query" ? Metrics.assets + "search/search.svg" : "image://icon/" + modelData.icon }
                    Text { x: Metrics.tok("search.row.text.x", 70) - search.colX; anchors.verticalCenter: parent.verticalCenter
                           width: parent.width - x - 8; elide: Text.ElideRight
                           text: modelData.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: hm; anchors.fill: parent; hoverEnabled: true
                        onClicked: modelData.kind === "app" ? (Usage.rememberApp(modelData.value), Apps.launch(modelData.value), search.close())
                                                            : (entry.text = modelData.value) }
                }
            }
        }
        Text {
            visible: home.suggested.length === 0
            x: search.colX; y: Metrics.tok("search.rows.y", 59) + 12
            text: Strings.tr("Your recent searches will appear here.")
            color: Metrics.themed("start.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
        }

        Heading { x: search.rightX; y: home.headY; text: Strings.tr("Quick searches") }
        MoreButton { x: search.rightX + search.rightWidth - 33; y: home.headY - 6 }
        Rectangle {
            x: search.rightX; y: Metrics.tok("search.card.y", 61)
            width: search.rightWidth; height: Metrics.tok("search.card.height", 150)
            radius: Metrics.flyoutRadius
            color: Metrics.themed("search.card.fill")
            border.color: Metrics.themed("search.card.border")
            Flow {
                x: 14; y: 18; width: parent.width - 28
                spacing: 14
                Repeater {
                    // Settings pages (fenestra-settings --page), as the reference's quick searches.
                    model: [["Focus settings", "focus"], ["Sound settings", "sound"], ["Bluetooth & devices", "bt-devices"],
                            ["Display settings", "display"], ["Color settings", "colors"], ["Search settings", "fx-search"]]
                    delegate: Rectangle {
                        required property var modelData
                        width: quickText.implicitWidth + 24; height: 28; radius: 14
                        color: quickMouse.containsMouse ? Metrics.themed("start.hover") : Metrics.themed("search.quick.fill")
                        border.color: Metrics.themed("search.quick.border")
                        Text { id: quickText; anchors.centerIn: parent; text: Strings.tr(modelData[0]); color: Theme.text
                               font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                        MouseArea { id: quickMouse; anchors.fill: parent; hoverEnabled: true
                            onClicked: { search.close(); Apps.runCommand("fenestra-settings --page " + modelData[1]) } }
                    }
                }
            }
        }

        Heading { x: search.rightX + 1; y: Metrics.tok("search.apps.y", 234) - 4; text: Strings.tr("Top apps") }
        Grid {
            x: search.rightX; y: Metrics.tok("search.card.y", 61) + 200
            columns: 3; spacing: Metrics.tok("search.tile.gap", 6)
            Repeater {
                model: home.topApps
                delegate: Rectangle {
                    required property var modelData
                    width: Metrics.tok("search.tile.width", 136) + (index === 1 ? 1 : 0); height: Metrics.tok("search.tile.height", 94)
                    required property int index
                    radius: Metrics.flyoutRadius
                    color: tm.containsMouse ? Metrics.themed("start.hover") : Metrics.themed("search.card.fill")
                    border.color: Metrics.themed("search.card.border")
                    Image { anchors.horizontalCenter: parent.horizontalCenter; y: 20; width: 32; height: 32
                            sourceSize: Qt.size(32 * Screen.devicePixelRatio, 32 * Screen.devicePixelRatio)
                            source: "image://icon/" + modelData.icon }
                    Text { x: 8; width: parent.width - 16; y: 60; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                           text: modelData.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                    MouseArea { id: tm; anchors.fill: parent; hoverEnabled: true
                        onClicked: { Usage.rememberApp(modelData.storageId); Apps.launch(modelData.storageId); search.close() } }
                }
            }
        }
    }

    // ---- Typing: chips, results, preview ---------------------------------------------------------
    Item {
        id: query
        visible: search.typing
        y: search.top; width: parent.width; height: parent.height - y
        readonly property int chipsY: Metrics.tok("search.query.chips.y", 24)
        Rectangle {
            // Back to the home page.
            x: 33; y: query.chipsY; width: 32; height: 32; radius: Metrics.controlRadius
            color: backMouse.containsMouse ? Metrics.themed("start.hover") : "transparent"
            SymbolicIcon { anchors.centerIn: parent; size: 24; src: Metrics.assets + "menu-icons/win11-explorer-back.svg" }
            MouseArea { id: backMouse; anchors.fill: parent; hoverEnabled: true; onClicked: { entry.text = ""; entry.forceActiveFocus() } }
        }
        Row {
            id: chips
            x: 70; y: query.chipsY; spacing: 4
            Repeater {
                model: [["all", "All"], ["apps", "Apps"], ["files", "Documents"], ["settings", "Settings"], ["folders", "Folders"], ["photos", "Photos"], ["web", "Web"]]
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool on: Search.filter === modelData[0]
                    width: chipText.implicitWidth + 24; height: Metrics.tok("search.chip.height", 32); radius: height / 2
                    color: on ? Theme.accentFill : chipMouse.containsMouse ? Metrics.themed("start.hover") : Metrics.themed("search.chip.fill")
                    border.color: on ? Theme.accentFill : Metrics.themed("search.chip.border")
                    Text { id: chipText; anchors.centerIn: parent; text: Strings.tr(modelData[1]); color: parent.on ? Theme.accentOn : Theme.text
                           font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
                    MouseArea { id: chipMouse; anchors.fill: parent; hoverEnabled: true; onClicked: { Search.filter = modelData[0]; search.selected = 0; entry.forceActiveFocus() } }
                }
            }
        }
        MoreButton { x: search.width - 59; y: query.chipsY }

        Flickable {
            id: results
            x: 29; y: Metrics.tok("search.query.preview.y", 70); width: Metrics.searchResultsWidth; height: parent.height - y - 3
            contentHeight: resultColumn.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: resultColumn
                width: parent.width
                Repeater {
                    model: Search.sections
                    delegate: Column {
                        id: section
                        required property var modelData
                        required property int index
                        width: parent.width
                        // Heading cap at y83, best match row at y112 (search.query.results.y).
                        Item {
                            width: parent.width; height: section.index ? 36 : Metrics.tok("search.query.results.y", 112) - Metrics.tok("search.query.preview.y", 70)
                            Heading { x: 6; y: parent.height - 33; text: section.modelData.title }
                        }
                        Repeater {
                            model: section.modelData.items
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool best: section.index === 0
                                readonly property bool isCurrent: search.current && JSON.stringify(search.current) === JSON.stringify(modelData)
                                width: parent.width; height: best ? 80 : 40; radius: Metrics.controlRadius
                                color: isCurrent ? Metrics.themed("search.result.fill")
                                       : rmouse.containsMouse ? Metrics.themed("start.hover") : "transparent"
                                Rectangle { visible: parent.isCurrent; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 22; radius: 1.5; color: Theme.accentFill }
                                Image {
                                    x: 10; anchors.verticalCenter: parent.verticalCenter; width: 24; height: 24
                                    sourceSize: Qt.size(24 * Screen.devicePixelRatio, 24 * Screen.devicePixelRatio)
                                    fillMode: Image.PreserveAspectFit
                                    source: modelData.iconSource ? modelData.iconSource : "image://icon/" + modelData.icon
                                }
                                Column {
                                    x: 41; width: parent.width - 49; anchors.verticalCenter: parent.verticalCenter
                                    // Best match: name, kind and date lines at 15 / 36 / 52 px from the
                                    // row's top (dark-100-11-search-query).
                                    anchors.verticalCenterOffset: -2
                                    Text { width: parent.width; height: best ? 22 : 19; text: search.displayTitle(modelData); elide: Text.ElideRight; color: Theme.text
                                           font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: best ? Font.DemiBold : Font.Normal }
                                    Text { visible: best; width: parent.width; height: 18; text: search.kindName(modelData); elide: Text.ElideRight
                                           color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                                    Text { width: parent.width; height: 16; text: best && modelData.modified ? Strings.tr("Last modified") + ": " + Qt.formatDateTime(modelData.modified, "d/M/yyyy, H:mm") : modelData.subtitle
                                           visible: text !== ""; elide: Text.ElideMiddle
                                           color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                                }
                                MouseArea { id: rmouse; anchors.fill: parent; hoverEnabled: true
                                    onClicked: { search.selected = search.flat.findIndex(i => JSON.stringify(i) === JSON.stringify(modelData)); Search.activate(modelData) } }
                            }
                        }
                    }
                }
                Text {
                    visible: Search.sections.length === 0
                    x: 7; topPadding: 8
                    text: Search.indexing ? Strings.tr("Searching…") : Strings.tr("No results")
                    color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                }
            }
        }
        // Preview pane
        Rectangle {
            id: pane
            visible: search.current !== null
            x: Metrics.tok("search.right.x", 330) + 34; y: Metrics.tok("search.query.preview.y", 70)
            width: Metrics.searchPreviewWidth; height: parent.height - y - 3
            radius: Metrics.flyoutRadius
            color: Metrics.themed("search.preview.fill")
            readonly property int pad: 24
            Image {
                anchors.horizontalCenter: parent.horizontalCenter; y: 32
                width: 64; height: 64
                sourceSize: Qt.size(96 * Screen.devicePixelRatio, 96 * Screen.devicePixelRatio)
                // Photos as a square thumbnail, icons as they are.
                fillMode: search.current && search.current.kind === "photo" ? Image.PreserveAspectCrop : Image.PreserveAspectFit
                source: search.current ? (search.current.iconSource ? search.current.iconSource : "image://icon/" + search.current.icon) : ""
            }
            Text { x: pane.pad; y: 112; width: parent.width - 2 * pane.pad; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                   text: search.current ? search.displayTitle(search.current) : ""
                   color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 18; font.weight: Font.DemiBold }
            Text { x: pane.pad; y: 140; width: parent.width - 2 * pane.pad; horizontalAlignment: Text.AlignHCenter
                   text: search.current ? search.kindName(search.current) : ""
                   color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            Rectangle { x: pane.pad + 2; y: 185; width: parent.width - 2 * x; height: 2; color: Metrics.themed("search.preview.separator") }
            Column {
                id: details
                x: pane.pad; y: 208; width: parent.width - 2 * pane.pad
                visible: search.current && search.current.path !== undefined
                spacing: 16
                Row {
                    Text { width: 108; rightPadding: 12; text: Strings.tr("Location"); color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                    Text { width: details.width - 108; elide: Text.ElideMiddle; text: search.current && search.current.subtitle ? search.current.subtitle : ""
                           color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption } }
                Row {
                    Text { width: 108; rightPadding: 12; text: Strings.tr("Last modified"); wrapMode: Text.WrapAtWordBoundaryOrAnywhere; color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                    Text { text: search.current && search.current.modified ? Qt.formatDateTime(search.current.modified, "d/M/yyyy, H:mm") : ""
                           color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption } }
            }
            Rectangle { visible: details.visible; x: pane.pad + 2; y: 293; width: parent.width - 2 * x; height: 2; color: Metrics.themed("search.preview.separator") }
            Column {
                x: 12; y: details.visible ? 307 : 198; width: parent.width - 24
                Repeater {
                    model: search.current ? search.actionsFor(search.current) : []
                    delegate: Rectangle {
                        required property var modelData
                        width: parent.width; height: 32; radius: Metrics.controlRadius
                        color: am.containsMouse ? Metrics.themed("start.hover") : "transparent"
                        SymbolicIcon { x: 16; anchors.verticalCenter: parent.verticalCenter; size: 16; monochrome: true
                                       src: modelData.iconSource || ""; name: modelData.iconSource ? "" : (modelData.icon || "") }
                        Text { x: 43; anchors.verticalCenter: parent.verticalCenter; text: modelData.text
                               color: Metrics.themed("search.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                        MouseArea { id: am; anchors.fill: parent; hoverEnabled: true; onClicked: modelData.action() }
                    }
                }
            }
        }
    }

    // Files as Explorer names them with known extensions hidden: "playa-verano", "Archivo JPG".
    function extension(item) {
        const m = (item.kind === "file" || item.kind === "photo") && item.title ? item.title.match(/\.([^.\/]+)$/) : null
        return m ? m[1] : ""
    }
    function displayTitle(item) {
        const ext = extension(item)
        return ext ? item.title.slice(0, -ext.length - 1) : item.title
    }
    function kindName(item) {
        const ext = extension(item).toLowerCase()
        if (ext === "txt") return Strings.tr("Text Document")
        if (ext) return Strings.tr("%1 File").arg(ext.toUpperCase())
        const kind = item.kind
        return Strings.tr({ app: "App", setting: "System settings", file: "Document", folder: "File folder", photo: "Photo", web: "Web" }[kind] || "")
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

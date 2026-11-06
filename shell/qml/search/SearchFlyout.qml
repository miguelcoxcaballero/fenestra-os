// SPDX-License-Identifier: GPL-3.0-or-later
// Search (S04, S05): metrics of arc/windows-search.css. Entry at the top, filter chips, a home
// page (Recent searches, Top apps) and, while typing, results (328 px) with a preview pane (376 px).
import QtQuick
import Fenestra.Shell

ShellPopup {
    id: search
    width: Metrics.searchWidth; height: Metrics.searchHeight
    property int selected: 0
    readonly property var flat: {
        const out = []
        for (const s of Search.sections) for (const i of s.items) out.push(i)
        return out
    }
    readonly property var current: flat.length ? flat[Math.min(selected, flat.length - 1)] : null

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

    // ---- Entry ------------------------------------------------------------------------------
    Rectangle {
        id: entryBox
        x: 33; y: 8; width: parent.width - 63; height: 32
        radius: 16
        color: Theme.dark ? Qt.rgba(28 / 255, 28 / 255, 28 / 255, 0.75) : Qt.rgba(1, 1, 1, 0.85)
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.08)
        Image { x: 14; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
                sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio)
                source: ShellSettings.searchIcon !== "" ? ShellSettings.searchIcon : Metrics.assets + "search/search.svg" }
        TextInput {
            id: entry
            x: 40; width: parent.width - 54
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.text
            selectionColor: Theme.accentFill; selectedTextColor: Theme.accentOn
            font.family: Metrics.fontFamily; font.pixelSize: 13
            clip: true
            // No focus ring or underline (windows-search.css :136-140): the field stays as drawn.
            onTextChanged: { Search.text = text; search.selected = 0 }
            Keys.onDownPressed: search.selected = Math.min(search.selected + 1, search.flat.length - 1)
            Keys.onUpPressed: search.selected = Math.max(search.selected - 1, 0)
            Keys.onReturnPressed: if (search.current) Search.activate(search.current)
            Keys.onEnterPressed: if (search.current) Search.activate(search.current)
            Keys.onEscapePressed: search.close()
        }
    }

    // ---- Filter chips -----------------------------------------------------------------------
    Row {
        id: chips
        x: 21; y: 57; spacing: 6
        Repeater {
            model: [["all", "All"], ["web", "Web"], ["apps", "Apps"], ["files", "Documents"], ["settings", "Settings"], ["folders", "Folders"], ["photos", "Photos"]]
            delegate: Rectangle {
                required property var modelData
                readonly property bool on: Search.filter === modelData[0]
                width: chipText.implicitWidth + 24; height: 28; radius: 15
                color: on ? Theme.accentFill : (chipMouse.containsMouse ? Theme.hover : (Theme.dark ? Qt.rgba(1, 1, 1, 0.055) : Qt.rgba(1, 1, 1, 0.7)))
                border.color: on ? "transparent" : (Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.06))
                Text { id: chipText; anchors.centerIn: parent; text: Strings.tr(modelData[1]); color: parent.on ? Theme.accentOn : Theme.text
                       font.family: Metrics.fontFamily; font.pixelSize: 14 }
                MouseArea { id: chipMouse; anchors.fill: parent; hoverEnabled: true; onClicked: { Search.filter = modelData[0]; search.selected = 0; entry.forceActiveFocus() } }
            }
        }
    }

    // ---- Home: Recent searches, Top apps ------------------------------------------------------
    Column {
        visible: entry.text.trim() === ""
        x: 33; y: 105; width: parent.width - 66
        spacing: 8
        Text { text: Strings.tr("Recent searches"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 18; font.weight: Font.DemiBold }
        Repeater {
            model: Usage.recentSearches
            delegate: Rectangle {
                required property var modelData
                width: parent.width; height: 48; radius: Metrics.controlRadius
                color: hm.containsMouse ? Theme.hover : "transparent"
                Rectangle {
                    x: 8; anchors.verticalCenter: parent.verticalCenter; width: 40; height: 40; radius: 4
                    color: modelData.kind === "query" ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.04)) : "transparent"
                    Image { anchors.centerIn: parent; width: modelData.kind === "query" ? 16 : 32; height: width
                            sourceSize: Qt.size(32 * Screen.devicePixelRatio, 32 * Screen.devicePixelRatio)
                            source: modelData.kind === "query" ? Metrics.assets + "search/search.svg" : "image://icon/" + modelData.icon }
                }
                Column {
                    x: 60; anchors.verticalCenter: parent.verticalCenter
                    Text { text: modelData.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                    Text { text: modelData.age; visible: text !== ""; color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                }
                MouseArea { id: hm; anchors.fill: parent; hoverEnabled: true
                    onClicked: modelData.kind === "app" ? (Usage.rememberApp(modelData.value), Apps.launch(modelData.value), search.close())
                                                        : (entry.text = modelData.value) }
            }
        }
        Text {
            visible: Usage.recentSearches.length === 0
            text: Strings.tr("Your recent searches will appear here.")
            color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12
        }
        Item { width: 1; height: 16 }
        Text { text: Strings.tr("Top apps"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 18; font.weight: Font.DemiBold }
        Row {
            Repeater {
                model: Usage.topApps(6)
                delegate: AppTile {
                    required property var modelData
                    tileWidth: 100
                    storageId: modelData.storageId; name: modelData.name; icon: modelData.icon
                    onActivated: { Usage.rememberApp(storageId); Apps.launch(storageId); search.close() }
                }
            }
        }
    }

    // ---- Results + preview --------------------------------------------------------------------
    Item {
        visible: entry.text.trim() !== ""
        x: 25; y: 105; width: parent.width - 57; height: parent.height - y - 18
        Flickable {
            id: results
            width: Metrics.searchResultsWidth; height: parent.height
            contentHeight: resultColumn.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: resultColumn
                width: parent.width
                Repeater {
                    model: Search.sections
                    delegate: Column {
                        required property var modelData
                        required property int index
                        width: parent.width
                        Text { topPadding: index ? 14 : 0; bottomPadding: 6; text: modelData.title; color: Theme.text
                               font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                        Repeater {
                            model: modelData.items
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool isCurrent: search.current && JSON.stringify(search.current) === JSON.stringify(modelData)
                                width: parent.width; height: 62; radius: Metrics.controlRadius
                                color: isCurrent ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.075) : Qt.rgba(0, 0, 0, 0.05))
                                       : rmouse.containsMouse ? (Theme.dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.03)) : "transparent"
                                Rectangle { visible: parent.isCurrent; x: 0; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 16; radius: 2; color: Theme.accentFill }
                                Image {
                                    x: 12; anchors.verticalCenter: parent.verticalCenter; width: 40; height: 40
                                    sourceSize: Qt.size(40 * Screen.devicePixelRatio, 40 * Screen.devicePixelRatio)
                                    fillMode: Image.PreserveAspectFit
                                    source: modelData.iconSource ? modelData.iconSource : "image://icon/" + modelData.icon
                                }
                                Column {
                                    x: 64; width: parent.width - 72; anchors.verticalCenter: parent.verticalCenter
                                    Text { width: parent.width; text: modelData.title; elide: Text.ElideRight; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                                    Text { width: parent.width; text: modelData.subtitle; elide: Text.ElideMiddle; color: Theme.dark ? "#c8cbca" : "#5c5c5c"
                                           font.family: Metrics.fontFamily; font.pixelSize: 12 }
                                }
                                MouseArea { id: rmouse; anchors.fill: parent; hoverEnabled: true
                                    onClicked: { search.selected = search.flat.findIndex(i => JSON.stringify(i) === JSON.stringify(modelData)); Search.activate(modelData) } }
                            }
                        }
                    }
                }
                Text {
                    visible: Search.sections.length === 0
                    text: Search.indexing ? Strings.tr("Searching…") : Strings.tr("No results")
                    color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 14
                }
            }
        }
        // Preview pane
        Rectangle {
            visible: search.current !== null
            x: Metrics.searchResultsWidth + 22; width: Metrics.searchPreviewWidth; height: Math.min(parent.height, previewColumn.height + 48)
            radius: 8
            color: Theme.dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(1, 1, 1, 0.6)
            Column {
                id: previewColumn
                x: 24; y: 23; width: parent.width - 49
                spacing: 6
                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: search.current && search.current.kind === "photo" ? 96 : 64; height: width
                    sourceSize: Qt.size(96 * Screen.devicePixelRatio, 96 * Screen.devicePixelRatio)
                    fillMode: Image.PreserveAspectFit
                    source: search.current ? (search.current.iconSource ? search.current.iconSource : "image://icon/" + search.current.icon) : ""
                }
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; text: search.current ? search.current.title : ""
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold }
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: search.current ? search.kindName(search.current.kind) : ""
                       color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                Item { width: 1; height: 10 }
                Rectangle { width: parent.width; height: 1; color: Theme.separator }
                Repeater {
                    model: search.current ? search.actionsFor(search.current) : []
                    delegate: MenuRow {
                        required property var modelData
                        width: previewColumn.width
                        text: modelData.text; iconName: modelData.icon || ""; iconSource: modelData.iconSource || ""
                        onTriggered: modelData.action()
                    }
                }
                Column {
                    visible: search.current && search.current.path !== undefined
                    width: parent.width; topPadding: 8; spacing: 4
                    Rectangle { width: parent.width; height: 1; color: Theme.separator }
                    Row { spacing: 8; topPadding: 6
                        Text { width: 124; text: Strings.tr("Location"); color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                        Text { width: previewColumn.width - 132; elide: Text.ElideMiddle; text: search.current && search.current.subtitle ? search.current.subtitle : ""
                               color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 } }
                    Row { spacing: 8
                        Text { width: 124; text: Strings.tr("Last modified"); color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                        Text { text: search.current && search.current.modified ? Qt.formatDateTime(search.current.modified, "dd/MM/yyyy, HH:mm") : ""
                               color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 } }
                }
            }
        }
    }

    function kindName(kind) {
        return Strings.tr({ app: "App", setting: "System settings", file: "Document", folder: "File folder", photo: "Photo", web: "Web" }[kind] || "")
    }
    function actionsFor(item) {
        const a = [{ text: Strings.tr(item.kind === "web" ? "Open results in browser" : "Open"), icon: "document-open-symbolic", action: () => Search.activate(item) }]
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

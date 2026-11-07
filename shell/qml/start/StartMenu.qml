// SPDX-License-Identifier: GPL-3.0-or-later
// Start, the 2025 layout of the user's Windows 11 (reference-shots/user-win11 160039 / 160110 at
// 150 %; positions in logical px from the panel's outer top-left = device px / 1.5, start.* tokens):
// 834 x 866 panel; a darker header band (66 px) with the search box; one scrolling page with
// Pinned (8 columns of 96 x 84, two rows, "Show all ˅" unfolds the rest), Recent (3 columns of
// 256 x 56, two rows, "Show all ›" opens the full list) and All (View: Category | Grid | List;
// category tiles of 156 px with four 32 px icons, the fourth slot a 2 x 2 of 16 px icons when the
// category has more apps; a tile opens the category); a footer band (64 px) with the account and
// power buttons. Text is placed by its baseline (start.*.baseline) as measured.
import QtQuick
import Fenestra.Shell

ShellPopup {
    id: start
    panelWidth: Metrics.startWidth
    // 866 px, or what fits under a 47 px top margin on short screens.
    panelHeight: targetScreen ? Math.min(Metrics.startHeight, targetScreen.height - Metrics.taskbarHeight - Metrics.flyoutGap
                                                             - Metrics.tok("start.margin.top", 47)) : Metrics.startHeight
    signal searchRequested(string text)
    // Compatibility with the bench (tests/shell-kwin): allApps scrolls to the All section.
    property bool allApps: false
    property string allView: "category"   // category (reference) | grid | list
    property bool pinnedExpanded: false
    property string page: ""                // "" | "recent"
    property var category: null             // the open category {name, apps}
    property var pins: StartPins.apps
    readonly property real bw: material.fill.border.width
    readonly property real headerH: Metrics.num("start.header.height", 66)
    readonly property real footerY: panelHeight - Metrics.num("start.footer.height", 64.67)
    readonly property real gridX: Metrics.num("start.grid.x", 33.33)
    readonly property int columns: Metrics.tok("start.pinned.columns", 8)
    readonly property int pinnedRows: Math.ceil(pins.length / columns)
    readonly property int pinnedShown: pinnedExpanded ? pinnedRows : Math.min(Metrics.tok("start.pinned.rows", 2), pinnedRows)
    readonly property var recent: RecentFiles.items
    readonly property int recentColumns: Metrics.tok("start.recent.columns", 3)
    readonly property int recentShown: Math.min(Metrics.tok("start.recent.rows", 2), Math.ceil(recent.length / recentColumns))
    // Section offsets: the reference has two Pinned and two Recent rows.
    readonly property real pinnedShift: (pinnedShown - 2) * Metrics.startTileHeight
    readonly property real recentShift: pinnedShift + (Math.max(1, recentShown) - 2) * Metrics.num("start.recent.row", 56)

    onOpened: { allApps = false; page = ""; category = null; pinnedExpanded = false; scroller.contentY = 0; header.forceActiveFocus() }
    onAllAppsChanged: if (allApps) scroller.contentY = Math.max(0, Math.min(allSection.y - 20, scroller.contentHeight - scroller.height))

    // Text placed by its bl (logical px in its parent).
    component Label: Text {
        property real bl
        y: bl - baselineOffset
        color: Theme.text
        font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize); font.pixelSize: Metrics.fontCaption
    }
    component Secondary: Label { color: Metrics.themed("popup.text.secondary") }
    // "Show all ˅" / "Show all ›" / "View: Category ˅": text and a Fluent chevron, right-aligned.
    component LinkButton: Item {
        id: lb
        property string text
        property string glyph: "\ue96e"   // ChevronDownSmall; \ue970 ChevronRightSmall
        property real bl
        signal clicked()
        readonly property real glyphGap: Metrics.num("start.link.gap", 9.67)
        width: lbText.implicitWidth + glyphGap + chev.width; height: 32
        y: bl - lbText.baselineOffset - (height - lbText.height) / 2
        Rectangle {
            x: -Metrics.num("start.link.padding", 11); width: parent.width + 2 * Metrics.num("start.link.padding", 11)
            height: parent.height; radius: Metrics.controlRadius
            color: lbm.pressed ? Metrics.themed("popup.pressed") : lbm.containsMouse ? Metrics.themed("popup.hover") : "transparent"
        }
        Text {
            id: lbText
            anchors.verticalCenter: parent.verticalCenter
            text: lb.text; color: Theme.text
            font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize); font.pixelSize: Metrics.fontBody
        }
        FluentGlyph {
            id: chev
            x: parent.width - width; size: Metrics.num("start.link.glyph", 9.33)
            y: lbText.y + lbText.baselineOffset - Metrics.num("start.link.glyph.baseline", 9.33)
            glyph: lb.glyph
            fallback: Metrics.assets + "menu-icons/" + (lb.glyph === "\ue96e" ? "win11-chevron-down.svg" : "win11-chevron-right.svg")
        }
        MouseArea { id: lbm; anchors.fill: parent; anchors.margins: -Metrics.num("start.link.padding", 11); hoverEnabled: true; onClicked: lb.clicked() }
    }

    // ---- Header band: search box --------------------------------------------------------------
    // The panel's fill is drawn here in three parts (header, body, footer): the bands are a
    // different acrylic, not an overlay on the body (an overlay cannot keep the chroma).
    Component.onCompleted: material.fill.color = "transparent"
    Rectangle {
        x: start.bw; y: start.headerH; width: start.panelWidth - 2 * start.bw; height: start.footerY - y
        color: Metrics.themed("acrylic.panel" + (ShellSettings.transparency ? "" : ".solid"))
    }
    Rectangle {
        x: start.bw; y: start.bw; width: start.panelWidth - 2 * start.bw; height: start.headerH - start.bw
        topLeftRadius: Metrics.flyoutRadius - start.bw; topRightRadius: Metrics.flyoutRadius - start.bw
        color: Metrics.themed("start.header.fill" + (ShellSettings.transparency ? "" : ".solid"))
        Rectangle { y: parent.height - height; width: parent.width; height: start.bw; color: Metrics.themed("start.divider") }
    }
    Item {
        id: header
        width: parent.width; height: start.headerH
        focus: true
        // Typing in Start goes to Search, like the search box.
        Keys.onPressed: (e) => {
            if (e.text.length === 1 && e.text.trim() !== "" && !(e.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
                start.searchRequested(e.text); e.accepted = true
            }
        }
        SearchBox {
            x: start.gridX; y: Metrics.num("start.search.y", 17.33)
            width: start.panelWidth - 2 * start.gridX
            placeholder: Strings.tr("Search for apps, settings, and documents")
            caretVisible: start.shown && start.page === "" && start.category === null
            MouseArea { anchors.fill: parent; onClicked: start.searchRequested("") }
        }
    }

    // ---- Scrolling page: Pinned, Recent, All ----------------------------------------------------
    Flickable {
        id: scroller
        visible: start.page === ""
        y: start.headerH; width: parent.width; height: start.footerY - y
        contentHeight: allSection.y + allSection.height + Metrics.num("start.bottom.padding", 24)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        // Panel coordinates of the reference -> content coordinates.
        function pp(v) { return v - start.headerH }

        Label { x: Metrics.num("start.title.x", 65.33) - 1; bl: scroller.pp(Metrics.num("start.pinned.title.baseline", 110))
                text: Strings.tr("Pinned"); font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
        LinkButton {
            visible: start.pinnedRows > Metrics.tok("start.pinned.rows", 2)
            x: Metrics.num("start.link.right", 770) - width; bl: scroller.pp(Metrics.num("start.pinned.title.baseline", 110))
            text: Strings.tr(start.pinnedExpanded ? "Show less" : "Show all")
            glyph: start.pinnedExpanded ? "\ue96d" : "\ue96e"
            onClicked: start.pinnedExpanded = !start.pinnedExpanded
        }
        Grid {
            id: pinnedGrid
            x: start.gridX; y: scroller.pp(Metrics.num("start.pinned.icon.y", 141.33) - Metrics.tok("start.pinned.icon.top", 12))
            columns: start.columns
            Repeater {
                model: start.pins.slice(0, start.pinnedShown * start.columns)
                delegate: AppTile {
                    required property var modelData
                    storageId: modelData.storageId; name: modelData.name; icon: modelData.icon
                    onActivated: { Apps.launch(storageId); start.close() }
                    onContextRequested: (x, y) => start.showAppMenu(this, storageId, name, true)
                }
            }
        }

        Label { x: Metrics.num("start.title.x", 65.33) - 1; bl: scroller.pp(Metrics.num("start.recent.title.baseline", 350.67)) + start.pinnedShift
                text: Strings.tr("Recent"); font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
        LinkButton {
            visible: start.recent.length > start.recentColumns * Metrics.tok("start.recent.rows", 2)
            x: Metrics.num("start.link.right", 770) - width; bl: scroller.pp(Metrics.num("start.recent.title.baseline", 350.67)) + start.pinnedShift
            text: Strings.tr("Show all"); glyph: "\ue970"
            onClicked: start.page = "recent"
        }
        Grid {
            x: start.gridX; y: scroller.pp(Metrics.num("start.recent.icon.y", 382.67) - Metrics.num("start.recent.icon.top", 12)) + start.pinnedShift
            columns: start.recentColumns
            Repeater {
                model: start.recent.slice(0, start.recentColumns * Metrics.tok("start.recent.rows", 2))
                delegate: RecentItem { required property var modelData; item: modelData }
            }
        }
        Secondary {
            visible: start.recent.length === 0
            x: Metrics.num("start.title.x", 65.33); bl: scroller.pp(Metrics.num("start.recent.name.baseline", 395.33)) + start.pinnedShift
            text: Strings.tr("Your recent files will appear here.")
        }

        Item {
            id: allSection
            y: start.recentShift
            width: scroller.width
            height: scroller.pp(Metrics.num("start.all.tiles.y", 555.33)) + allBody.height
            Label { x: Metrics.num("start.title.x", 65.33) - 1; bl: scroller.pp(Metrics.num("start.all.title.baseline", 535.33))
                    text: Strings.tr("All"); font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
            LinkButton {
                id: viewButton
                x: Metrics.num("start.link.right", 770) - width; bl: scroller.pp(Metrics.num("start.all.title.baseline", 535.33))
                text: Strings.tr("View") + ": " + Strings.tr(start.allView === "grid" ? "Grid" : start.allView === "list" ? "List" : "Category")
                onClicked: start.openViewMenu(viewButton)
            }
            Loader {
                id: allBody
                y: scroller.pp(Metrics.num("start.all.tiles.y", 555.33))
                width: parent.width
                active: start.shown || start.visible
                sourceComponent: start.allView === "grid" ? gridView : start.allView === "list" ? listView : categoryView
            }
        }
    }

    // A recent file: 32 px icon at 32 px, name and age (12 px) from 76.67 px, 256 x 56 cells.
    component RecentItem: Item {
        id: ri
        property var item
        width: Metrics.num("start.recent.width", 256); height: Metrics.num("start.recent.row", 56)
        Rectangle {
            anchors.fill: parent; anchors.margins: 2; radius: Metrics.controlRadius
            color: rim.pressed ? Metrics.themed("popup.pressed") : rim.containsMouse ? Metrics.themed("popup.hover") : "transparent"
        }
        Image { x: Metrics.num("start.recent.icon.x", 32); y: Metrics.num("start.recent.icon.top", 12); width: 32; height: 32
                sourceSize: Qt.size(64, 64); source: "image://icon/" + ri.item.icon }
        readonly property real textX: Metrics.num("start.recent.text.x", 76.67) - 0.67
        Label { x: ri.textX; width: ri.width - x - Metrics.num("start.recent.text.right", 14); elide: Text.ElideRight
                bl: Metrics.num("start.recent.icon.top", 12) + Metrics.num("start.recent.name.baseline", 395.33) - Metrics.num("start.recent.icon.y", 382.67)
                text: ri.item.name }
        Secondary { x: ri.textX; width: ri.width - x - Metrics.num("start.recent.text.right", 14); elide: Text.ElideRight
                    bl: Metrics.num("start.recent.icon.top", 12) + Metrics.num("start.recent.age.baseline", 411.33) - Metrics.num("start.recent.icon.y", 382.67)
                    text: ri.item.age }
        MouseArea { id: rim; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton
                    onClicked: { RecentFiles.open(ri.item.uri); start.close() } }
    }

    // Category view: 4 columns of 156 px tiles, 183.33 px apart, rows 204.67 px apart.
    Component {
        id: categoryView
        Item {
            readonly property var groups: start.shown ? AllApps.groups() : []
            height: Math.ceil(groups.length / 4) * Metrics.num("start.category.pitch.y", 204.67)
            Repeater {
                model: parent.groups
                delegate: Item {
                    id: cat
                    required property var modelData
                    required property int index
                    readonly property real size: Metrics.num("start.category.size", 156)
                    x: Metrics.num("start.title.x", 65.33) + (index % 4) * Metrics.num("start.category.pitch.x", 183.33)
                    y: Math.floor(index / 4) * Metrics.num("start.category.pitch.y", 204.67)
                    width: size; height: Metrics.num("start.category.pitch.y", 204.67)
                    Rectangle {
                        width: cat.size; height: cat.size; radius: Metrics.flyoutRadius
                        color: cm.pressed ? Metrics.themed("popup.pressed") : cm.containsMouse ? Metrics.themed("start.category.hover") : Metrics.themed("start.category.fill")
                        border.width: start.bw; border.color: Metrics.themed("start.category.border")
                        Repeater {
                            model: cat.modelData.apps.length > 4 ? cat.modelData.apps.slice(0, 3) : cat.modelData.apps
                            delegate: Image {
                                required property var modelData
                                required property int index
                                x: Metrics.num("start.category.icon.x", 28) + (index % 2) * Metrics.num("start.category.icon.pitch", 68)
                                y: Metrics.num("start.category.icon.x", 28) + Math.floor(index / 2) * Metrics.num("start.category.icon.pitch", 68)
                                width: 32; height: 32; sourceSize: Qt.size(64, 64)
                                source: "image://icon/" + modelData.icon
                            }
                        }
                        // More apps: the fourth slot shows the next four at 16 px (2 px apart).
                        Grid {
                            visible: cat.modelData.apps.length > 4
                            x: Metrics.num("start.category.icon.x", 28) + Metrics.num("start.category.icon.pitch", 68) - 1
                            y: x; columns: 2; spacing: 2
                            Repeater {
                                model: cat.modelData.apps.length > 4 ? cat.modelData.apps.slice(3, 7) : []
                                delegate: Image { required property var modelData; width: 16; height: 16; sourceSize: Qt.size(32, 32)
                                                  source: "image://icon/" + modelData.icon }
                            }
                        }
                        MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; onClicked: start.category = cat.modelData }
                    }
                    Label { width: cat.size; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                            bl: Metrics.num("start.category.label.baseline", 180)
                            text: Strings.tr(cat.modelData.name) }
                }
            }
        }
    }
    Component {
        id: gridView
        Grid {
            x: start.gridX; columns: start.columns
            Repeater {
                model: AllApps
                delegate: AppTile {
                    required property var model
                    storageId: model.storageId; name: model.name; icon: model.icon
                    onActivated: { Apps.launch(storageId); start.close() }
                    onContextRequested: start.showAppMenu(this, storageId, name, false)
                }
            }
        }
    }
    // List view: letters and 40 px rows (24 px icon, 12 px name), as the All apps list of Windows.
    Component {
        id: listView
        Column {
            x: start.gridX; width: start.panelWidth - 2 * start.gridX
            Repeater {
                model: AllApps
                delegate: Column {
                    id: lr
                    required property var model
                    required property int index
                    width: parent.width
                    Item {
                        visible: lr.index === 0 || AllApps.data(AllApps.index(lr.index - 1, 0), 261) !== lr.model.letter
                        width: parent.width; height: visible ? 40 : 0
                        Label { x: 32 + 12 - width / 2; bl: 25; text: lr.model.letter; font.pixelSize: Metrics.fontBody }
                    }
                    Item {
                        width: parent.width; height: 40
                        Rectangle { anchors.fill: parent; radius: Metrics.controlRadius
                                    color: lm.pressed ? Metrics.themed("popup.pressed") : lm.containsMouse ? Metrics.themed("popup.hover") : "transparent" }
                        Image { x: 32; anchors.verticalCenter: parent.verticalCenter; width: 24; height: 24; sourceSize: Qt.size(48, 48)
                                source: "image://icon/" + lr.model.icon }
                        Label { x: 76; bl: 25; width: parent.width - x - 16; elide: Text.ElideRight; text: lr.model.name }
                        MouseArea { id: lm; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: (e) => e.button === Qt.RightButton ? start.showAppMenu(parent, lr.model.storageId, lr.model.name, false)
                                                                                   : (Apps.launch(lr.model.storageId), start.close()) }
                    }
                }
            }
        }
    }

    // ---- Recent: every recent file (Show all ›) --------------------------------------------------
    Item {
        visible: start.page === "recent"
        y: start.headerH; width: parent.width; height: start.footerY - y
        BackTitle { title: Strings.tr("Recent"); onBack: start.page = "" }
        Flickable {
            x: start.gridX; y: Metrics.num("start.recent.icon.y", 382.67) - Metrics.num("start.recent.title.baseline", 350.67) + 44 - 12
            width: start.panelWidth - 2 * start.gridX; height: parent.height - y
            contentHeight: recentAll.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            Grid { id: recentAll; columns: start.recentColumns
                   Repeater { model: start.page === "recent" ? start.recent : []; delegate: RecentItem { required property var modelData; item: modelData } } }
        }
    }
    // A page's title row: ‹ and the title where the section title was.
    component BackTitle: Item {
        id: bt
        property string title
        signal back()
        width: parent.width; height: 64
        Rectangle {
            x: Metrics.num("start.title.x", 65.33) - 1 - 40; y: 44 - 10.67 / 2 - 16 - 3; width: 32; height: 32; radius: Metrics.controlRadius
            color: btm.containsMouse ? Metrics.themed("popup.hover") : "transparent"
            FluentGlyph { anchors.centerIn: parent; size: 16; glyph: "\ue72b"; fallback: Metrics.assets + "menu-icons/win11-explorer-back.svg" }
            MouseArea { id: btm; anchors.fill: parent; hoverEnabled: true; onClicked: bt.back() }
        }
        Label { x: Metrics.num("start.title.x", 65.33) - 1; bl: 44; text: bt.title; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
    }

    // ---- An open category: its apps over the page --------------------------------------------
    MouseArea {
        visible: start.category !== null
        y: start.headerH; width: parent.width; height: start.footerY - y
        onClicked: start.category = null
        Acrylic {
            id: categoryCard
            recipe: "menu.panel"; shadowKind: "menu"
            width: Math.min(4, start.category ? start.category.apps.length : 1) * Metrics.startTileWidth + 2 * 24
            height: 56 + Math.ceil((start.category ? start.category.apps.length : 0) / 4) * Metrics.startTileHeight + 16
            x: (parent.width - width) / 2; y: Math.max(16, (parent.height - height) / 2)
            MouseArea { anchors.fill: parent }   // clicks inside do not close it
            Label { x: 24; bl: 36; text: start.category ? Strings.tr(start.category.name) : ""
                    font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
            Grid {
                x: 24; y: 52; columns: 4
                Repeater {
                    model: start.category ? start.category.apps : []
                    delegate: AppTile {
                        required property var modelData
                        storageId: modelData.storageId; name: modelData.name; icon: modelData.icon
                        onActivated: { Apps.launch(storageId); start.close() }
                        onContextRequested: start.showAppMenu(this, storageId, name, false)
                    }
                }
            }
            Keys.onEscapePressed: start.category = null
        }
    }

    // ---- Footer band: account and power ---------------------------------------------------------
    Rectangle {
        id: footer
        x: start.bw; y: start.footerY
        width: start.panelWidth - 2 * start.bw; height: start.panelHeight - start.bw - y
        bottomLeftRadius: Metrics.flyoutRadius - start.bw; bottomRightRadius: Metrics.flyoutRadius - start.bw
        color: Metrics.themed("start.header.fill" + (ShellSettings.transparency ? "" : ".solid"))
        Rectangle { width: parent.width; height: start.bw; color: Metrics.themed("start.divider") }
    }
    Rectangle {
        id: account
        // Avatar at 65.33, name from 124 (12 px), 40 px high button centred in the band.
        x: Metrics.num("start.title.x", 65.33) - 12; y: (start.footerY + start.panelHeight) / 2 - height / 2
        width: accountRow.implicitWidth + 24; height: 40
        radius: Metrics.controlRadius
        color: am2.pressed ? Metrics.themed("popup.pressed") : am2.containsMouse ? Metrics.themed("popup.hover") : "transparent"
        Row {
            id: accountRow
            x: 12; anchors.verticalCenter: parent.verticalCenter; spacing: Metrics.num("start.footer.name.gap", 12)
            Avatar { size: Metrics.tok("start.footer.avatar", 32) }
            Text { anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: Metrics.num("start.footer.name.offset", 0)
                   text: UserInfo.name; color: Theme.text; font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize); font.pixelSize: Metrics.fontCaption }
        }
        MouseArea { id: am2; anchors.fill: parent; hoverEnabled: true; onClicked: start.openAccountMenu() }
    }
    Rectangle {
        id: powerButton
        // 16 px glyph whose right edge lines up with the links (769.33), 40 px button.
        x: Metrics.num("start.power.x", 741.33); y: (start.footerY + start.panelHeight) / 2 - height / 2
        width: 40; height: 40; radius: Metrics.controlRadius
        color: pm.pressed ? Metrics.themed("popup.pressed") : pm.containsMouse ? Metrics.themed("popup.hover") : "transparent"
        Accessible.name: Strings.tr("Power")
        FluentGlyph { anchors.centerIn: parent; size: 16; glyph: "\ue7e8"; fallback: Metrics.assets + "power/3.svg" }
        MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true; onClicked: start.openPowerMenu() }
    }

    // Menus above the footer buttons: the gap counts from the taskbar, so add Start's own place above it.
    function aboveFooter(extra) { return Metrics.flyoutGap + start.panelHeight - powerButton.y + extra }
    function openPowerMenu() {
        powerMenu.anchorX = start.screenX + powerButton.x + powerButton.width / 2
        powerMenu.open()
    }
    function openAccountMenu() {
        accountMenu.anchorLeft = start.screenX + Metrics.tok("menu.account.x", 15)
        accountMenu.open()
    }
    function openViewMenu(button) {
        const p = button.mapToItem(start.panel, button.width / 2, button.height)
        viewMenu.anchorX = start.screenX + p.x
        viewMenu.gap = Metrics.flyoutGap + start.panelHeight - p.y - viewMenu.height + start.shadowMargin
        viewMenu.open()
    }
    ContextMenu {
        id: viewMenu
        targetScreen: start.targetScreen
        overPanel: true
        onDismissed: start.requestActivate()
        items: [
            { text: Strings.tr("Category"), action: () => start.allView = "category" },
            { text: Strings.tr("Grid"), action: () => start.allView = "grid" },
            { text: Strings.tr("List"), action: () => start.allView = "list" },
        ]
    }
    ContextMenu {
        id: powerMenu
        targetScreen: start.targetScreen
        overPanel: true
        gap: start.aboveFooter(Metrics.tok("menu.power.gap", 4))
        onDismissed: start.requestActivate()
        items: [
            { text: Strings.tr("Lock"), iconSource: Metrics.assets + "power/1.svg", iconSize: 19, action: () => { start.close(); Session.lock() } },
        ].concat(Session.canSuspend ? [{ text: Strings.tr("Sleep"), iconSource: Metrics.assets + "power/4.svg", iconSize: 19, action: () => { start.close(); Session.suspend() } }] : [], [
            { text: Strings.tr("Shut down"), iconSource: Metrics.assets + "power/3.svg", iconSize: 19, action: () => { start.close(); Session.powerOff() } },
            { text: Strings.tr("Restart"), iconSource: Metrics.assets + "power/2.svg", iconSize: 19, action: () => { start.close(); Session.reboot() } },
        ])
    }
    // Account card (362 x 128): switch user and sign out on top, picture, name, account kind and
    // a link to the account settings.
    Flyout {
        id: accountMenu
        motion: "menu"
        targetScreen: start.targetScreen
        gap: start.aboveFooter(Metrics.tok("menu.account.gap", 6))
        padding: 0
        recipe: "menu.panel"
        onDismissed: start.requestActivate()
        Item {
            width: Metrics.tok("menu.account.width", 362); height: Metrics.tok("menu.account.height", 128)
            MenuLink {
                x: 12; y: 12
                iconSource: Metrics.assets + "power/7.svg"
                text: Strings.tr("Switch user"); secondary: true
                onClicked: { accountMenu.close(); start.close(); Session.switchUser() }
            }
            MenuLink {
                anchors.right: parent.right; anchors.rightMargin: 16; y: 12
                text: Strings.tr("Sign out"); fontSize: Metrics.fontBody
                onClicked: { accountMenu.close(); start.close(); Session.logout() }
            }
            Avatar { x: 17; y: 55; size: Metrics.tok("menu.account.avatar", 58) }
            Column {
                x: 87; y: 55
                Item { width: nameText.implicitWidth; height: 24
                       Text { id: nameText; y: -3; text: UserInfo.fullName || UserInfo.name; color: Theme.text; font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize); font.pixelSize: 20; font.weight: Font.DemiBold } }
                Text { height: 17; text: Strings.tr("Local account"); color: Metrics.themed("popup.text.secondary"); font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize); font.pixelSize: Metrics.fontCaption }
                Text {
                    height: 17; text: Strings.tr("Manage my account"); color: Theme.accentText
                    font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize); font.pixelSize: Metrics.fontCaption
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: { accountMenu.close(); start.close(); Apps.runCommand("fenestra-settings --page yourinfo") } }
                }
            }
        }
    }
    // The account picture, or the reference's placeholder: grey silhouette on a light disc.
    component Avatar: Item {
        id: av
        property int size: 32
        width: size; height: size
        Canvas {
            anchors.fill: parent
            visible: UserInfo.picture === ""
            onPaint: {
                const c = getContext("2d"), s = av.size
                c.reset()
                c.fillStyle = Tokens.v("start.avatar.fill", "#fafafa")
                c.beginPath(); c.arc(s / 2, s / 2, s / 2, 0, 2 * Math.PI); c.fill()
                c.fillStyle = Tokens.v("start.avatar.ink", "#8f8f8f")
                c.beginPath(); c.arc(s / 2, s * 0.355, s * 0.14, 0, 2 * Math.PI); c.fill()
                c.save(); c.beginPath(); c.rect(0, 0, s, s * 0.775); c.clip()
                c.beginPath(); c.ellipse(s * 0.25, s * 0.55, s * 0.5, s * 0.44); c.fill()
                c.restore()
            }
        }
        Rectangle {
            anchors.fill: parent; radius: av.size / 2; clip: true
            visible: UserInfo.picture !== ""
            Image { anchors.fill: parent; source: UserInfo.picture; fillMode: Image.PreserveAspectCrop }
        }
    }
    component MenuLink: Rectangle {
        id: link
        property string text
        property url iconSource
        property bool secondary: false
        property int fontSize: Metrics.fontCaption
        signal clicked()
        width: linkRow.implicitWidth + 12; height: 28
        radius: Metrics.controlRadius
        color: lmouse.containsMouse ? Metrics.themed("popup.hover") : "transparent"
        Row {
            id: linkRow
            x: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 7
            SymbolicIcon { visible: link.iconSource.toString() !== ""; size: 18; src: link.iconSource; anchors.verticalCenter: parent.verticalCenter }
            Text { text: link.text; anchors.verticalCenter: parent.verticalCenter
                   color: link.secondary ? Metrics.themed("popup.text.secondary") : Theme.text
                   font.family: Metrics.fontFamily; font.variableAxes: Metrics.opsz(font.pixelSize); font.pixelSize: link.fontSize }
        }
        MouseArea { id: lmouse; anchors.fill: parent; hoverEnabled: true; onClicked: link.clicked() }
    }
    ContextMenu { id: appMenu; targetScreen: start.targetScreen; overPanel: true }

    // Test hooks (tests/shell-kwin).
    function testPowerMenu() { openPowerMenu() }
    function testAccountMenu() { openAccountMenu() }
    function testCloseMenus() { powerMenu.close(); accountMenu.close(); appMenu.close(); viewMenu.close() }

    function showAppMenu(item, storageId, name, pinnedTile) {
        const pinned = StartPins.isPinned(storageId)
        appMenu.items = [
            { text: Strings.tr(pinned ? "Unpin from Start" : "Pin to Start"), iconSource: Metrics.assets + "menu-icons/win11-explorer-pin.svg",
              action: () => pinned ? StartPins.unpin(storageId) : StartPins.pin(storageId) },
            { text: Strings.tr(ShellSettings.isPinned(storageId) ? "Unpin from taskbar" : "Pin to taskbar"), iconSource: Metrics.assets + "menu-icons/win11-explorer-pin.svg",
              action: () => ShellSettings.isPinned(storageId) ? ShellSettings.unpin(storageId) : ShellSettings.pin(storageId) },
        ]
        appMenu.anchorX = start.screenX + item.mapToItem(start.panel, item.width / 2, 0).x
        appMenu.open()
    }
}

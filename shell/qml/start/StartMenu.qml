// SPDX-License-Identifier: GPL-3.0-or-later
// Start (S01–S03) as measured on the reference (start.* in design/tokens.json, scale 1):
// 642 × 726, search box, Pinned (6 columns of 96 × 84, three rows), Recommended (two columns of
// 56 px rows), All apps (alphabetical list with letter rows of 40 px; Category and Grid views
// through allView), footer of 63 px with the account and power menus.
import QtQuick
import Fenestra.Shell

ShellPopup {
    id: start
    width: Metrics.startWidth; height: Metrics.startHeight
    signal searchRequested(string text)
    property bool allApps: false
    property string allView: "list"   // list (reference) | category | grid
    property var pins: StartPins.apps
    readonly property int recommendedColumns: Metrics.tok("start.recommended.columns", 2)
    property var recent: RecentFiles.items.slice(0, 3 * recommendedColumns)
    readonly property int inset: Metrics.startInset
    readonly property int contentWidth: width - 2 * inset

    onOpened: { allApps = false; header.forceActiveFocus() }
    // Pinned <-> All apps: the new page slides in 40 px with a fade (PopupMotion "page", assumption
    // in design/motion.json); not while Start itself opens or closes.
    onAllAppsChanged: {
        if (!shown || moving) return pageMotion.reset()
        pageMotion.target = allApps ? all : home
        pageMotion.kind = allApps ? "page-forward" : "page-back"
        pageMotion.enter()
    }
    PopupMotion { id: pageMotion }

    // ---- Search box ---------------------------------------------------------------------------
    Item {
        id: header
        width: parent.width; height: Metrics.tok("start.pinned.y", 141)
        focus: true
        // Typing in Start goes to Search, like the search box.
        Keys.onPressed: (e) => {
            if (e.text.length === 1 && e.text.trim() !== "" && !(e.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
                start.searchRequested(e.text); e.accepted = true
            }
        }
        Rectangle {
            x: start.inset; y: Metrics.tok("start.search.y", 33)
            width: start.contentWidth; height: Metrics.tok("start.search.height", 32)
            radius: height / 2
            // Home: the box has the keyboard focus (dark fill, colour icon, caret); All apps: it
            // does not (lighter fill, monochrome glyph, brighter placeholder), as on the reference.
            readonly property string state_: start.allApps ? "start.search.idle" : "start.search"
            color: Metrics.themed(state_ + ".fill")
            border.color: Metrics.themed(state_ + ".border")
            Image { x: Metrics.tok("start.search.icon.x", 15); anchors.verticalCenter: parent.verticalCenter; width: 18; height: 18
                    visible: !start.allApps
                    source: ShellSettings.searchIcon !== "" ? ShellSettings.searchIcon : Metrics.assets + "search/search.svg"
                    sourceSize: Qt.size(18 * Screen.devicePixelRatio, 18 * Screen.devicePixelRatio) }
            SymbolicIcon { x: Metrics.tok("start.search.icon.x", 15); anchors.verticalCenter: parent.verticalCenter; size: 18
                           visible: start.allApps; monochrome: true; src: Metrics.assets + "search/search-glyph.svg" }
            Text {
                x: Metrics.tok("start.search.text.x", 44); anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: Metrics.tok("start.text.offset", 0)
                text: Strings.tr("Search for apps, settings, and documents")
                color: Metrics.themed(parent.state_ + ".text"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
            }
            Rectangle {
                id: caret
                x: Metrics.tok("start.search.text.x", 44); y: 6; width: 1; height: 19
                color: Metrics.themed("start.search.caret")
                visible: !start.allApps && start.shown && blink.on
                Timer { id: blink; property bool on: true; interval: 530; repeat: true
                        running: !start.allApps && start.shown && !Motion.reduced
                        onRunningChanged: on = true; onTriggered: on = !on }
            }
            MouseArea { anchors.fill: parent; onClicked: start.searchRequested("") }
        }
        SectionHeader {
            x: Metrics.startHeaderInset; y: Metrics.tok("start.header.y", 105)
            width: start.width - 2 * Metrics.startHeaderInset - 2
            title: Strings.tr(start.allApps ? "All apps" : "Pinned")
            action: Strings.tr(start.allApps ? "Back" : "All apps")
            chevron: start.allApps ? "left" : "right"
            titleOffset: Metrics.tok("start.header.title.offset", -1)
            onActionClicked: start.allApps = !start.allApps
        }
    }

    // ---- Home: Pinned and Recommended -----------------------------------------------------------
    Item {
        id: home
        visible: !start.allApps
        transform: pageMotion.target === home ? pageMotion.shift : []
        y: header.height; width: parent.width; height: footer.y - y
        Flickable {
            id: pinnedArea
            x: start.inset; width: start.contentWidth
            height: Metrics.startPinnedRows * Metrics.startTileHeight
            contentHeight: pinnedGrid.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Grid {
                id: pinnedGrid
                columns: Metrics.startColumns
                Repeater {
                    model: start.pins
                    delegate: AppTile {
                        required property var modelData
                        storageId: modelData.storageId; name: modelData.name; icon: modelData.icon
                        onActivated: { Apps.launch(storageId); start.close() }
                        onContextRequested: (x, y) => start.showAppMenu(this, storageId, name, true)
                    }
                }
            }
        }
        SectionHeader {
            x: Metrics.startHeaderInset; y: Metrics.tok("start.recommended.y", 424) - header.height
            width: start.width - 2 * Metrics.startHeaderInset - 2
            title: Strings.tr("Recommended")
        }
        Grid {
            x: start.inset; y: Metrics.tok("start.recommended.items.y", 461) - header.height
            columns: start.recommendedColumns
            Repeater {
                model: start.recent
                delegate: Rectangle {
                    required property var modelData
                    width: start.contentWidth / start.recommendedColumns; height: Metrics.tok("start.recommended.row", 56)
                    radius: Metrics.controlRadius
                    color: rm.containsMouse ? Metrics.themed("start.hover") : "transparent"
                    Image { x: Metrics.tok("start.recommended.icon.x", 32); anchors.verticalCenter: parent.verticalCenter; width: 32; height: 32
                            sourceSize: Qt.size(32 * Screen.devicePixelRatio, 32 * Screen.devicePixelRatio)
                            source: "image://icon/" + modelData.icon }
                    Column {
                        x: Metrics.tok("start.recommended.text.x", 77); anchors.verticalCenter: parent.verticalCenter
                        anchors.verticalCenterOffset: Metrics.tok("start.text.offset", 0)
                        width: parent.width - x - 8
                        Text { width: parent.width; height: 16; text: modelData.name; elide: Text.ElideMiddle; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                        Text { width: parent.width; height: 16; text: modelData.age; color: Metrics.themed("start.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                    }
                    MouseArea { id: rm; anchors.fill: parent; hoverEnabled: true; onClicked: { RecentFiles.open(modelData.uri); start.close() } }
                }
            }
        }
        Text {
            visible: start.recent.length === 0
            x: Metrics.startHeaderInset; y: Metrics.tok("start.recommended.items.y", 461) - header.height + 8
            text: Strings.tr("Your recent files will appear here.")
            color: Metrics.themed("start.text.secondary"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
        }
    }

    // ---- All apps ------------------------------------------------------------------------------
    Item {
        id: all
        visible: start.allApps
        transform: pageMotion.target === all ? pageMotion.shift : []
        y: Metrics.tok("start.all.y", 141); width: parent.width; height: footer.y - y
        readonly property int row: Metrics.tok("start.all.row", 40)
        // Alphabetical list (the reference): a letter row before each initial, 40 px rows.
        ListView {
            id: alphaList
            visible: start.allView === "list"
            anchors.fill: parent
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: start.allApps && start.allView === "list" ? AllApps : null
            section.property: "letter"
            section.delegate: Item {
                required property string section
                width: alphaList.width; height: all.row
                Text {
                    // Centred on the icon column.
                    x: Metrics.tok("start.all.icon.x", 65) + Metrics.tok("start.all.icon", 24) / 2 - width / 2
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: Metrics.tok("start.text.offset", 0)
                    text: section; color: Theme.text
                    font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                }
            }
            delegate: Item {
                id: appRow
                required property var model
                width: alphaList.width; height: all.row
                Rectangle {
                    x: start.inset; width: start.contentWidth; height: parent.height
                    radius: Metrics.controlRadius
                    color: lm.containsMouse ? Metrics.themed("start.hover") : "transparent"
                }
                readonly property int iconSize: Metrics.tok("start.all.icon", 24)
                Image { x: Metrics.tok("start.all.icon.x", 65); anchors.verticalCenter: parent.verticalCenter
                        width: appRow.iconSize; height: appRow.iconSize
                        sourceSize: Qt.size(appRow.iconSize * Screen.devicePixelRatio, appRow.iconSize * Screen.devicePixelRatio)
                        source: "image://icon/" + appRow.model.icon }
                Text { x: Metrics.tok("start.all.text.x", 109); anchors.verticalCenter: parent.verticalCenter
                       anchors.verticalCenterOffset: Metrics.tok("start.text.offset", 0)
                       width: start.width - start.inset - x - 8; elide: Text.ElideRight
                       text: appRow.model.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                MouseArea {
                    id: lm; x: start.inset; width: start.contentWidth; height: parent.height; hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: (e) => e.button === Qt.RightButton ? start.showAppMenu(appRow, appRow.model.storageId, appRow.model.name, false)
                                                                   : (Apps.launch(appRow.model.storageId), start.close())
                }
            }
        }
        Flickable {
            visible: start.allView !== "list"
            anchors.fill: parent
            contentHeight: allLoader.item ? allLoader.item.height + 16 : 0
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Loader {
                id: allLoader
                width: parent.width
                active: start.allApps && start.allView !== "list"
                sourceComponent: start.allView === "category" ? categoryView : gridView
            }
        }
        Component {
            id: categoryView
            Grid {
                x: start.inset + 12; columns: 3; columnSpacing: 29; rowSpacing: 18
                Repeater {
                    model: AllApps.groups()
                    delegate: Column {
                        required property var modelData
                        spacing: 11
                        Rectangle {
                            width: 154; height: 154; radius: 8
                            color: cm.containsMouse ? Metrics.themed("start.hover") : Metrics.themed("start.button.fill")
                            border.color: Metrics.themed("start.button.border")
                            Grid {
                                anchors.centerIn: parent; columns: 2; spacing: 36
                                Repeater {
                                    model: modelData.apps.slice(0, 4)
                                    delegate: Image { required property var modelData; width: 32; height: 32
                                        sourceSize: Qt.size(32 * Screen.devicePixelRatio, 32 * Screen.devicePixelRatio)
                                        source: "image://icon/" + modelData.icon }
                                }
                            }
                            MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; onClicked: { start.allView = "list" } }
                        }
                        Text { width: 154; horizontalAlignment: Text.AlignHCenter; text: Strings.tr(modelData.name); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                    }
                }
            }
        }
        Component {
            id: gridView
            Grid {
                x: start.inset; columns: Metrics.startColumns
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
    }

    // ---- Footer: account and power ---------------------------------------------------------
    Rectangle {
        id: footer
        // Inside the 1 px border: a 1 px divider, then 63 px (start.footer.height).
        x: 1; y: parent.height - 1 - Metrics.startFooterHeight
        width: parent.width - 2; height: Metrics.startFooterHeight
        bottomLeftRadius: Metrics.flyoutRadius - 1; bottomRightRadius: Metrics.flyoutRadius - 1
        color: Metrics.themed("start.footer.fill")
        Rectangle { y: -1; width: parent.width; height: 1; color: Metrics.themed("start.footer.divider") }
        readonly property int buttonInset: Metrics.tok("start.footer.inset", 53) - 1
        Rectangle {
            id: account
            x: footer.buttonInset; y: Metrics.tok("start.footer.button.y", 11)
            width: accountRow.implicitWidth + 24; height: 40
            radius: Metrics.controlRadius
            color: am2.containsMouse ? Metrics.themed("start.hover") : "transparent"
            Row {
                id: accountRow
                x: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 12
                Avatar { size: Metrics.tok("start.footer.avatar", 32) }
                Text { anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: Metrics.tok("start.text.offset", 0)
                       text: UserInfo.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            }
            MouseArea { id: am2; anchors.fill: parent; hoverEnabled: true; onClicked: start.openAccountMenu() }
        }
        Rectangle {
            id: powerButton
            anchors { right: parent.right; rightMargin: footer.buttonInset }
            y: Metrics.tok("start.footer.button.y", 11)
            width: 40; height: 40; radius: Metrics.controlRadius
            color: pm.containsMouse ? Metrics.themed("start.hover") : "transparent"
            Accessible.name: Strings.tr("Power")
            SymbolicIcon { anchors.centerIn: parent; size: 19; src: Metrics.assets + "power/3.svg" }
            MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true; onClicked: start.openPowerMenu() }
        }
    }

    // Menus above the footer buttons (menu.power.gap / menu.account.* in design/tokens.json):
    // the gap counts from the taskbar, so add Start's own place above it.
    function aboveFooter(extra) { return Metrics.flyoutGap + start.height - (footer.y + powerButton.y) + extra }
    function openPowerMenu() {
        powerMenu.anchorX = start.screenX + powerButton.mapToItem(start.panel, powerButton.width / 2, 0).x
        powerMenu.open()
    }
    function openAccountMenu() {
        accountMenu.anchorLeft = start.screenX + Metrics.tok("menu.account.x", 15)
        accountMenu.open()
    }
    ContextMenu {
        id: powerMenu
        targetScreen: start.targetScreen
        gap: start.aboveFooter(Metrics.tok("menu.power.gap", 4))
        onDismissed: start.requestActivate()
        items: [
            { text: Strings.tr("Lock"), iconSource: Metrics.assets + "power/1.svg", iconSize: 19, action: () => { start.close(); Session.lock() } },
        ].concat(Session.canSuspend ? [{ text: Strings.tr("Sleep"), iconSource: Metrics.assets + "power/4.svg", iconSize: 19, action: () => { start.close(); Session.suspend() } }] : [], [
            { text: Strings.tr("Shut down"), iconSource: Metrics.assets + "power/3.svg", iconSize: 19, action: () => { start.close(); Session.powerOff() } },
            { text: Strings.tr("Restart"), iconSource: Metrics.assets + "power/2.svg", iconSize: 19, action: () => { start.close(); Session.reboot() } },
        ])
    }
    // Account card (362 × 128): switch user and sign out on top, picture, name, account kind and
    // a link to the account settings.
    Flyout {
        id: accountMenu
        motion: "menu"
        targetScreen: start.targetScreen
        gap: start.aboveFooter(Metrics.tok("menu.account.gap", 6))
        padding: 0
        background.color: Metrics.themed("menu.fill")
        background.border.color: Metrics.themed("menu.border")
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
                // 14 px like the reference (dark-100-09-account-menu: 913-992 × 854-863).
                anchors.right: parent.right; anchors.rightMargin: 16; y: 12
                text: Strings.tr("Sign out"); fontSize: Metrics.fontBody
                onClicked: { accountMenu.close(); start.close(); Session.logout() }
            }
            Avatar { x: 17; y: 55; size: Metrics.tok("menu.account.avatar", 58) }
            Column {
                x: 87; y: 55
                Item { width: nameText.implicitWidth; height: 24
                       Text { id: nameText; y: -3; text: UserInfo.fullName || UserInfo.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold } }
                Text { height: 17; text: Strings.tr("Local account"); color: Metrics.themed("menu.header"); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
                Text {
                    height: 17; text: Strings.tr("Manage my account"); color: Theme.accentText
                    font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
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
        color: lmouse.containsMouse ? Metrics.themed("menu.hover") : "transparent"
        Row {
            id: linkRow
            x: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 7
            SymbolicIcon { visible: link.iconSource.toString() !== ""; size: 18; src: link.iconSource; anchors.verticalCenter: parent.verticalCenter }
            Text { text: link.text; anchors.verticalCenter: parent.verticalCenter
                   color: link.secondary ? Metrics.themed("menu.header") : Theme.text
                   font.family: Metrics.fontFamily; font.pixelSize: link.fontSize }
        }
        MouseArea { id: lmouse; anchors.fill: parent; hoverEnabled: true; onClicked: link.clicked() }
    }
    ContextMenu { id: appMenu; targetScreen: start.targetScreen }

    // Test hooks (tests/shell-kwin).
    function testPowerMenu() { openPowerMenu() }
    function testAccountMenu() { openAccountMenu() }
    function testCloseMenus() { powerMenu.close(); accountMenu.close(); appMenu.close() }

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

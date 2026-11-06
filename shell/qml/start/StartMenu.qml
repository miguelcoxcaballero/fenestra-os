// SPDX-License-Identifier: GPL-3.0-or-later
// Start (S01–S03), the layout of arc/menulayouts/eleven.js + windowsStartHome.js: 832 × 864,
// search pill, Pinned (8 columns, 2 rows or all), Recommended (6 recent files), All apps
// (Category / Grid / List), footer with the account and power menus.
import QtQuick
import Fenestra.Shell

ShellPopup {
    id: start
    width: 832; height: 864
    signal searchRequested(string text)
    property bool allApps: false
    property bool pinnedExpanded: false
    property string allView: "category"   // category | grid | list
    property var pins: StartPins.apps
    property var recent: RecentFiles.items.slice(0, 6)

    onOpened: { allApps = false; pinnedExpanded = false; header.forceActiveFocus() }

    Item {
        id: header
        width: parent.width; height: 56
        focus: true
        // Typing in Start goes to Search, like the search pill.
        Keys.onPressed: (e) => {
            if (e.text.length === 1 && e.text.trim() !== "" && !(e.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
                start.searchRequested(e.text); e.accepted = true
            }
        }
        Rectangle {
            x: 32; y: 16; width: parent.width - 64; height: 32
            radius: 16
            color: Theme.dark ? Qt.rgba(28 / 255, 28 / 255, 28 / 255, 0.75) : Qt.rgba(1, 1, 1, 0.85)
            border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.08)
            Image { x: 14; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; source: Metrics.assets + "search/search.svg"
                    sourceSize: Qt.size(16 * Screen.devicePixelRatio, 16 * Screen.devicePixelRatio) }
            Text {
                x: 40; anchors.verticalCenter: parent.verticalCenter
                text: Strings.tr("Search for apps, settings, and documents")
                color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 13
            }
            MouseArea { anchors.fill: parent; onClicked: start.searchRequested("") }
        }
    }

    // ---- Home page ------------------------------------------------------------------------
    Flickable {
        id: home
        visible: !start.allApps
        x: 0; y: header.height + 16; width: parent.width; height: parent.height - y - footer.height
        contentHeight: homeColumn.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: homeColumn
            width: parent.width
            spacing: 0
            SectionHeader {
                x: 56; width: parent.width - 112
                title: Strings.tr("Pinned")
                action: start.pinnedExpanded ? Strings.tr("Show less") + "  ⌃" : Strings.tr("All") + "  ›"
                onActionClicked: start.pinnedExpanded ? start.pinnedExpanded = false : start.allApps = true
            }
            Item { width: 1; height: 10 }
            Grid {
                x: 44
                columns: 8
                Repeater {
                    model: start.pinnedExpanded ? start.pins : start.pins.slice(0, 16)
                    delegate: AppTile {
                        required property var modelData
                        storageId: modelData.storageId; name: modelData.name; icon: modelData.icon
                        onActivated: { Apps.launch(storageId); start.close() }
                        onContextRequested: (x, y) => start.showAppMenu(this, storageId, name, true)
                    }
                }
            }
            Item {
                visible: start.pins.length > 16 && !start.pinnedExpanded
                width: parent.width; height: 24
                Text { anchors.centerIn: parent; text: Strings.tr("Show all") + "  ⌄"; color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                MouseArea { anchors.fill: parent; onClicked: start.pinnedExpanded = true }
            }
            Item { width: 1; height: 24; visible: !start.pinnedExpanded }
            SectionHeader {
                visible: !start.pinnedExpanded
                x: 56; width: parent.width - 112
                title: Strings.tr("Recommended")
            }
            Item { width: 1; height: 12; visible: !start.pinnedExpanded }
            Grid {
                visible: !start.pinnedExpanded
                x: 44; columns: 3; columnSpacing: 8; rowSpacing: 4
                Repeater {
                    model: start.recent
                    delegate: Rectangle {
                        required property var modelData
                        width: 236; height: 52
                        radius: Metrics.controlRadius
                        color: rm.containsMouse ? Theme.hover : "transparent"
                        Image { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 32; height: 32
                                sourceSize: Qt.size(32 * Screen.devicePixelRatio, 32 * Screen.devicePixelRatio)
                                source: "image://icon/" + modelData.icon }
                        Column {
                            x: 54; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 62
                            Text { width: parent.width; text: modelData.name; elide: Text.ElideMiddle; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                            Text { width: parent.width; text: modelData.age; color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                        }
                        MouseArea { id: rm; anchors.fill: parent; hoverEnabled: true; onClicked: { RecentFiles.open(modelData.uri); start.close() } }
                    }
                }
            }
            Text {
                visible: !start.pinnedExpanded && start.recent.length === 0
                x: 56; topPadding: 8
                text: Strings.tr("Your recent files will appear here.")
                color: Theme.textSecondary; font.family: Metrics.fontFamily; font.pixelSize: 12
            }
            Item { width: 1; height: 16 }
        }
    }

    // ---- All apps -------------------------------------------------------------------------
    Item {
        id: all
        visible: start.allApps
        x: 0; y: header.height + 16; width: parent.width; height: parent.height - y - footer.height
        Item {
            x: 56; width: parent.width - 112; height: 28
            Rectangle {
                width: 70; height: 24; radius: Metrics.controlRadius
                anchors.verticalCenter: parent.verticalCenter
                color: bm.containsMouse ? Theme.hover : (Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.7))
                Text { anchors.centerIn: parent; text: "‹  " + Strings.tr("Back"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                MouseArea { id: bm; anchors.fill: parent; hoverEnabled: true; onClicked: start.allApps = false }
            }
            SectionHeader {
                anchors.right: parent.right; width: 260
                title: ""
                action: Strings.tr("View") + ": " + Strings.tr(start.allView === "category" ? "Category" : start.allView === "grid" ? "Grid" : "List") + "  ⌄"
                onActionClicked: start.allView = start.allView === "category" ? "grid" : start.allView === "grid" ? "list" : "category"
            }
        }
        Flickable {
            y: 40; width: parent.width; height: parent.height - 40
            contentHeight: allLoader.item ? allLoader.item.height + 16 : 0
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Loader {
                id: allLoader
                width: parent.width
                active: start.allApps
                sourceComponent: start.allView === "category" ? categoryView : start.allView === "grid" ? gridView : listView
            }
        }
        Component {
            id: categoryView
            Grid {
                x: 45; columns: 4; columnSpacing: 29; rowSpacing: 18
                Repeater {
                    model: AllApps.groups()
                    delegate: Column {
                        required property var modelData
                        spacing: 11
                        Rectangle {
                            width: 154; height: 154; radius: 8
                            color: Theme.dark ? Qt.rgba(1, 1, 1, cm.containsMouse ? 0.07 : 0.04) : Qt.rgba(1, 1, 1, cm.containsMouse ? 0.8 : 0.6)
                            border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.05)
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
                        Text { width: 154; horizontalAlignment: Text.AlignHCenter; text: Strings.tr(modelData.name); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                    }
                }
            }
        }
        Component {
            id: gridView
            Grid {
                x: 44; columns: 8
                Repeater {
                    model: AllApps
                    delegate: AppTile {
                        required property var model
                        tileWidth: 80
                        storageId: model.storageId; name: model.name; icon: model.icon
                        onActivated: { Apps.launch(storageId); start.close() }
                        onContextRequested: start.showAppMenu(this, storageId, name, false)
                    }
                }
            }
        }
        Component {
            id: listView
            Grid {
                x: 44; columns: 2; columnSpacing: 20
                Repeater {
                    model: AllApps
                    delegate: Rectangle {
                        required property var model
                        width: 352; height: 40
                        radius: Metrics.controlRadius
                        color: lm.containsMouse ? Theme.hover : "transparent"
                        Image { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 24; height: 24
                                sourceSize: Qt.size(24 * Screen.devicePixelRatio, 24 * Screen.devicePixelRatio)
                                source: "image://icon/" + model.icon }
                        Text { x: 46; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 54; elide: Text.ElideRight
                               text: model.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                        MouseArea {
                            id: lm; anchors.fill: parent; hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: (e) => e.button === Qt.RightButton ? start.showAppMenu(parent, model.storageId, model.name, false)
                                                                           : (Apps.launch(model.storageId), start.close())
                        }
                    }
                }
            }
        }
    }

    // ---- Footer: account and power ---------------------------------------------------------
    Rectangle {
        id: footer
        anchors.bottom: parent.bottom
        width: parent.width; height: 64
        bottomLeftRadius: Metrics.flyoutRadius; bottomRightRadius: Metrics.flyoutRadius
        color: Theme.dark ? Qt.rgba(0, 0, 0, 0.21) : Qt.rgba(0, 0, 0, 0.03)
        Rectangle { width: parent.width; height: 1; color: Theme.dark ? Qt.rgba(0, 0, 0, 0.2) : Qt.rgba(0, 0, 0, 0.06) }
        Rectangle {
            id: account
            x: 48; anchors.verticalCenter: parent.verticalCenter
            width: accountRow.implicitWidth + 20; height: 40
            radius: Metrics.controlRadius
            color: am2.containsMouse ? Theme.hover : "transparent"
            Row {
                id: accountRow
                x: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 12
                Rectangle {
                    width: 32; height: 32; radius: 16; clip: true
                    color: Theme.dark ? "#3a3a3a" : "#d6d6d6"
                    Image { anchors.fill: parent; source: UserInfo.picture; visible: UserInfo.picture !== ""; fillMode: Image.PreserveAspectCrop }
                    SymbolicIcon { anchors.centerIn: parent; size: 18; visible: UserInfo.picture === ""; name: "avatar-default-symbolic" }
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: UserInfo.name; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
            }
            MouseArea {
                id: am2; anchors.fill: parent; hoverEnabled: true
                onClicked: { accountMenu.anchorX = account.mapToItem(null, account.width / 2, 0).x; accountMenu.open() }
            }
        }
        Rectangle {
            id: powerButton
            anchors { right: parent.right; rightMargin: 48; verticalCenter: parent.verticalCenter }
            width: 40; height: 40; radius: Metrics.controlRadius
            color: pm.containsMouse ? Theme.hover : "transparent"
            Accessible.name: Strings.tr("Power")
            SymbolicIcon { anchors.centerIn: parent; src: Metrics.assets + "power/3.svg" }
            MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true
                onClicked: { powerMenu.anchorX = powerButton.mapToItem(null, powerButton.width / 2, 0).x; powerMenu.open() } }
        }
    }

    ContextMenu {
        id: powerMenu
        targetScreen: start.targetScreen
        onDismissed: start.requestActivate()
        items: [
            { text: Strings.tr("Lock"), iconSource: Metrics.assets + "power/1.svg", action: () => { start.close(); Session.lock() } },
            { text: Strings.tr("Sleep"), iconSource: Metrics.assets + "power/4.svg", action: () => { start.close(); Session.suspend() } },
            { text: Strings.tr("Shut down"), iconSource: Metrics.assets + "power/3.svg", action: () => { start.close(); Session.powerOff() } },
            { text: Strings.tr("Restart"), iconSource: Metrics.assets + "power/2.svg", action: () => { start.close(); Session.reboot() } },
        ]
    }
    ContextMenu {
        id: accountMenu
        targetScreen: start.targetScreen
        items: [
            { text: Strings.tr("Change account settings"), icon: "fenestra-settings", action: () => { start.close(); Apps.runCommand("fenestra-settings --page yourinfo") } },
            "-",
            { text: Strings.tr("Sign out"), iconSource: Metrics.assets + "power/0.svg", action: () => { start.close(); Session.logout() } },
            { text: Strings.tr("Switch user"), iconSource: Metrics.assets + "power/7.svg", action: () => { start.close(); Session.switchUser() } },
        ]
    }
    ContextMenu { id: appMenu; targetScreen: start.targetScreen }

    // Test hooks (tests/shell-kwin).
    function testPowerMenu() { powerMenu.anchorX = powerButton.mapToItem(null, powerButton.width / 2, 0).x; powerMenu.open() }
    function testAccountMenu() { accountMenu.anchorX = account.mapToItem(null, account.width / 2, 0).x; accountMenu.open() }
    function testCloseMenus() { powerMenu.close(); accountMenu.close(); appMenu.close() }

    function showAppMenu(item, storageId, name, pinnedTile) {
        const pinned = StartPins.isPinned(storageId)
        appMenu.items = [
            { text: Strings.tr(pinned ? "Unpin from Start" : "Pin to Start"), iconSource: Metrics.assets + "menu-icons/win11-explorer-pin.svg",
              action: () => pinned ? StartPins.unpin(storageId) : StartPins.pin(storageId) },
            { text: Strings.tr(ShellSettings.isPinned(storageId) ? "Unpin from taskbar" : "Pin to taskbar"), iconSource: Metrics.assets + "menu-icons/win11-explorer-pin.svg",
              action: () => ShellSettings.isPinned(storageId) ? ShellSettings.unpin(storageId) : ShellSettings.pin(storageId) },
        ]
        appMenu.anchorX = item.mapToItem(null, item.width / 2, 0).x
        appMenu.open()
    }
}

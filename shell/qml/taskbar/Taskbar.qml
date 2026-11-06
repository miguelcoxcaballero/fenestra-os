// SPDX-License-Identifier: GPL-3.0-or-later
// Taskbar (B01–B11). Values of the GNOME layer: 48 px, #000402 / #f3f3f3 at 63 %, 1 px top border,
// icons centred (or left), weather at the left end, search box, tray and clock at the right.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: bar
    required property var targetScreen
    // Set by Main.qml: Start / Search open on this screen (their buttons stay lit, the box shows the query).
    property bool startOpen: false
    property bool searchOpen: false
    // Screen x of the search box's (or button's) left edge: the Search flyout lines up with it.
    readonly property real searchBoxX: tasks.x + searchButton.x + searchButton.boxX

    height: Metrics.taskbarHeight
    color: "transparent"
    // Shown only once the screen is set: a layer surface binds to its output when it is created.
    visible: false
    Component.onCompleted: { ShellUtil.placeOnScreen(bar, targetScreen.name); visible = true }
    LayerShell.Window.scope: "fenestra-taskbar"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft
                               | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: Metrics.taskbarHeight   // maximized windows stop above it
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    readonly property bool leftAligned: ShellSettings.taskbarAlignment === "left"

    Rectangle {
        anchors.fill: parent
        color: Metrics.themed("taskbar.fill")
        Rectangle { width: parent.width; height: 1; color: Metrics.themed("taskbar.border") }
    }

    // Empty-area right click (B07): Task Manager, Taskbar settings.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: (m) => bar.openBarMenu(m.x)
    }

    // B05: weather at the left end; hidden with left-aligned icons or without data.
    WeatherButton {
        id: weather
        anchors { left: parent.left; leftMargin: 4; verticalCenter: parent.verticalCenter }
        visible: !bar.leftAligned && ShellSettings.showWeather && available
        targetScreen: bar.targetScreen
    }

    Row {
        id: tasks
        height: parent.height
        spacing: 0   // the cells carry the spacing (taskbar.button.pitch)
        x: bar.leftAligned ? 12 : Math.round((parent.width - width) / 2)
        Behavior on x { enabled: bar.visible; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        TaskButton {
            id: startButton
            anchors.verticalCenter: parent.verticalCenter
            iconSource: ShellSettings.startIcon !== "" ? ShellSettings.startIcon : Metrics.assets + "branding/start-button.svg"
            label: Strings.tr("Start")
            checked: bar.startOpen
            // No context menu on Start (B07).
            onClicked: ShellState.toggleStart(bar.targetScreen, startButton.mapToItem(null, width / 2, 0).x)
        }
        SearchButton {
            id: searchButton
            anchors.verticalCenter: parent.verticalCenter
            checked: bar.searchOpen
            query: Search.text
            onClicked: ShellState.toggleSearch(bar.targetScreen, searchButton.mapToItem(null, width / 2, 0).x)
        }
        Repeater {
            id: taskRepeater
            model: TaskbarModel
            delegate: TaskButton {
                id: task
                required property int index
                required property var model
                anchors.verticalCenter: parent ? parent.verticalCenter : undefined
                iconName: model.icon
                label: model.name
                windowCount: model.windowCount
                focused: model.active
                attention: model.demandsAttention
                onClicked: { preview.close(); TaskbarModel.activate(index) }
                onMiddleClicked: TaskbarModel.newInstance(index)
                onRightClicked: {
                    preview.close()
                    const items = []
                    // Jump list: the app's recent files (recently-used.xbel, by the MIME types it opens).
                    const mimes = model.storageId !== "" ? (Apps.info(model.storageId).mimeTypes || []) : []
                    const recent = RecentFiles.items.filter(f => mimes.indexOf(f.mime) >= 0).slice(0, 5)
                    if (recent.length) {
                        items.push({ header: Strings.tr("Recent") })
                        for (const f of recent)
                            items.push({ text: f.name.replace(/\.[^.]+$/, ""), icon: f.icon, action: () => RecentFiles.open(f.uri) })
                        items.push("-")
                    }
                    if (model.storageId !== "")
                        items.push({ text: model.name, icon: model.icon, action: () => TaskbarModel.newInstance(index) })
                    if (model.storageId !== "")
                        items.push({ text: Strings.tr(model.pinned ? "Unpin from taskbar" : "Pin to taskbar"),
                                     iconSource: Metrics.assets + "menu-icons/win11-explorer-pin.svg",
                                     action: () => TaskbarModel.togglePinned(index) })
                    if (model.windowCount > 0)
                        items.push({ text: Strings.tr(model.windowCount > 1 ? "Close all windows" : "Close window"),
                                     iconSource: Metrics.assets + "menu-icons/win11-menu-cancel.svg",
                                     action: () => TaskbarModel.closeAll(index) })
                    appMenu.items = items
                    appMenu.anchorX = task.mapToItem(null, task.width / 2, 0).x
                    appMenu.open()
                }
                onHoveredChanged: {
                    if (hovered && model.windowCount > 0) {
                        previewTimer.owner = task
                        previewTimer.restart()
                    } else if (!hovered) {
                        previewTimer.stop()
                        closeTimer.restart()
                    }
                }
            }
        }
    }

    // Tray area and clock (B08); the system icons and their flyouts come with H4.
    Tray {
        id: tray
        targetScreen: bar.targetScreen
        anchors { right: parent.right; rightMargin: 12; top: parent.top; bottom: parent.bottom }
        onQuickSettingsRequested: (x) => ShellState.toggleQuickSettings(bar.targetScreen, x)
        onCalendarRequested: (x) => ShellState.toggleCalendar(bar.targetScreen, x)
    }

    // "Show desktop" corner (B09): the last pixels at the right end.
    MouseArea {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: 8
        hoverEnabled: true
        Accessible.name: Strings.tr("Show desktop")
        onClicked: WindowsModel.toggleShowDesktop()
        Rectangle { anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            width: 1; height: 16; color: Theme.separator; visible: parent.containsMouse }
    }

    // Test hooks (tests/shell-kwin, through the test probe's Eval).
    function testButton(i) { return taskRepeater.itemAt(i) }
    function testBarMenu(x) { openBarMenu(x) }
    // B07: opens at the pointer, its bottom-left corner on the taskbar's top edge (no gap).
    function openBarMenu(x) { barMenu.anchorX = -1; barMenu.anchorLeft = x; barMenu.open() }
    function testPreview(i) {
        const b = taskRepeater.itemAt(i)
        preview.windows = b.model.windows
        preview.icon = b.model.icon
        preview.anchorX = b.mapToItem(null, b.width / 2, 0).x
        preview.open()
    }
    function testOverflow() { tray.testOverflow() }
    function testMenuOfTray(row) { tray.testMenu(row) }
    function testCloseFlyouts() { preview.close(); appMenu.close(); barMenu.close(); tray.testCloseFlyouts() }

    Timer {
        id: previewTimer
        property var owner
        interval: Metrics.previewDelay
        onTriggered: if (owner && owner.hovered) {
            preview.windows = owner.model.windows
            preview.icon = owner.model.icon
            preview.anchorX = owner.mapToItem(null, owner.width / 2, 0).x
            preview.open()
        }
    }
    Timer { id: closeTimer; interval: 300; onTriggered: if (!preview.keepOpen && !(previewTimer.owner && previewTimer.owner.hovered)) preview.close() }

    TaskPreview { id: preview; targetScreen: bar.targetScreen; onKeepOpenChanged: if (!keepOpen) closeTimer.restart() }
    // Jump list (B02): 296 px wide like the reference, centred on the button, 12 px above the bar.
    ContextMenu { id: appMenu; targetScreen: bar.targetScreen; minWidth: Metrics.tok("jumplist.width", 296) }
    ContextMenu {
        id: barMenu
        targetScreen: bar.targetScreen
        // Rows of 35 px touching the border, a full-width line between them (menu.taskbar.*).
        gap: 0
        padding: 1
        separatorMargin: 0
        itemHeight: Metrics.tok("menu.taskbar.item.height", 35)
        items: [
            { text: Strings.tr("Task Manager"), iconSource: Metrics.assets + "menu-icons/win11-menu-tvmonitor.svg", action: () => Apps.runCommand("fenestra-taskmgr") },
            "-",
            { text: Strings.tr("Taskbar settings"), iconSource: Metrics.assets + "menu-icons/win11-menu-settings.svg", action: () => Apps.runCommand("fenestra-settings --page taskbar") },
        ]
    }
}

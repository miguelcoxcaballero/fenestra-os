// SPDX-License-Identifier: GPL-3.0-or-later
// Taskbar (B01–B11). Values of the GNOME layer: 48 px, #000402 / #f3f3f3 at 63 %, 1 px top border,
// icons centred (or left), weather at the left end, search box, tray and clock at the right.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: bar
    required property var targetScreen

    screen: targetScreen
    height: Metrics.taskbarHeight
    color: "transparent"
    visible: true
    LayerShell.Window.scope: "fenestra-taskbar"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft
                               | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: Metrics.taskbarHeight   // maximized windows stop above it
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    readonly property bool leftAligned: ShellSettings.taskbarAlignment === "left"

    Rectangle {
        anchors.fill: parent
        color: Theme.taskbar
        Rectangle { width: parent.width; height: 1; color: Theme.taskbarBorder }
    }

    // Empty-area right click (B07): Task Manager, Taskbar settings.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: (m) => { barMenu.anchorX = m.x; barMenu.open() }
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
        spacing: 4
        x: bar.leftAligned ? 12 : Math.round((parent.width - width) / 2)
        Behavior on x { enabled: bar.visible; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        TaskButton {
            id: startButton
            anchors.verticalCenter: parent.verticalCenter
            iconSource: Metrics.assets + "branding/start-button.svg"
            label: Strings.tr("Start")
            // No context menu on Start (B07).
            onClicked: ShellState.toggleStart(bar.targetScreen, startButton.mapToItem(null, width / 2, 0).x)
        }
        SearchButton {
            id: searchButton
            anchors.verticalCenter: parent.verticalCenter
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
    Row {
        id: tray
        anchors { right: parent.right; rightMargin: 12; top: parent.top; bottom: parent.bottom }
        spacing: 4
        Clock { anchors.verticalCenter: parent.verticalCenter }
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
    function testBarMenu(x) { barMenu.anchorX = x; barMenu.open() }
    function testPreview(i) {
        const b = taskRepeater.itemAt(i)
        preview.windows = b.model.windows
        preview.anchorX = b.mapToItem(null, b.width / 2, 0).x
        preview.open()
    }
    function testCloseFlyouts() { preview.close(); appMenu.close(); barMenu.close() }

    Timer {
        id: previewTimer
        property var owner
        interval: 400
        onTriggered: if (owner && owner.hovered) {
            preview.windows = owner.model.windows
            preview.anchorX = owner.mapToItem(null, owner.width / 2, 0).x
            preview.open()
        }
    }
    Timer { id: closeTimer; interval: 300; onTriggered: if (!preview.keepOpen && !(previewTimer.owner && previewTimer.owner.hovered)) preview.close() }

    TaskPreview { id: preview; targetScreen: bar.targetScreen; onKeepOpenChanged: if (!keepOpen) closeTimer.restart() }
    ContextMenu { id: appMenu; targetScreen: bar.targetScreen }
    ContextMenu {
        id: barMenu
        targetScreen: bar.targetScreen
        items: [
            { text: Strings.tr("Task Manager"), icon: "org.fenestra.TaskManager", action: () => Apps.runCommand("fenestra-taskmgr") },
            { text: Strings.tr("Taskbar settings"), icon: "fenestra-settings", action: () => Apps.runCommand("fenestra-settings --page taskbar") },
        ]
    }
}

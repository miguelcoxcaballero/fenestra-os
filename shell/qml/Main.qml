// SPDX-License-Identifier: GPL-3.0-or-later
// One wallpaper and one taskbar per screen. Every surface is a wlr-layer-shell surface
// (LayerShellQt), so KWin keeps them out of the window list, Alt+Tab and the work area.
import QtQuick
import Fenestra.Shell

Item {
    id: root

    // Per screen (B10); objects are reachable from the test probe as root.screensView.objectAt(i).
    property alias screensView: perScreen
    Instantiator {
        id: perScreen
        model: Qt.application.screens
        delegate: QtObject {
            required property var modelData
            property Wallpaper wallpaper: Wallpaper { targetScreen: modelData }
            property Taskbar taskbar: Taskbar { targetScreen: modelData }
            property StartMenu start: StartMenu {
                targetScreen: modelData
                onSearchRequested: (text) => { close(); search.openWith(text) }
            }
            property SearchFlyout search: SearchFlyout { targetScreen: modelData }
        }
    }

    // Start / Search for the screen that asked (taskbar button) or the first screen (Super, D-Bus).
    function screenObjects(screen) {
        for (let i = 0; i < perScreen.count; ++i) {
            const o = perScreen.objectAt(i)
            if (!screen || o.modelData.name === screen.name) return o
        }
        return perScreen.objectAt(0)
    }
    Connections {
        target: ShellState
        function onStartRequested(screen, x) {
            const o = root.screenObjects(screen)
            o.search.close()
            o.start.toggle()
        }
        function onSearchRequested(screen, x) {
            const o = root.screenObjects(screen)
            o.start.close()
            o.search.shown ? o.search.close() : o.search.openWith("")
        }
    }
    Connections {
        target: ShellControl
        function onToggleStartRequested() { ShellState.toggleStart(null, -1) }
        function onToggleSearchRequested() { ShellState.toggleSearch(null, -1) }
    }

    Component.onCompleted: {
        // Marker for tests/shell-kwin and tests/perf: the first surfaces exist.
        console.info("FENESTRA_SHELL_READY screens=" + Qt.application.screens.length
                     + " windowManagement=" + WindowsModel.available)
    }

    Connections {
        target: WindowsModel
        function onCountChanged() { console.info("FENESTRA_SHELL_WINDOWS count=" + WindowsModel.count) }
        function onAvailableChanged() { console.info("FENESTRA_SHELL_WM available=" + WindowsModel.available) }
    }
    Connections {
        target: TaskbarModel
        function onModelReset() { console.info("FENESTRA_SHELL_TASKBAR buttons=" + TaskbarModel.rowCount()) }
    }
}

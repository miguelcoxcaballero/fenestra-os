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
        }
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

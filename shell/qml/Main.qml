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
            property Desktop desktop: Desktop { targetScreen: modelData }
            property Taskbar taskbar: Taskbar { targetScreen: modelData }
            property StartMenu start: StartMenu {
                targetScreen: modelData
                onSearchRequested: (text) => { close(); search.openWith(text) }
            }
            property SearchFlyout search: SearchFlyout { targetScreen: modelData }
            property QuickSettings quick: QuickSettings { targetScreen: modelData; rightAligned: true }
            property NotificationCenter center: NotificationCenter { targetScreen: modelData; rightAligned: true }
            property Osd osd: Osd { targetScreen: modelData }
            // Snipping overlay (Q04): one per output, toolbar on the first; opened by Snip.start().
            property SnipOverlay snip: SnipOverlay {
                targetScreen: modelData
                hasToolbar: modelData.name === Qt.application.screens[0].name
            }
        }
    }

    // One per session, on the first screen: banners, Ctrl+Alt+Del, the administrator prompt.
    // (Held by a QtObject like the per-screen surfaces: a Window declared directly as a child of
    // the root Item was hidden again right after being shown.)
    property QtObject sessionSurfaces: QtObject {
        property Toasts toasts: Toasts { targetScreen: Qt.application.screens[0] }
        property SecurityScreen security: SecurityScreen { targetScreen: Qt.application.screens[0] }
        property ConsentDialog consent: ConsentDialog { }
        property SnapLayouts snap: SnapLayouts { targetScreen: Qt.application.screens[0] }
        property FirstLoginCurtain curtain: FirstLoginCurtain { }
    }
    readonly property var toastsWindow: sessionSurfaces.toasts
    readonly property var securityScreen: sessionSurfaces.security
    readonly property var snapLayouts: sessionSurfaces.snap

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
        target: ShellState
        function onQuickSettingsRequested(screen, x) { const o = root.screenObjects(screen); o.center.close(); o.quick.toggle() }
        function onCalendarRequested(screen, x) { const o = root.screenObjects(screen); o.quick.close(); o.center.toggle() }
    }
    Connections {
        target: Shortcuts
        function onOsd(kind, value) { root.screenObjects(null).osd.show(kind, value) }
        function onSecurityScreenRequested() { root.securityScreen.open() }
        function onNotificationCenterRequested() { ShellState.toggleCalendar(null, -1) }
        function onQuickSettingsRequested() { ShellState.toggleQuickSettings(null, -1) }
        function onSearchRequested() { ShellState.toggleSearch(null, -1) }
        function onSnapLayoutsRequested() { root.snapLayouts.open() }
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
        // Not in the migrator's boot test (its HOME is a throwaway directory).
        if (WindowsModel.available) ShellUtil.markSessionOk()
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

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
            property Taskbar taskbar: Taskbar { targetScreen: modelData; startOpen: start.shown; searchOpen: search.shown }
            property StartMenu start: StartMenu {
                targetScreen: modelData
                onSearchRequested: (text) => { close(); search.openWith(text) }
            }
            // Search lines up with the taskbar's search box (or button), like the reference.
            property SearchFlyout search: SearchFlyout { targetScreen: modelData; anchorLeft: taskbar.searchBoxX }
            property QuickSettings quick: QuickSettings { targetScreen: modelData; rightAligned: true }
            property NotificationCenter center: NotificationCenter { targetScreen: modelData; rightAligned: true }
            property Osd osd: Osd { targetScreen: modelData }
            property InputSwitcher inputSwitcher: InputSwitcher { targetScreen: modelData; rightAligned: true }
            property EmojiPanel emoji: EmojiPanel { targetScreen: modelData }
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
        // The laptop maker's banner (Samsung Galaxy Book Fn+F11 / Fn+F9), on the first screen.
        property OemBanner oem: OemBanner { targetScreen: Qt.application.screens[0] }
    }
    readonly property var oemBanner: sessionSurfaces.oem
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
        function onInputSwitcherRequested(screen) {
            const o = root.screenObjects(screen)
            if (o.inputSwitcher.shown) o.inputSwitcher.close(); else o.inputSwitcher.present(5000)
        }
        function onCalendarRequested(screen, x) { const o = root.screenObjects(screen); o.quick.close(); o.center.toggle() }
    }
    Connections {
        target: Shortcuts
        function onOsd(kind, value) { root.screenObjects(null).osd.show(kind, value); LockOsd.progress(kind, value) }
        function onSecurityScreenRequested() { root.securityScreen.open() }
        function onNotificationCenterRequested() { ShellState.toggleCalendar(null, -1) }
        function onQuickSettingsRequested() { ShellState.toggleQuickSettings(null, -1) }
        function onEmojiRequested() { const p = root.screenObjects(null).emoji; if (p.shown) p.close(); else p.present() }
        function onNextKeyboardRequested() {
            if (KeyboardStatus.count < 2) return
            KeyboardStatus.next()
            root.screenObjects(null).inputSwitcher.present(Metrics.osdTimeout)
        }
        function onSearchRequested() { ShellState.toggleSearch(null, -1) }
        function onSnapLayoutsRequested() { root.snapLayouts.open() }
    }
    // Firmware hotkeys: the maker's banner on Samsung Galaxy Books (as SamsungSystemSupportOSD),
    // a Windows-style banner on other laptops.
    Connections {
        target: PerformanceMode
        function onKeyChanged(profile) {
            const glyph = profile === "performance" ? "\uec4a" : profile === "balanced" ? "\uec49" : "\uec48"
            // On the lock screen too (LockOsd: the shell's own surfaces are hidden while locked).
            LockOsd.text(PerformanceMode.vendor === "samsung-galaxybook" ? "oem" : "performance", PerformanceMode.label(profile), glyph,
                         PerformanceMode.vendor === "samsung-galaxybook" ? PerformanceMode.icon(profile, true) : "")
            if (PerformanceMode.vendor === "samsung-galaxybook")
                root.oemBanner.show(PerformanceMode.label(profile), PerformanceMode.icon(profile, Theme.dark), glyph)
            else
                root.screenObjects(null).osd.showText("performance", PerformanceMode.label(profile), glyph)
        }
    }
    Connections {
        target: KbdBacklight
        function onKeyChanged(level) {
            if (KbdBacklight.vendor === "samsung-galaxybook")
                LockOsd.text("oem", KbdBacklight.samsungLabel(level), "\ued39", KbdBacklight.samsungIcon(true))
            else
                LockOsd.progress("keyboard", KbdBacklight.percent)
            if (KbdBacklight.vendor === "samsung-galaxybook")
                root.oemBanner.show(KbdBacklight.samsungLabel(level), KbdBacklight.samsungIcon(Theme.dark), "\ued39")
            else
                root.screenObjects(null).osd.show("keyboard", KbdBacklight.percent)
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

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
    Component.onCompleted: { ShellUtil.placeOnScreen(bar, targetScreen.name); visible = true; ShellUtil.setBlurItems(bar, [blurPin], 0) }
    // Keeps KWin's blur effect active at all times (a 1 px region nobody sees). Without it, when the
    // last blurred popup closed KWin moved windows onto hardware overlay planes and that switch dropped
    // a frame: every window flickered once (i915 "Atomic commit failed: EBUSY", Meteor Lake). The
    // session also starts KWin with KWIN_USE_OVERLAYS=0 (session/libexec/fenestra-session).
    Item { id: blurPin; x: 0; y: 0; width: 1; height: 1 }
    onVisibleChanged: if (visible) ShellUtil.setBlurItems(bar, [blurPin], 0)
    LayerShell.Window.scope: "dock"   // KWin: a panel (stays when the desktop is shown)
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft
                               | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: Metrics.taskbarHeight   // maximized windows stop above it
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone

    // Taskbar button drag (reorder): the dragged row, the slot under it and its offset from its slot.
    property int dragFrom: -1
    property int dragTo: -1
    property real dragDx: 0
    property bool animateSlots: true
    function dropDragged() {
        if (dragFrom < 0) return
        const pitch = taskRepeater.count > 0 && taskRepeater.itemAt(0) ? taskRepeater.itemAt(0).width : Metrics.taskPitch
        dropAnim.from = dragDx
        dropAnim.to = (dragTo - dragFrom) * pitch
        dropAnim.restart()
    }
    // The dragged button glides into its new slot, then the model moves it there and every offset
    // drops to 0 in the same frame (no visible jump).
    SequentialAnimation {
        id: dropAnim
        property alias from: glide.from
        property alias to: glide.to
        NumberAnimation { id: glide; target: bar; property: "dragDx"; duration: Motion.reduced ? 0 : 250
                          easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] }
        ScriptAction { script: {
            const from = bar.dragFrom, to = bar.dragTo
            bar.animateSlots = false
            bar.dragFrom = -1; bar.dragTo = -1; bar.dragDx = 0
            if (to !== from) TaskbarModel.move(from, to)
            bar.animateSlots = true
        } }
    }

    readonly property bool leftAligned: ShellSettings.taskbarAlignment === "left"
    // The window's real scale (1.5 at 150 %); Screen.devicePixelRatio is the screen's integer one (2).
    readonly property real dpr: scaleProbe.devicePixelRatio > 0 ? scaleProbe.devicePixelRatio : 1
    ShadowLabel { id: scaleProbe; visible: false; width: 1; height: 1 }

    // Material: acrylic over the wallpaper (src/core/acrylic.h: Microsoft's recipe, computed from
    // the wallpaper as the desktop draws it); the flat fallback colour with transparency effects off
    // and while the acrylic is being computed. Measurements: design/tokens.json "taskbar.acrylic.*".
    Rectangle {
        anchors.fill: parent
        color: Metrics.themed("taskbar.fill")
        Image {
            id: acrylic
            anchors.fill: parent
            visible: ShellSettings.transparency && status === Image.Ready
            asynchronous: true
            cache: false
            smooth: false
            readonly property var scr: bar.targetScreen
            source: !ShellSettings.transparency || !scr ? ""
                    : "image://acrylic/" + (Theme.dark ? "dark" : "light") + "/" + scr.width + "/" + scr.height + "/"
                      + Metrics.taskbarHeight + "/" + (scr.devicePixelRatio || 1) + "/"
                      + encodeURIComponent(WallpaperSource.image !== "" ? decodeURIComponent(WallpaperSource.image.replace(/^file:\/\//, ""))
                                                                       : WallpaperSource.color)
        }
        // Top edge: 1 px at 100 %, 2 device px at 150 % (user-win11 163657: rows 1728-1729), drawn in
        // #767676 at 40 % over the acrylic ((62, 72, 69) over the user's green; #404040 over the VM's
        // flat #1c1c1c fallback, both exactly).
        Rectangle { width: parent.width; height: (Math.ceil(bar.dpr) - 0.001) / bar.dpr; color: Metrics.themed("taskbar.border") }
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
            // Windows draws its own Start logo (lighter than WindowsLogo.svg): traced from the captures.
            iconSource: ShellSettings.startIcon !== "" ? ShellSettings.startIcon
                        : Metrics.assets + "branding/start-button-" + (Theme.dark ? "dark" : "light") + ".svg"
            label: Strings.tr("Start")
            checked: bar.startOpen
            // Windows' Start cell is one device pixel wider than the others (user-win11 160039 /
            // 160049 / 163657 at 150 %: Search, the apps, their plates and dashes all sit 1 px right of
            // the 66 px grid that Start starts), and its 23 px logo sits 1 px below the 24 px box.
            dpr: bar.dpr
            trailing: 1 / bar.dpr
            iconDy: Math.ceil(bar.dpr / 2) / bar.dpr
            plateGrow: 1.999 / bar.dpr
            // No context menu on Start (B07).
            onClicked: ShellState.toggleStart(bar.targetScreen, startButton.mapToItem(null, width / 2, 0).x)
        }
        SearchButton {
            id: searchButton
            anchors.verticalCenter: parent.verticalCenter
            dpr: bar.dpr
            checked: bar.searchOpen
            query: Search.text
            onClicked: ShellState.toggleSearch(bar.targetScreen, searchButton.mapToItem(null, width / 2, 0).x)
        }
        // Task view (B04), after search as in Windows 11: KWin's Overview with the virtual desktops.
        TaskButton {
            id: taskViewButton
            visible: ShellSettings.showTaskView
            dpr: bar.dpr
            anchors.verticalCenter: parent.verticalCenter
            // Windows' two-window picture (dark), traced from dark-100-01-taskbar.png; the glyph in light mode.
            iconSource: Theme.dark ? Metrics.assets + "taskview/task-view-dark.svg" : ""
            iconName: "task-view-symbolic"
            label: Strings.tr("Task view")
            onClicked: KWinIntegration.toggleOverview()
        }
        Repeater {
            id: taskRepeater
            model: TaskbarModel
            delegate: TaskButton {
                id: task
                required property int index
                required property var model
                anchors.verticalCenter: parent ? parent.verticalCenter : undefined
                dpr: bar.dpr
                // Drag sideways to reorder, as Windows 11 (recorded on the reference VM, 2026-11-07): the
                // dragged button leaves its slot and follows the pointer; the buttons it passes slide over
                // to fill the gap (Fluent decelerate (0, 0, 0, 1), ~250 ms: half the way in ~30 ms); on
                // release it glides into the slot under it.
                readonly property bool dragged: bar.dragFrom === index
                // Neighbours: one slot towards the gap while the dragged button is past them.
                readonly property real shiftX: bar.dragFrom < 0 || dragged ? 0
                    : (index > bar.dragFrom && index <= bar.dragTo) ? -width
                    : (index < bar.dragFrom && index >= bar.dragTo) ? width : 0
                z: dragged ? 2 : 0
                transform: Translate {
                    id: slide
                    x: task.dragged ? bar.dragDx : task.shiftX
                    Behavior on x { enabled: !task.dragged && bar.animateSlots && !Motion.reduced
                        NumberAnimation { duration: 250; easing.type: Easing.BezierSpline; easing.bezierCurve: [0, 0, 0, 1, 1, 1] } }
                }
                DragHandler {
                    id: reorder
                    target: null
                    yAxis.enabled: false
                    onActiveChanged: {
                        if (active) { preview.close(); bar.animateSlots = true; bar.dragFrom = task.index; bar.dragTo = task.index; bar.dragDx = 0; return }
                        bar.dropDragged()
                    }
                    onActiveTranslationChanged: if (active) {
                        bar.dragDx = activeTranslation.x
                        bar.dragTo = Math.max(0, Math.min(TaskbarModel.rowCount() - 1, task.index + Math.round(activeTranslation.x / task.width)))
                    }
                }
                iconName: model.icon
                label: model.name
                windowCount: model.windowCount
                windowList: model.windows
                focused: model.active
                attention: model.demandsAttention
                onClicked: { preview.close(); TaskbarModel.activate(index) }
                onMiddleClicked: TaskbarModel.newInstance(index)
                // The button's place for KWin: its windows minimize into it and restore from it
                // (kwin/effects/fenestra-window-motion). Sent once the row stops moving.
                readonly property var minimizeTarget: [tasks.x, x, width, model.windowCount, bar.width]
                onMinimizeTargetChanged: geometryTimer.restart()
                Component.onCompleted: geometryTimer.restart()
                Timer {
                    id: geometryTimer
                    interval: 260   // after the row's 200 ms slide
                    onTriggered: if (task.model.windowCount > 0) TaskbarModel.setButtonGeometry(task.index, task)
                }
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
                onHoveredChanged: bar.taskHovered(task, hovered)
            }
        }
    }

    // Tray area and clock (B08); the system icons and their flyouts come with H4.
    Tray {
        id: tray
        targetScreen: bar.targetScreen
        // The clock's text ends 20 px from the screen's right edge (user-win11 163657: x 2850 of 2880),
        // its cell 8 px after it.
        anchors { right: parent.right; rightMargin: Tokens.v("tray.right", 10.67); top: parent.top; bottom: parent.bottom }
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
    function testPreview(i) { showPreview(taskRepeater.itemAt(i)) }
    function testPreviewHot(slot) { preview.testHot = slot }
    function testOverflow() { tray.testOverflow() }
    function testWidgets(byClick) { weather.testOpenBoard(byClick) }
    function testPreviewShown() { return preview.shown }
    function testBoardState() { const b = weather.testBoard(); return b.shown + " " + b.visible + " " + b.slide + " " + b.width + "x" + b.height }
    function testPrivacyTip() { tray.showPrivacyTip() }
    function testTray(status, ms) { tray.testStatus = status; if (ms) tray.testSetTime(ms) }
    function testMenuOfTray(row) { tray.testMenu(row) }
    function testCloseFlyouts() { preview.close(); appMenu.close(); barMenu.close(); tray.testCloseFlyouts() }

    // Hover previews (B03), as Windows 11 (recorded on the reference VM at 150 %, design/motion.json
    // "preview"): resting on a button with windows opens its preview after motion.preview.delay
    // (400 ms, Windows' mouse hover time); while a preview is up, resting on another button with
    // windows swaps the panel in place after motion.preview.switch (~240 ms, no motion); leaving the
    // buttons and the preview hides it at once after motion.preview.hide (~490 ms).
    function showPreview(b) {
        if (!b || b.windowCount === 0) return
        closeTimer.stop()
        preview.owner = b
        preview.anchorX = b.mapToItem(null, b.width / 2, 0).x
        preview.open()
    }
    function taskHovered(b, hovered) {
        if (hovered && b.windowCount > 0 && bar.dragFrom < 0) {
            previewTimer.owner = b
            previewTimer.interval = preview.shown ? Tokens.v("motion.preview.switch", 240) : Metrics.previewDelay
            previewTimer.restart()
        } else if (!hovered) {
            if (previewTimer.owner === b) previewTimer.stop()
            closeTimer.restart()
        } else if (hovered && preview.shown) {
            // A button without windows: the open preview goes as if the pointer had left.
            closeTimer.restart()
        }
    }
    Timer {
        id: previewTimer
        property var owner
        interval: Metrics.previewDelay
        onTriggered: if (owner && owner.hovered) bar.showPreview(owner)
    }
    Timer {
        id: closeTimer
        interval: Tokens.v("motion.preview.hide", 490)
        onTriggered: if (!preview.keepOpen && !(preview.owner && preview.owner.hovered)) preview.close()
    }

    TaskPreview { id: preview; targetScreen: bar.targetScreen; onKeepOpenChanged: if (!keepOpen) closeTimer.restart() }
    // Jump list (B02): 296 px wide like the reference, centred on the button, 12 px above the bar.
    ContextMenu { id: appMenu; targetScreen: bar.targetScreen; minWidth: Metrics.tok("jumplist.width", 296); motion: "taskbar" }
    ContextMenu {
        id: barMenu
        targetScreen: bar.targetScreen
        motion: "taskbar"
        // Rows of 35 px touching the border, a full-width line between them (menu.taskbar.*).
        gap: 0
        padding: 1
        separatorMargin: 0
        itemHeight: Metrics.tok("menu.taskbar.item.height", 35)
        items: [
            { text: Strings.tr("Task Manager"), iconSource: Metrics.assets + "menu-icons/win11-menu-taskmanager.svg", action: () => Apps.runCommand("fenestra-taskmgr") },
            "-",
            { text: Strings.tr("Taskbar settings"), iconSource: Metrics.assets + "menu-icons/shell-settings.svg", action: () => Apps.runCommand("fenestra-settings --page taskbar") },
        ]
    }
}

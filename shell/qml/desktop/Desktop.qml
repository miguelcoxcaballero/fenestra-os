// SPDX-License-Identifier: GPL-3.0-or-later
// Desktop (D01–D03): wallpaper (picture, solid colour or Spotlight) and the icon grid of the
// Desktop folder, column by column from the top-left; click / Ctrl-click / rubber-band selection,
// double-click opens, drag to another cell moves, files dropped from apps are copied here;
// context menus like the Explorer's (Fenestra glyphs).
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: desk
    required property var targetScreen
    readonly property bool primary: targetScreen && Qt.application.screens.length && targetScreen.name === Qt.application.screens[0].name
    color: WallpaperSource.color
    visible: false
    Component.onCompleted: { ShellUtil.placeOnScreen(desk, targetScreen.name); visible = true }
    LayerShell.Window.scope: "fenestra-wallpaper"
    LayerShell.Window.layer: LayerShell.Window.LayerBackground
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand

    property var selection: []          // model rows
    property int renaming: -1
    readonly property int cellW: Metrics.desktopCellWidth
    readonly property int cellH: Metrics.desktopCellHeight
    readonly property int rows: Math.max(1, Math.floor((height - Metrics.taskbarHeight - 2 * Metrics.desktopMargin) / cellH))
    onRowsChanged: if (primary) DesktopModel.setRowsPerColumn(rows)
    function selected(row) { return selection.indexOf(row) >= 0 }

    Image {
        anchors.fill: parent
        source: WallpaperSource.image
        visible: source.toString() !== ""
        fillMode: Image.PreserveAspectCrop   // background-size: cover
        asynchronous: true
        sourceSize: Qt.size(desk.width * Screen.devicePixelRatio, desk.height * Screen.devicePixelRatio)
    }

    Item {
        id: surface
        anchors.fill: parent
        focus: true
        visible: desk.primary   // icons on the primary screen, as before
        Keys.onPressed: (e) => {
            if (e.key === Qt.Key_Delete) DesktopModel.trash(desk.selection)
            else if (e.key === Qt.Key_F2 && desk.selection.length === 1) desk.renaming = desk.selection[0]
            else if (e.key === Qt.Key_Return && desk.selection.length) desk.selection.forEach(r => DesktopModel.open(r))
            else if (e.matches(StandardKey.Copy)) DesktopModel.copy(desk.selection, false)
            else if (e.matches(StandardKey.Cut)) DesktopModel.copy(desk.selection, true)
            else if (e.matches(StandardKey.Paste)) DesktopModel.paste()
            else if (e.matches(StandardKey.SelectAll)) { const all = []; for (let i = 0; i < DesktopModel.rowCount(); ++i) all.push(i); desk.selection = all }
            else return
            e.accepted = true
        }

        // Background: click clears, drag draws the selection rectangle, right click opens the menu.
        MouseArea {
            id: bg
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            property point start
            onPressed: (m) => {
                surface.forceActiveFocus(); desk.requestActivate()
                desk.renaming = -1
                if (m.button === Qt.RightButton) { desk.selection = []; desk.openBackgroundMenu(m.x); return }
                start = Qt.point(m.x, m.y); band.visible = true
                band.x = m.x; band.y = m.y; band.width = 0; band.height = 0
                if (!(m.modifiers & Qt.ControlModifier)) desk.selection = []
            }
            onPositionChanged: (m) => {
                if (!band.visible) return
                band.x = Math.min(start.x, m.x); band.y = Math.min(start.y, m.y)
                band.width = Math.abs(m.x - start.x); band.height = Math.abs(m.y - start.y)
                const sel = []
                for (let i = 0; i < icons.count; ++i) {
                    const it = icons.itemAt(i)
                    if (it && it.x < band.x + band.width && it.x + it.width > band.x && it.y < band.y + band.height && it.y + it.height > band.y) sel.push(i)
                }
                desk.selection = sel
            }
            onReleased: band.visible = false
        }
        Rectangle {
            id: band
            visible: false
            color: Qt.rgba(Theme.accentFill.r, Theme.accentFill.g, Theme.accentFill.b, 0.25)
            border.color: Theme.accentFill
        }

        Repeater {
            id: icons
            model: DesktopModel
            delegate: Item {
                id: icon
                required property int index
                required property var model
                readonly property bool isSelected: desk.selected(index)
                x: Metrics.desktopMargin + model.cell.x * desk.cellW
                y: Metrics.desktopMargin + model.cell.y * desk.cellH
                width: desk.cellW; height: desk.cellH - 4
                Drag.active: drag.drag.active
                Drag.dragType: Drag.Automatic
                Drag.supportedActions: Qt.CopyAction | Qt.MoveAction
                Drag.mimeData: model.isTrash ? ({}) : ({ "text/uri-list": model.url.toString() })
                Accessible.role: Accessible.ListItem
                Accessible.name: model.name
                Rectangle {
                    anchors.fill: parent
                    radius: 2
                    color: icon.isSelected ? Qt.rgba(Theme.accentFill.r, Theme.accentFill.g, Theme.accentFill.b, 0.35)
                           : drag.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
                    border.color: icon.isSelected ? Qt.rgba(Theme.accentFill.r, Theme.accentFill.g, Theme.accentFill.b, 0.7) : "transparent"
                }
                Image {
                    x: (parent.width - Metrics.desktopIcon) / 2; y: 6
                    width: Metrics.desktopIcon; height: Metrics.desktopIcon
                    sourceSize: Qt.size(Metrics.desktopIcon * Screen.devicePixelRatio, Metrics.desktopIcon * Screen.devicePixelRatio)
                    source: icon.model.iconSource !== "" ? icon.model.iconSource : "image://icon/" + icon.model.icon
                }
                Text {
                    visible: desk.renaming !== icon.index
                    x: 2; y: 10 + Metrics.desktopIcon; width: parent.width - 4
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap; maximumLineCount: icon.isSelected ? 4 : 2; elide: Text.ElideRight
                    text: icon.model.name
                    color: "white"
                    style: Text.Outline; styleColor: Qt.rgba(0, 0, 0, 0.35)   // legible on any wallpaper
                    font.family: Metrics.fontFamily; font.pixelSize: 12
                }
                Rectangle {
                    visible: desk.renaming === icon.index
                    x: 0; y: 8 + Metrics.desktopIcon; width: parent.width; height: 22
                    color: "white"; border.color: Theme.accentFill
                    TextInput {
                        id: editor
                        anchors.fill: parent; anchors.margins: 3
                        horizontalAlignment: Text.AlignHCenter
                        color: "black"; font.family: Metrics.fontFamily; font.pixelSize: 12
                        text: icon.model.name
                        onVisibleChanged: if (visible) { forceActiveFocus(); selectAll() }
                        onAccepted: { DesktopModel.rename(icon.index, text); desk.renaming = -1; surface.forceActiveFocus() }
                        Keys.onEscapePressed: { desk.renaming = -1; surface.forceActiveFocus() }
                    }
                }
                MouseArea {
                    id: drag
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    drag.target: dragGhost
                    property bool moved: false
                    onPressed: (m) => {
                        surface.forceActiveFocus(); desk.requestActivate()
                        if (m.modifiers & Qt.ControlModifier)
                            desk.selection = icon.isSelected ? desk.selection.filter(r => r !== icon.index) : desk.selection.concat([icon.index])
                        else if (!icon.isSelected)
                            desk.selection = [icon.index]
                        if (m.button === Qt.RightButton) desk.openItemMenu(icon)
                    }
                    onDoubleClicked: DesktopModel.open(icon.index)
                    onReleased: (m) => {
                        if (dragGhost.x !== 0 || dragGhost.y !== 0) {
                            const p = icon.mapToItem(surface, dragGhost.x + icon.width / 2, dragGhost.y + icon.height / 2)
                            DesktopModel.moveTo(icon.index, Math.max(0, Math.floor((p.x - Metrics.desktopMargin) / desk.cellW)),
                                                Math.max(0, Math.min(desk.rows - 1, Math.floor((p.y - Metrics.desktopMargin) / desk.cellH))))
                        }
                        dragGhost.x = 0; dragGhost.y = 0
                    }
                    Item { id: dragGhost }
                }
            }
        }
        // Files dragged from apps (Files, browsers) are copied to the Desktop folder; Shift moves.
        DropArea {
            anchors.fill: parent
            keys: ["text/uri-list"]
            onDropped: (d) => { if (d.hasUrls) { DesktopModel.dropUrls(d.urls, d.proposedAction === Qt.MoveAction); d.accept() } }
        }
    }

    Connections {
        target: DesktopModel
        function onRenameRequested(row) { desk.selection = [row]; desk.renaming = row }
    }

    ContextMenu { id: menu; targetScreen: desk.targetScreen }
    function glyph(name) { return Metrics.assets + "menu-icons/win11-menu-" + name + ".svg" }
    function openBackgroundMenu(x) {
        const items = [
            { text: Strings.tr("Refresh"), iconSource: glyph("refresh"), action: () => DesktopModel.sortBy("") },
            { text: Strings.tr("Sort by") + ": " + Strings.tr("Name"), iconSource: glyph("sort"), action: () => DesktopModel.sortBy("name") },
            { text: Strings.tr("Sort by") + ": " + Strings.tr("Type"), iconSource: glyph("sort"), action: () => DesktopModel.sortBy("type") },
            { text: Strings.tr("Sort by") + ": " + Strings.tr("Date modified"), iconSource: glyph("sort"), action: () => DesktopModel.sortBy("date") },
            "-",
            { text: Strings.tr("Paste"), iconSource: glyph("paste"), action: () => DesktopModel.paste() },
            { text: Strings.tr("New folder"), iconSource: glyph("newfolder"), action: () => DesktopModel.newFolder() },
        ]
        for (const t of DesktopModel.templates)
            items.push({ text: Strings.tr("New") + ": " + t.replace(/\.[^.]*$/, ""), iconSource: glyph("document"), action: () => DesktopModel.newFromTemplate(t) })
        items.push("-",
            { text: Strings.tr("Open in Terminal"), iconSource: glyph("terminal"), action: () => DesktopModel.openTerminal() },
            "-",
            { text: Strings.tr("Display settings"), iconSource: glyph("tvmonitor"), action: () => Apps.runCommand("fenestra-settings --page display") },
            { text: Strings.tr("Personalize"), iconSource: glyph("personalize"), action: () => Apps.runCommand("fenestra-settings --page personalization") })
        menu.items = items
        menu.anchorX = x
        menu.open()
    }
    function openItemMenu(icon) {
        const rows = desk.selection
        if (icon.model.isTrash) {
            menu.items = [{ text: Strings.tr("Open"), iconSource: glyph("folderopen"), action: () => DesktopModel.open(icon.index) }]
        } else {
            menu.items = [
                { text: Strings.tr("Open"), iconSource: glyph("folderopen"), action: () => rows.forEach(r => DesktopModel.open(r)) },
                "-",
                { text: Strings.tr("Cut"), iconSource: glyph("cut"), action: () => DesktopModel.copy(rows, true) },
                { text: Strings.tr("Copy"), iconSource: glyph("copy"), action: () => DesktopModel.copy(rows, false) },
                { text: Strings.tr("Rename"), iconSource: glyph("rename"), action: () => desk.renaming = icon.index },
                { text: Strings.tr("Delete"), iconSource: glyph("delete"), action: () => DesktopModel.trash(rows) },
                "-",
                { text: Strings.tr("Copy as path"), iconSource: glyph("copypath"), action: () => DesktopModel.copyAsPath(rows) },
                { text: Strings.tr("Properties"), iconSource: glyph("properties"), action: () => DesktopModel.properties(rows) },
            ]
        }
        menu.anchorX = icon.mapToItem(null, icon.width / 2, 0).x
        menu.open()
    }
    // Test hooks (tests/shell-kwin).
    function testBackgroundMenu() { openBackgroundMenu(desk.width / 2) }
    function testItemMenu(row) { desk.selection = [row]; openItemMenu(icons.itemAt(row)) }
    function testCloseMenu() { menu.close() }
}

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
    // Shown only once the wallpaper picture is decoded: mapping at once showed the fallback colour
    // (grey) for a moment at every start. A missing / broken picture, or 2 s, shows it anyway.
    readonly property bool wallpaperReady: WallpaperSource.image === "" || wallpaper.status === Image.Ready
                                           || wallpaper.status === Image.Error
    function reveal() { if (!visible) { ShellUtil.placeOnScreen(desk, targetScreen.name); visible = true } }
    onWallpaperReadyChanged: if (wallpaperReady) reveal()
    Component.onCompleted: { if (wallpaperReady) reveal(); else revealTimer.start() }
    Timer { id: revealTimer; interval: 2000; onTriggered: desk.reveal() }
    LayerShell.Window.scope: "desktop"   // KWin: a desktop window (stays when the desktop is shown)
    LayerShell.Window.layer: LayerShell.Window.LayerBackground
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand

    property var selection: []          // model rows
    property int renaming: -1
    // Grid of Windows 11 at 100 % (design/tokens.json "desktop.*" and their _sources): 96 × 124 cells
    // from the top-left corner, 48 px icon centred 7 px down, label (Segoe UI 9 pt, 15 px lines,
    // two lines and "…" unless selected) 54 px below the icon's top, with a blurred black shadow.
    // Windows does not scale all of it with the display: at 150 % (solid/dark-150-01) the icons
    // stay 7 device px from the top, rows are 190 px apart (124 × 1.5 + 4) and label lines 25 px
    // (not 22.5): those are device-pixel values, computed here for the screen's scale.
    // The window's fractional scale (Screen.devicePixelRatio is the screen's, rounded up).
    readonly property real dpr: scaleProbe.devicePixelRatio > 0 ? scaleProbe.devicePixelRatio : 1
    ShadowLabel { id: scaleProbe; visible: false; width: 1; height: 1 }
    // Column width in device px: 96 at 100 % (VM), 113 at 150 % (the user's Windows, 163657: bin
    // centred at x 56.5); like the rows, Windows' grid grows by a fixed amount per 100 % of scale.
    readonly property real cellW: Math.round(Metrics.desktopCellWidth + Metrics.tok("desktop.cell.width.perscale", 34) * Math.max(0, dpr - 1)) / dpr
    // Row pitch in device px, measured: 124 at 100 % (VM) and 153 at 150 % (the user's Windows,
    // 163657: labels at 88 and 241). Windows' grid does not scale with the DPI; it grows by 58 px
    // per 100 % of extra scale.
    readonly property real cellH: Math.round(Metrics.desktopCellHeight + Metrics.tok("desktop.cell.height.perscale", 58) * Math.max(0, dpr - 1)) / dpr
    readonly property real iconTop: Metrics.tok("desktop.icon.top", 7) / dpr
    readonly property real labelTop: iconTop + Metrics.desktopIcon + Metrics.tok("desktop.label.gap", 3)
    readonly property int labelFontDevice: Math.round(Metrics.tok("desktop.label", 12) * dpr)
    readonly property int labelLineDevice: dpr <= 1 ? Math.round(Metrics.tok("desktop.label.line", 15) * dpr)
                                         : dpr <= 1.5 ? Math.round(Metrics.tok("desktop.label.line", 15) + 20 * (dpr - 1))
                                         : Math.round(labelFontDevice * Metrics.tok("desktop.label.line.150", 25) / 18)
    readonly property real labelLine: labelLineDevice / dpr
    readonly property int labelInset: Metrics.tok("desktop.label.inset", 2)
    readonly property int itemInset: Metrics.tok("desktop.item.inset", 2)
    readonly property int itemTop: Metrics.tok("desktop.item.top", 2)
    readonly property int rows: Math.max(1, Math.floor((height - Metrics.taskbarHeight - 2 * Metrics.desktopMargin) / cellH))
    onRowsChanged: if (primary) DesktopModel.setRowsPerColumn(rows)
    function selected(row) { return selection.indexOf(row) >= 0 }

    Image {
        id: wallpaper
        anchors.fill: parent
        source: WallpaperSource.image
        visible: source.toString() !== ""
        fillMode: Image.PreserveAspectCrop   // background-size: cover
        asynchronous: true
        sourceSize: Qt.size((desk.targetScreen ? desk.targetScreen.width : desk.width) * Screen.devicePixelRatio,
                            (desk.targetScreen ? desk.targetScreen.height : desk.height) * Screen.devicePixelRatio)
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
                width: desk.cellW; height: desk.cellH
                Drag.active: drag.drag.active
                Drag.dragType: Drag.Automatic
                Drag.supportedActions: Qt.CopyAction | Qt.MoveAction
                Drag.mimeData: model.isTrash ? ({}) : ({ "text/uri-list": model.url.toString() })
                Accessible.role: Accessible.ListItem
                Accessible.name: model.name
                // Hover / selection: the item's box (icon + label), square like Windows' desktop.
                Rectangle {
                    x: desk.itemInset; y: desk.itemTop
                    width: parent.width - 2 * desk.itemInset
                    height: desk.labelTop - desk.itemTop + Math.max(1, label.lineCount) * desk.labelLine + Metrics.tok("desktop.item.bottom", 4)
                    color: icon.isSelected ? Tokens.v("desktop.item.selected", "#4dcce8ff")
                           : drag.containsMouse ? Tokens.v("desktop.item.hover", "#33e5f3ff") : "transparent"
                    border.color: icon.isSelected ? Tokens.v("desktop.item.selected.border", "#8c99d1ff") : "transparent"
                }
                Image {
                    x: (parent.width - Metrics.desktopIcon) / 2; y: desk.iconTop
                    width: Metrics.desktopIcon; height: Metrics.desktopIcon
                    // File-type icons: Windows' 48 px drawing (fewer, darker lines and a border, as Files
                    // shows it), scaled to the screen; the 64 px+ drawings are much fainter. Folders, the
                    // bin and app icons keep their large drawings (they match the user's capture).
                    readonly property bool fileType: !icon.model.isDir && !icon.model.isTrash && icon.model.iconSource === ""
                                                     && !String(icon.model.path).endsWith(".desktop")
                    readonly property real request: fileType ? Metrics.desktopIcon : Metrics.desktopIcon * Screen.devicePixelRatio
                    sourceSize: Qt.size(request, request)
                    smooth: true
                    mipmap: false
                    source: icon.model.iconSource !== "" ? icon.model.iconSource : "image://icon/" + icon.model.icon
                }
                ShadowLabel {
                    id: label
                    visible: desk.renaming !== icon.index
                    x: desk.labelInset - pad; y: desk.labelTop - pad
                    width: parent.width - 2 * desk.labelInset + 2 * pad
                    height: implicitHeight
                    z: 1   // its shadow may overhang the next cell
                    text: icon.model.name
                    maxLines: icon.isSelected ? 0 : Metrics.tok("desktop.label.lines", 2)
                    lineHeightDevice: desk.labelLineDevice
                    color: "white"
                    // Windows' icon title font (SPI_GETICONTITLELOGFONT): Segoe UI 9 pt, not the
                    // UI's Segoe UI Variable; hinted at its device size (ShadowLabel lays it out there).
                    font.family: Tokens.v("desktop.label.font", "Segoe UI"); font.pixelSize: Metrics.tok("desktop.label", 12)
                    font.hintingPreference: Font.PreferFullHinting
                    gamma: Number(Tokens.v("desktop.label.gamma", 1.0))
                    shadowColor: Tokens.v("desktop.label.shadow.color", "#000000")
                    shadowBlur: Number(Tokens.v("desktop.label.shadow.blur", 1.6))
                    shadowX: Number(Tokens.v("desktop.label.shadow.x", 0.5))
                    shadowY: Number(Tokens.v("desktop.label.shadow.y", 1))
                    shadowStrength: Number(Tokens.v("desktop.label.shadow.strength", 1.7))
                }
                Rectangle {
                    visible: desk.renaming === icon.index
                    x: 0; y: desk.labelTop - 4; width: parent.width; height: 22
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

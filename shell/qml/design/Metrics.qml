// SPDX-License-Identifier: GPL-3.0-or-later
// Sizes from design/tokens.json (placeholders until the reference measurements replace them).
pragma Singleton
import QtQuick
import Fenestra.Shell

QtObject {
    readonly property int taskbarHeight: Tokens.px("taskbar.height", 48)
    readonly property int taskButton: Tokens.px("taskbar.button", 44)
    readonly property int taskIcon: Tokens.px("taskbar.icon", 24)
    readonly property int indicatorFocused: Tokens.px("taskbar.indicator.focused", 16)
    readonly property int indicatorUnfocused: Tokens.px("taskbar.indicator.unfocused", 6)
    readonly property int indicatorHeight: Tokens.px("taskbar.indicator.height", 3)
    readonly property int flyoutGap: Tokens.px("flyout.gap", 12)
    readonly property int flyoutEdge: Tokens.px("flyout.edge", 13)
    readonly property int flyoutRadius: Tokens.px("flyout.radius", 8)
    readonly property int controlRadius: Tokens.px("control.radius", 4)
    readonly property int menuItemHeight: Tokens.px("menu.item.height", 36)
    readonly property int menuMinWidth: Tokens.px("menu.width.min", 220)
    readonly property int searchBoxWidth: Tokens.px("search.box.width", 228)
    readonly property int searchBoxHeight: Tokens.px("search.box.height", 32)
    readonly property int startWidth: Tokens.px("start.width", 832)
    readonly property int startHeight: Tokens.px("start.height", 864)
    readonly property int startColumns: Tokens.px("start.pinned.columns", 8)
    readonly property int startTileWidth: Tokens.px("start.pinned.tile.width", 80)
    readonly property int startTileHeight: Tokens.px("start.pinned.tile.height", 69)
    readonly property int startFooterHeight: Tokens.px("start.footer.height", 64)
    readonly property int searchWidth: Tokens.px("search.width", 832)
    readonly property int searchHeight: Tokens.px("search.height", 851)
    readonly property int searchResultsWidth: Tokens.px("search.results.width", 328)
    readonly property int searchPreviewWidth: Tokens.px("search.preview.width", 376)
    readonly property int quickWidth: Tokens.px("quick.width", 400)
    readonly property int quickTileWidth: Tokens.px("quick.tile.width", 104)
    readonly property int quickTileHeight: Tokens.px("quick.tile.height", 48)
    readonly property int quickFooterHeight: Tokens.px("quick.footer.height", 48)
    readonly property int notificationsWidth: Tokens.px("notifications.width", 332)
    readonly property int toastWidth: Tokens.px("toast.width", 362)
    readonly property int calendarDay: Tokens.px("calendar.day", 40)
    readonly property int osdWidth: Tokens.px("osd.width", 192)
    readonly property int osdHeight: Tokens.px("osd.height", 48)
    readonly property int osdGap: Tokens.px("osd.gap", 24)
    readonly property int osdTimeout: Tokens.px("osd.timeout", 1500)
    readonly property int previewDelay: Tokens.px("motion.preview.delay", 400)
    readonly property int desktopIcon: Tokens.px("desktop.icon", 32)
    readonly property int desktopCellWidth: Tokens.px("desktop.cell.width", 76)
    readonly property int desktopCellHeight: Tokens.px("desktop.cell.height", 84)
    readonly property int desktopMargin: Tokens.px("desktop.margin", 8)
    readonly property int snipToolbarTop: Tokens.px("snip.toolbar.top", 8)
    readonly property int snipToolbarRadius: Tokens.px("snip.toolbar.radius", 8)
    readonly property int snipToolbarPadding: Tokens.px("snip.toolbar.padding", 4)
    readonly property int snipToolbarShadow: Tokens.px("snip.toolbar.shadow", 8)
    readonly property int snipButtonWidth: Tokens.px("snip.button.width", 40)
    readonly property int snipButtonHeight: Tokens.px("snip.button.height", 36)
    readonly property int snipButtonRadius: Tokens.px("snip.button.radius", 4)
    readonly property int snipButtonSpacing: Tokens.px("snip.button.spacing", 2)
    readonly property int snipIcon: Tokens.px("snip.icon", 16)
    readonly property int snipSeparatorHeight: Tokens.px("snip.separator.height", 20)
    readonly property real snipDim: Number(Tokens.v("snip.dim.opacity", 0.5))
    readonly property int snipBorderWidth: Tokens.px("snip.border.width", 2)
    readonly property color snipBorderColor: Tokens.v("snip.border.color", "#ffffff")
    readonly property int snipTooltipDelay: Tokens.px("snip.tooltip.delay", 600)
    readonly property string fontFamily: Tokens.v("font.family", "Segoe UI Variable")
    readonly property int fontBody: Tokens.px("font.body", 14)
    readonly property int fontCaption: Tokens.px("font.caption", 12)
    readonly property string assets: "file:///usr/share/fenestra/assets/"

    // Measured colours of the shell's own surfaces: "<key>.dark" / "<key>.light" in tokens.json.
    function col(key) { return Tokens.v(key + (Theme.dark ? ".dark" : ".light"), "#ff00ff") }
    function n(key, fallback) { return Tokens.px(key, fallback) }
    readonly property int quickHeight: Tokens.px("quick.height", 335)
    readonly property int quickMediaHeight: Tokens.px("quick.media.height", 178)
    readonly property int windowButtonWidth: Tokens.px("window.button.width", 45)
    readonly property int windowButtonHeight: Tokens.px("window.button.height", 29)
    readonly property int switcherThumbHeight: Tokens.px("switcher.thumbnail.height", 243)

    // Taskbar, Start, Search and menus as measured on the reference (design/tokens.json _sources).
    // themed("x.fill") reads "x.fill.dark" / "x.fill.light" for the current scheme.
    function themed(key) { return Tokens.v(key + (Theme.dark ? ".dark" : ".light"), "#ff00ff") }
    function tok(key, fallback) { return Tokens.px(key, fallback) }
    // Segoe UI Variable's optical size as DirectWrite picks it: the size in points on the device
    // (14 px at 150 % = 15.75). Qt's default instance is opsz 8 ("Small"), 4 % wider than Windows'
    // text (user-win11 160039: "Search for apps, settings, and documents" 376 device px; opsz 8:
    // 395, opsz 15.75: 380).
    function opsz(px) { return { "opsz": px * 0.75 * Number(Tokens.v("font.opsz.scale", 1.5)) } }
    // Fractional sizes (logical px measured at 150 %: device px / 1.5).
    function num(key, fallback) { return Number(Tokens.v(key, fallback)) }
    readonly property int taskPitch: Tokens.px("taskbar.button.pitch", 44)
    readonly property int startInset: Tokens.px("start.inset", 33)
    readonly property int startHeaderInset: Tokens.px("start.header.inset", 64)
    readonly property int startPinnedRows: Tokens.px("start.pinned.rows", 3)
    readonly property int menuPadding: Tokens.px("menu.padding", 2)
    readonly property int menuIconX: Tokens.px("menu.icon.x", 16)
    readonly property int menuTextX: Tokens.px("menu.text.x", 44)
    readonly property int menuPaddingRight: Tokens.px("menu.padding.right", 16)
}

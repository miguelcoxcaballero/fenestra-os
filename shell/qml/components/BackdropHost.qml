// SPDX-License-Identifier: GPL-3.0-or-later
// The real acrylic (core/backdrop.h) for small shell surfaces that are not Flyouts or ShellPopups
// (OSD banners, notification banners): asks Backdrop for the screen area behind `area`, shows the
// computed image in each Acrylic of `acrylics` (fixed on the screen, so it stays put while the
// surface moves by `shift`) and keeps KWin's blur under the fallback material until it is ready.
//   start() when the surface shows (again), stop() when it hides.
import QtQuick
import Fenestra.Shell

QtObject {
    id: host
    property Window window
    // Logical rectangle on the window's screen that the acrylics can cover (at rest and moving).
    property rect area
    property var acrylics: []
    // Screen top-left of an acrylic at rest (logical px).
    property var originOf: function (a) { return Qt.point(area.x, area.y) }
    property var shift: null
    property int blurRadius: Metrics.flyoutRadius
    property int backdropId: 0
    property int shownId: 0
    property bool acrylicOn: false
    property bool active: false

    function updateBlur() {
        if (!window || !window.visible) return
        if (!ShellSettings.transparency || acrylicOn) { ShellUtil.clearBlur(window); return }
        ShellUtil.setBlurItems(window, acrylics.filter(a => a.visible), blurRadius)
    }
    function show(id) {
        for (const a of acrylics) {
            a.backdrop.area = Backdrop.area(id)
            a.backdrop.origin = originOf(a)
            if (shift) a.backdrop.shift = shift
            a.backdrop.source = "image://backdrop/" + id + "/" + a.backdropRecipe
        }
    }
    function start() {
        active = true
        if (backdropId !== shownId) Backdrop.release(backdropId)
        backdropId = 0
        updateBlur()
        if (!ShellSettings.transparency || !window || acrylics.length === 0 || area.width <= 0) return
        const recipes = []
        for (const a of acrylics) if (recipes.indexOf(a.backdropRecipe) < 0) recipes.push(a.backdropRecipe)
        backdropId = Backdrop.request(window, area, WallpaperSource.image !== "" ? WallpaperSource.image : WallpaperSource.color, recipes)
    }
    function stop() {
        active = false
        Backdrop.release(backdropId)
        if (shownId !== backdropId) Backdrop.release(shownId)
        backdropId = 0; shownId = 0
        acrylicOn = false
        for (const a of acrylics) a.backdrop.source = ""
        if (window) ShellUtil.clearBlur(window)
    }
    property Connections readyConn: Connections {
        target: Backdrop
        function onReady(id, ms) {
            if (id !== host.backdropId || !host.active) return
            host.show(id)
            if (host.shownId !== id) Backdrop.release(host.shownId)
            host.shownId = id
            if (!host.acrylicOn) fadeTimer.restart()
        }
    }
    // After BackdropView's 83 ms fade: KWin's blur is under an opaque acrylic, drop it.
    property Timer fadeTimer: Timer { interval: 100; onTriggered: { host.acrylicOn = true; host.updateBlur() } }
    property Connections settingsConn: Connections {
        target: ShellSettings
        function onTransparencyChanged() { if (host.active) { if (ShellSettings.transparency) host.start(); else host.stop() } }
    }
}

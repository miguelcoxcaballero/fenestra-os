// SPDX-License-Identifier: GPL-3.0-or-later
// Widgets board (B05), opened from the weather at the taskbar's left end.
// Measured on the Windows 11 24H2 VM (build 26100, 1920 x 1080 at 100 %, QMP screendumps):
//   board 12 px from the left and top edges and 12 above the taskbar, 1000 wide, radius 8;
//   slides in from the left edge in ~230 ms (decelerating) and out in ~150 ms (accelerating),
//   clipped by its own left edge; header: date (12 px, secondary) with glyph tops at 36 and
//   "Good afternoon" (20 px semibold) at 55; "Widgets" (14 px semibold) at 161; the weather card
//   at (24, 184), 300 x 146, radius 8, blue sky gradient (47, 86, 153) -> (59, 91, 150), location
//   (14 px semibold, white) at (41, 19), sun 36 px at (20, 56), temperature 46 px at (69, 59).
// Behaviour (WeatherButton.qml): hover opens after ~600 ms; leaving closes it again (~850 ms
// after the pointer leaves if it never entered the board, ~270 ms if it did) unless the weather
// was clicked; a click opens it at once and keeps it until a click outside or Esc.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: board
    property var targetScreen
    property bool shown: false
    // Opened by a click (or clicked while hover-opened): stays until a click outside / Esc.
    property bool pinned: false
    readonly property bool hovered: hover.hovered
    property bool entered: false
    readonly property real slide: sheet.x   // tests
    readonly property real edge: Tokens.v("widgets.margin", 12)
    readonly property real dpr: scaleProbe.devicePixelRatio > 0 ? scaleProbe.devicePixelRatio : 1
    ShadowLabel { id: scaleProbe; parent: board.contentItem; visible: false; width: 1; height: 1 }

    color: "transparent"
    flags: Qt.FramelessWindowHint
    width: Tokens.v("widgets.width", 1000)
    height: Math.max(1, (targetScreen ? targetScreen.height : 1080) - Metrics.taskbarHeight - 2 * edge)
    visible: false
    // "dock": KWin's scale effect animates other names as opening apps (the board has its own slide).
    LayerShell.Window.scope: "dock"
    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorLeft
    LayerShell.Window.margins.left: edge
    LayerShell.Window.margins.top: edge
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: pinned ? LayerShell.Window.KeyboardInteractivityOnDemand
                                                    : LayerShell.Window.KeyboardInteractivityNone

    function open(byClick) {
        if (targetScreen) ShellUtil.placeOnScreen(board, targetScreen.name)
        if (byClick) pinned = true
        if (!shown) { entered = false; shown = true; visible = true; slideIn.restart() }
        if (pinned) requestActivate()
    }
    function close() {
        if (!shown) return
        shown = false; pinned = false
        slideIn.stop(); slideOut.restart()
    }
    onActiveChanged: if (!active && pinned && shown) close()
    onHoveredChanged: if (hovered) entered = true

    Item {
        id: sheet
        width: board.width; height: board.height
        x: -board.width - board.edge
        NumberAnimation { id: slideIn; target: sheet; property: "x"; from: -board.width - board.edge; to: 0
            duration: Motion.reduced ? 0 : Motion.edgeOpen; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.decelerateEdge }
        SequentialAnimation {
            id: slideOut
            NumberAnimation { target: sheet; property: "x"; to: -board.width - board.edge
                duration: Motion.reduced ? 0 : Motion.closeEdge; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.accelerate }
            ScriptAction { script: board.visible = false }
        }
        HoverHandler { id: hover }
        Keys.onEscapePressed: board.close()
        focus: true

        // Material: the flyout acrylic (acrylic.cpp, renderCard) over the wallpaper; the light VM
        // capture's board is (248, 244, 241) over its dark wallpaper.
        // Computed once, off the GUI thread, and kept: it depends only on the wallpaper and the size
        // (it used to be recomputed on every opening, blocking the shell for ~1 s).
        Image {
            anchors.fill: parent
            visible: ShellSettings.transparency && status === Image.Ready
            smooth: false
            asynchronous: true
            cache: true
            readonly property var scr: board.targetScreen
            source: !scr || !ShellSettings.transparency ? ""
                    : "image://acrylic/card/" + (Theme.dark ? "dark" : "light") + "/" + scr.width + "/" + scr.height + "/"
                      + board.dpr + "/" + board.edge + "/" + board.edge + "/" + board.width + "/" + board.height + "/"
                      + Metrics.flyoutRadius + "/0/"
                      + encodeURIComponent(WallpaperSource.image !== "" ? decodeURIComponent(WallpaperSource.image.replace(/^file:\/\//, ""))
                                                                       : WallpaperSource.color)
        }
        Rectangle {
            anchors.fill: parent
            visible: !ShellSettings.transparency
            radius: Metrics.flyoutRadius
            color: Metrics.themed("widgets.fill")
            border.color: Theme.flyoutBorder
        }

        property date now: new Date()
        Text {
            x: 24; y: 22
            text: Qt.locale().toString(sheet.now, "d MMMM")
            color: Theme.textSecondary
            font.family: Metrics.fontFamily; font.pixelSize: 12
        }
        Text {
            x: 24; y: 40
            text: Strings.tr(sheet.now.getHours() < 12 ? "Good morning" : sheet.now.getHours() < 20 ? "Good afternoon" : "Good evening")
            color: Theme.text
            font.family: Metrics.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold
        }
        Text {
            x: 24; y: 150
            text: Strings.tr("Widgets")
            color: Theme.text
            font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold
        }

        // Weather card.
        Rectangle {
            id: card
            x: 24; y: 184; width: 300; height: 146
            radius: Metrics.flyoutRadius
            visible: Weather.available
            gradient: Gradient {
                GradientStop { position: 0; color: Metrics.themed("widgets.weather.top") }
                GradientStop { position: 1; color: Metrics.themed("widgets.weather.bottom") }
            }
            Row {
                x: 20; y: 16; spacing: 6
                SymbolicIcon { anchors.verticalCenter: parent.verticalCenter; size: 12; name: "mark-location-symbolic"; monochrome: true }
                Text { text: Weather.location; color: "white"; font.family: Metrics.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
            }
            Image {
                x: 20; y: 56; width: 36; height: 36
                sourceSize: Qt.size(36 * Screen.devicePixelRatio, 36 * Screen.devicePixelRatio)
                source: Weather.iconName ? "image://icon/" + Weather.iconName : ""
            }
            Text {
                x: 64; y: 46
                text: Weather.temperature
                color: "white"
                font.family: Metrics.fontFamily; font.pixelSize: 46; font.weight: Font.Normal
            }
            Column {
                x: 180; y: 56; width: 104; spacing: 2
                Text { width: parent.width; text: Weather.condition; color: "white"; elide: Text.ElideRight
                       font.family: Metrics.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold }
                Text { width: parent.width; visible: Weather.feelsLike !== ""; text: Strings.tr("Feels like") + " " + Weather.feelsLike
                       color: "white"; opacity: 0.8; elide: Text.ElideRight; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                Text { width: parent.width; visible: Weather.humidity !== ""; text: Strings.tr("Humidity") + " " + Weather.humidity
                       color: "white"; opacity: 0.8; elide: Text.ElideRight; font.family: Metrics.fontFamily; font.pixelSize: 12 }
            }
            Text {
                anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 8 }
                text: Strings.tr("See full forecast")
                color: "white"
                font.family: Metrics.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                onClicked: { board.close(); Weather.openApp() } }
        }
    }
}

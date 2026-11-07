// SPDX-License-Identifier: GPL-3.0-or-later
// A piece of a popup's acrylic (core/backdrop.h): the image computed from what is behind the
// popup, drawn fixed on the SCREEN (the popup slides over its backdrop, as Windows samples it)
// and kept inside this item's rounded rectangle. Fades in over the fallback material when the
// image is ready (83 ms, WinUI's fast fade).
import QtQuick
import QtQuick.Effects
import Fenestra.Shell

Item {
    id: view
    property string source
    // The image's rectangle on the screen and this item's top-left on the screen at rest (logical).
    property rect area
    property point origin
    // The motion's current offset of the popup (PopupMotion.shift).
    property var shift: null
    property real topRadius: Metrics.flyoutRadius
    property real bottomRadius: Metrics.flyoutRadius
    // WinUI acrylic's noise (2 %); 0 for materials without it.
    property real noise: Metrics.num("acrylic.backdrop.noise", 0.02)
    // A new acrylic replaces the shown one without a frame between them (retainWhileLoading);
    // only the first one fades in.
    readonly property bool ready: source !== "" && image.status === Image.Ready
    property bool everReady: false
    onReadyChanged: if (ready) everReady = true
    onSourceChanged: if (source === "") everReady = false
    opacity: ready || (everReady && image.status === Image.Loading) ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: Motion.reduced ? 0 : 83 } }
    layer.enabled: visible
    layer.effect: MultiEffect {
        maskEnabled: true
        maskSource: mask
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
    }
    readonly property real dx: -view.origin.x - (view.shift ? view.shift.x : 0)
    readonly property real dy: -view.origin.y - (view.shift ? view.shift.y : 0)
    // The recipe's image is a coarse grid (core/backdrop.h): scaled bilinearly.
    Image {
        id: image
        x: view.area.x + view.dx
        y: view.area.y + view.dy
        width: view.area.width; height: view.area.height
        source: view.source
        retainWhileLoading: true
        cache: false
        smooth: true
    }
    // Noise at 2 % (WinUI's acrylic noise; the taskbar's texture): 256 device px tiles fixed on the
    // screen from its top-left corner.
    readonly property real dpr: Window.window ? ShellUtil.scaleOf(Window.window) : 1
    Image {
        readonly property real tile: 256 / view.dpr
        x: Math.floor(view.area.x / tile) * tile + view.dx
        y: Math.floor(view.area.y / tile) * tile + view.dy
        width: view.area.width + tile; height: view.area.height + tile
        visible: view.source !== "" && view.noise > 0
        source: visible ? "image://backdrop/noise/" + view.dpr : ""
        fillMode: Image.Tile
        smooth: false
        opacity: view.noise
    }
    Rectangle {
        id: mask
        anchors.fill: parent
        visible: false
        layer.enabled: true
        color: "black"
        topLeftRadius: view.topRadius; topRightRadius: view.topRadius
        bottomLeftRadius: view.bottomRadius; bottomRightRadius: view.bottomRadius
    }
}

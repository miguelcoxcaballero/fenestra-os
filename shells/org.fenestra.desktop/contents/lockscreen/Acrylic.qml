// SPDX-License-Identifier: GPL-3.0-or-later
// Windows' acrylic flyout over the sign-in picture: the blurred picture (under the sign-in dim) with
// a tint over it. Measured on LogonUI's opaque fallback (reference VM, no GPU blur): the network
// flyout is #0C0C0C at 54.5 % over the mean of what it covers, the power menu #191919 at 44 %.
// 1 px light border (white 16 %), radius 8. The backdrop is captured once (the picture is still).
import QtQuick
import QtQuick.Effects

Item {
    id: a
    property real radius: 8
    property color tint: "#0c0c0c"
    property real tintOpacity: 0.545
    property bool border: true
    readonly property real pad: 48
    ShaderEffectSource {
        id: grab
        visible: false
        sourceItem: scene
        live: false
        recursive: false
        width: a.width + 2 * a.pad; height: a.height + 2 * a.pad
        function place() {
            const p = a.mapToItem(scene, -a.pad, -a.pad)
            sourceRect = Qt.rect(p.x, p.y, width, height)
            scheduleUpdate()
        }
    }
    Component.onCompleted: Qt.callLater(grab.place)
    Item {
        id: blurred
        anchors.fill: parent
        visible: false
        layer.enabled: true
        MultiEffect {
            x: -a.pad; y: -a.pad; width: grab.width; height: grab.height
            source: grab
            autoPaddingEnabled: false
            blurEnabled: true; blur: 1.0; blurMax: 64; blurMultiplier: 0.5
        }
    }
    Rectangle { id: mask; anchors.fill: parent; radius: a.radius; visible: false; layer.enabled: true }
    MultiEffect { anchors.fill: parent; source: blurred; maskEnabled: true; maskSource: mask }
    Rectangle { anchors.fill: parent; radius: a.radius; color: "black"; opacity: 0.466 }   // the sign-in dim
    Rectangle { anchors.fill: parent; radius: a.radius; color: a.tint; opacity: a.tintOpacity }
    Rectangle {
        anchors.fill: parent; radius: a.radius; color: "transparent"
        visible: a.border
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.16)
    }
}

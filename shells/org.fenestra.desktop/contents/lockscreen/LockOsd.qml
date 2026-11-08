// SPDX-License-Identifier: GPL-3.0-or-later
// Banners on the lock screen: volume, brightness, keyboard light and performance mode change here
// as on the desktop (Windows shows its volume / brightness flyout over the lock screen too).
// kscreenlocker_greet finds this item by its objectName ("onScreenDisplay") and sets the properties
// below from org.kde.osdService's osdProgress / osdText, which Fenestra Shell sends while the
// session is locked (shell/src/services/lockosd.h). The icon names Fenestra's kind:
//   fenestra-volume | fenestra-volume-muted | fenestra-brightness | fenestra-keyboard   (value 0-100)
//   fenestra-performance:<glyph>:                text banner, Windows' style
//   fenestra-oem:<glyph>:<image path>            the maker's banner (Samsung Galaxy Book)
// Geometry, slider and timing as the shell's own banners (design/tokens.json osd.*, oem.samsung.osd.*).
import QtQuick

Item {
    id: osd
    objectName: "onScreenDisplay"
    anchors.fill: parent

    // Set by kscreenlocker_greet (UnlockApp::osdProgress / osdText).
    property string icon
    property var osdValue: 0
    property int osdMaxValue: 100
    property string osdAdditionalText
    property bool showingProgress: false

    property color accent: "#0078D4"
    readonly property string kind: icon.startsWith("fenestra-") ? icon.slice(9).split(":")[0] : "volume"
    readonly property string glyphArg: icon.split(":")[1] || ""
    readonly property string imageArg: icon.split(":").slice(2).join(":")
    readonly property bool oem: kind === "oem"
    readonly property int value: showingProgress ? Math.round(100 * Number(osdValue) / Math.max(1, osdMaxValue)) : 0
    readonly property string text: showingProgress ? "" : String(osdValue)

    function show() {
        pill.shown = !oem
        banner.shown = oem
        hideTimer.interval = oem ? 2400 : 1500
        hideTimer.restart()
    }
    Timer { id: hideTimer; onTriggered: { pill.shown = false; banner.shown = false } }

    readonly property string glyph: {
        if (kind === "brightness") return ""
        if (kind === "keyboard") return ""
        if (kind === "performance") return glyphArg
        if (kind === "volume-muted") return ""
        return value === 0 ? "" : value < 34 ? "" : value < 67 ? "" : ""
    }

    // Windows' banner: 192 x 48 (text banners as wide as their text), 24 px over the bottom
    // edge's taskbar line, rising and fading in.
    Item {
        id: pill
        property bool shown: false
        readonly property bool textOnly: osd.kind === "performance"
        width: textOnly ? Math.max(48, 16 + 16 + 12 + Math.ceil(label.implicitWidth) + 16) : 192
        height: 48
        x: Math.round((osd.width - width) / 2)
        y: osd.height - 48 - 24 - height + (shown ? 0 : 16)
        opacity: shown ? 1 : 0
        visible: opacity > 0
        Behavior on y { NumberAnimation { duration: pill.shown ? 250 : 167; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: pill.shown ? 167 : 167 } }
        Acrylic { anchors.fill: parent; radius: 8; tint: "#1c1c1c"; tintOpacity: 0.6 }
        Glyph {
            x: 16; anchors.verticalCenter: parent.verticalCenter
            size: 16; glyph: osd.glyph; color: "white"
        }
        // Slider: 104 px track from x 48, 4 px high, accent up to the value, a 20 px thumb with a
        // 10 px accent dot.
        Item {
            visible: !pill.textOnly
            x: 48; width: 104; height: 20
            anchors.verticalCenter: parent.verticalCenter
            Rectangle { y: 8; width: parent.width; height: 4; radius: 2; color: "#a1a1a1" }
            Rectangle { y: 8; width: parent.width * Math.max(0, osd.value) / 100; height: 4; radius: 2; color: osd.accent }
            Rectangle {
                x: parent.width * Math.max(0, osd.value) / 100 - 10; width: 20; height: 20; radius: 10
                color: "#454545"; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.09)
                Rectangle { anchors.centerIn: parent; width: 10; height: 10; radius: 5; color: osd.accent }
            }
        }
        Text {
            visible: !pill.textOnly
            anchors.right: parent.right; anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            text: Math.max(0, osd.value)
            color: "white"; font.family: Fluent.text; font.pixelSize: 14
        }
        Text {
            id: label
            visible: pill.textOnly
            x: 16 + 16 + 12; anchors.verticalCenter: parent.verticalCenter
            text: osd.text
            color: "white"; font.family: Fluent.text; font.pixelSize: 14
        }
    }

    // The maker's banner (Samsung Galaxy Book: performance mode, keyboard light): 44 px high,
    // 14 / 12 px padding, 20 px icon, 75 px over the taskbar line; shown and hidden at once.
    Item {
        id: banner
        property bool shown: false
        visible: shown
        width: 14 + 20 + 12 + Math.floor(oemLabel.implicitWidth) + 14
        height: 44
        x: Math.round((osd.width - width) / 2)
        y: osd.height - 48 - 75 - height
        Acrylic { anchors.fill: parent; radius: 8; border: false; tint: "#202020"; tintOpacity: 0.75 }
        Image {
            visible: osd.imageArg !== ""
            x: 14; y: 12; width: 20; height: 20
            sourceSize: Qt.size(90, 90); smooth: true; mipmap: true
            source: osd.imageArg === "" ? "" : (osd.imageArg.startsWith("/") ? "file://" + osd.imageArg : osd.imageArg)
        }
        Glyph {
            visible: osd.imageArg === ""
            x: 14; y: 12; size: 20; glyph: osd.glyphArg; color: "#fafaff"
        }
        Text {
            id: oemLabel
            x: 14 + 20 + 12; y: 12
            text: osd.text
            color: "#fafaff"; font.family: "Segoe UI"; font.pixelSize: 14
        }
    }
}

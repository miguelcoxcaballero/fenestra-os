// SPDX-License-Identifier: GPL-3.0-or-later
// Clock view, bottom right: Windows' LockApp "NetworkAndBatteryIcon" (network, then battery), with
// the same glyphs as the taskbar (Windows.Internal.UI.NetworkUX / PowerUX: Segoe Fluent battery
// and Wi-Fi glyphs; here the icon pack's white exports of them, cp/white/*.svg). Measured on the
// reference VM (wired, no battery): the network glyph 21 x 21 device px at 150 % (a 14 px em),
// centred 48 px from the right and 28 px over the bottom. The battery is drawn in the taskbar's
// proportion to the network glyph (20 / 16) and 10.5 px after it (the taskbar's 12 px x 14 / 16).
// State: plasma-nm (Wi-Fi bars = signal / 20, wired, offline) and UPower through the
// powermanagement engine (level in 10 % steps, charging, energy saver, critical).
import QtQuick
import QtCore
import org.kde.plasma.plasma5support as P5Support

Row {
    id: icons
    spacing: 10.5
    readonly property string white: StandardPaths.writableLocation(StandardPaths.GenericDataLocation).toString() + "/fenestra/packs/windows-11-user-export/glyphs/cp/white/"
    Loader { id: net; source: "NetworkStatus.qml"; visible: false }
    IconFile {
        size: 14
        anchors.verticalCenter: parent.verticalCenter
        name: !net.item ? "" : net.item.kind === "wired" ? "wired" : net.item.kind === "wifi" ? "wifi-" + net.item.bars : "wifi-offline"
        fallback: net.item ? net.item.fallbackIcon : ""
    }
    P5Support.DataSource {
        id: power
        engine: "powermanagement"
        connectedSources: ["Battery", "AC Adapter"]
    }
    // Energy saver (power-profiles-daemon's power-saver): the leaf glyph, as the taskbar shows it.
    property bool saver: false
    Timer {
        interval: 60000; repeat: true; running: icons.hasBattery; triggeredOnStart: true
        onTriggered: root.run("powerprofilesctl get", (out) => icons.saver = out.trim() === "power-saver")
    }
    readonly property bool hasBattery: power.data["Battery"] ? !!power.data["Battery"]["Has Battery"] : false
    readonly property int percent: power.data["Battery"] ? Number(power.data["Battery"]["Percent"] || 0) : 0
    readonly property bool plugged: power.data["AC Adapter"] ? !!power.data["AC Adapter"]["Plugged in"] : false
    IconFile {
        visible: icons.hasBattery
        size: 17.5
        anchors.verticalCenter: parent.verticalCenter
        readonly property int level: Math.max(0, Math.min(100, Math.round(icons.percent / 10) * 10))
        name: icons.plugged ? "battery-" + level + "-charging"
            : icons.saver ? "battery-saver"
            : icons.percent <= 5 ? "battery-caution"
            : "battery-" + level
        fallback: "file:///usr/share/fenestra/assets/battery/" + (icons.plugged ? "charging" : "normal") + "-0-" + Math.round(icons.percent / 10) + ".svg"
    }
    component IconFile: Image {
        id: f
        property string name
        property string fallback
        property real size: 16
        width: size; height: size
        sourceSize: Qt.size(Math.ceil(size * Screen.devicePixelRatio), Math.ceil(size * Screen.devicePixelRatio))
        // The pack's glyph; Fenestra's own drawing if the pack is not there.
        property bool missing: false
        source: name === "" ? "" : missing ? fallback : icons.white + name + ".svg"
        onNameChanged: missing = false
        onStatusChanged: if (status === Image.Error && !missing) missing = true
        smooth: true
    }
}

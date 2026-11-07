// SPDX-License-Identifier: GPL-3.0-or-later
// Clock view, bottom right: battery then network (Windows: 21 px glyph boxes at 150 %, the network
// one centred 48 px from the right and 28 px over the bottom).
import QtQuick
import QtCore
import org.kde.plasma.plasma5support as P5Support

Row {
    spacing: 18
    layoutDirection: Qt.RightToLeft
    readonly property string pack: StandardPaths.writableLocation(StandardPaths.GenericDataLocation).toString() + "/fenestra/packs/windows-11-user-export/glyphs/cp/"
    Loader { id: net; source: "NetworkStatus.qml"; visible: false }
    Glyph {
        size: 14
        glyph: net.item && net.item.kind === "wired" ? "" : ""
        fallback: net.item ? (net.item.icon !== "" ? net.item.icon : net.item.fallbackIcon) : ""
        Image { id: probe; visible: false; source: net.item ? net.item.icon : "" }
        Component.onCompleted: if (probe.status === Image.Error && net.item) fallback = net.item.fallbackIcon
    }
    P5Support.DataSource {
        id: power
        engine: "powermanagement"
        connectedSources: ["Battery", "AC Adapter"]
    }
    readonly property bool hasBattery: power.data["Battery"] ? !!power.data["Battery"]["Has Battery"] : false
    readonly property int percent: power.data["Battery"] ? Number(power.data["Battery"]["Percent"] || 0) : 0
    readonly property bool plugged: power.data["AC Adapter"] ? !!power.data["AC Adapter"]["Plugged in"] : false
    Glyph {
        visible: parent.hasBattery
        size: 20
        anchors.verticalCenter: parent.verticalCenter
        readonly property int tenths: Math.round(parent.percent / 10)
        fallback: parent.pack + "battery-" + (tenths * 10) + (parent.plugged ? "-charging" : "") + ".svg"
    }
}

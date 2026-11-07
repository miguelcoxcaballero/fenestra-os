// SPDX-License-Identifier: GPL-3.0-or-later
// The active connection as the corner button and the clock view show it (plasma-nm's model of
// NetworkManager): wired, Wi-Fi with its bars (0-4: signal / 20, as the taskbar), or none.
import QtQuick
import QtCore
import org.kde.plasma.networkmanagement as PlasmaNM

Item {
    id: st
    property string kind: "none"     // wired | wifi | none
    property int bars: 0
    property string name: ""
    readonly property string glyph: kind === "wired" ? "" : ""   // Wi-Fi: the pack's tray glyphs
    readonly property string pack: StandardPaths.writableLocation(StandardPaths.GenericDataLocation).toString() + "/fenestra/packs/windows-11-user-export/glyphs/cp/"
    readonly property string icon: kind === "wired" ? "" : kind === "wifi" ? pack + "wifi-" + bars + ".svg" : pack + "wifi-offline.svg"
    readonly property string fallbackIcon: kind === "wifi"
        ? "file:///usr/share/fenestra/assets/status/network-wireless-signal-" + ["none", "weak", "ok", "good", "excellent"][bars] + "-symbolic.svg"
        : kind === "wired" ? "file:///usr/share/fenestra/assets/security/network-wired.svg" : "file:///usr/share/fenestra/assets/status/network-wireless-offline-symbolic.svg"
    Instantiator {
        id: rows
        model: PlasmaNM.NetworkModel {}
        delegate: QtObject {
            required property var model
            readonly property int state: model.ConnectionState
            readonly property int type: model.Type
            readonly property int signal: model.Signal
            readonly property string label: model.Name
        }
        onObjectAdded: st.update()
        onObjectRemoved: st.update()
    }
    Timer { interval: 2000; running: true; repeat: true; onTriggered: st.update() }
    function update() {
        let k = "none", b = 0, n = ""
        for (let i = 0; i < rows.count; i++) {
            const r = rows.objectAt(i)
            if (!r || r.state !== PlasmaNM.Enums.Activated) continue
            if (r.type === PlasmaNM.Enums.Wired) { k = "wired"; n = r.label; break }
            if (r.type === PlasmaNM.Enums.Wireless) { k = "wifi"; b = Math.max(0, Math.min(4, Math.floor(r.signal / 20))); n = r.label }
        }
        kind = k; bars = b; name = n
    }
}

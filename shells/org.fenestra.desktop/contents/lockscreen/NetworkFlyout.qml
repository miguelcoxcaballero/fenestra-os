// SPDX-License-Identifier: GPL-3.0-or-later
// Network flyout of the sign-in screen (Windows: 362.7 px wide, its right edge 24.7 px from the
// screen's, its bottom 70.7 px over the bottom; the connection's 28 px glyph at 17.3, its name
// and state at 56; quick tiles 96 x 48 at 25.3 with their label under them). Wi-Fi networks are
// listed as in Windows: select one to connect (with its key when it is new) or disconnect.
import QtQuick
import QtCore
import org.kde.plasma.networkmanagement as PlasmaNM

Acrylic {
    id: fly
    width: 362.7
    height: list.y + list.height + 26 + tiles.height + 43.4
    readonly property string pack: StandardPaths.writableLocation(StandardPaths.GenericDataLocation).toString() + "/fenestra/packs/windows-11-user-export/glyphs/cp/"
    property string selected: ""
    PlasmaNM.Handler { id: handler }
    PlasmaNM.EnabledConnections { id: radios }
    PlasmaNM.AppletProxyModel { id: networks; sourceModel: PlasmaNM.NetworkModel {} }
    Component.onCompleted: handler.requestScan()
    Text { // nothing to show (no device, or Wi-Fi off)
        x: 17.3; y: 22
        visible: list.count === 0
        text: radios.wirelessEnabled ? root.tr("No networks found", "No se encontraron redes") : root.tr("Wi-Fi is off", "La Wi-Fi está desactivada")
        color: Qt.rgba(1, 1, 1, 0.786)
        font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
        renderType: Text.QtRendering
    }
    ListView {
        id: list
        x: 4; y: 4
        width: parent.width - 8
        height: Math.min(contentHeight, 5 * 60)
        clip: true
        interactive: contentHeight > height
        model: networks
        delegate: Item {
            id: row
            required property var model
            readonly property bool wifi: model.Type === PlasmaNM.Enums.Wireless
            readonly property bool wired: model.Type === PlasmaNM.Enums.Wired
            readonly property bool active: model.ConnectionState === PlasmaNM.Enums.Activated
            readonly property bool activating: model.ConnectionState === PlasmaNM.Enums.Activating
            readonly property bool known: model.ConnectionPath !== ""
            readonly property bool secured: model.SecurityType > 0
            readonly property bool open: fly.selected === model.ItemUniqueName
            readonly property int bars: Math.max(0, Math.min(4, Math.floor(model.Signal / 20)))
            visible: (wifi || (wired && active)) && !model.Duplicate
            width: list.width
            height: visible ? (open ? 60 + actions.height + 12 : 60) : 0
            Rectangle {
                anchors.fill: parent; anchors.margins: 0; radius: 4
                color: row.open ? Qt.rgba(1, 1, 1, 0.06) : hover.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : "transparent"
            }
            Glyph {
                x: 13.3; y: 16; size: 28
                glyph: row.wired ? "\uE839" : ""
                fallback: row.wired ? "file:///usr/share/fenestra/assets/security/network-wired.svg" : fly.pack + "wifi-" + row.bars + ".svg"
            }
            Column {
                x: 52; y: 14
                width: parent.width - x - 12
                Text {
                    width: parent.width; elide: Text.ElideRight
                    text: row.wired ? row.model.Name : row.model.Ssid || row.model.Name
                    color: "white"
                    font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                    renderType: Text.QtRendering
                }
                Text {
                    text: row.active ? (row.wifi && row.secured ? root.tr("Connected, secured", "Conectado, protegida") : root.tr("Connected", "Conectado"))
                        : row.activating ? root.tr("Connecting…", "Conectando…")
                        : row.secured ? root.tr("Secured", "Protegida") : root.tr("Open", "Abierta")
                    color: Qt.rgba(1, 1, 1, 0.786)
                    font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                    renderType: Text.QtRendering
                }
            }
            MouseArea { id: hover; width: parent.width; height: 60; hoverEnabled: true; enabled: row.wifi; onClicked: fly.selected = row.open ? "" : row.model.ItemUniqueName }
            Column {
                id: actions
                visible: row.open
                x: 52; y: 60
                width: parent.width - x - 12
                spacing: 8
                readonly property bool needsKey: !row.active && !row.known && row.secured
                Item {
                    visible: actions.needsKey
                    onVisibleChanged: if (visible) key.forceActiveFocus()
                    width: parent.width; height: 32
                    Rectangle {
                        anchors.fill: parent; radius: 4
                        color: key.activeFocus ? Qt.rgba(30 / 255, 30 / 255, 30 / 255, 0.70) : Qt.rgba(1, 1, 1, 0.06)
                        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.08)
                    }
                    Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 1 }
                                height: key.activeFocus ? 2 : 1; color: key.activeFocus ? root.accent : Qt.rgba(1, 1, 1, 0.54) }
                    TextInput {
                        id: key
                        x: 10; width: parent.width - 20; anchors.verticalCenter: parent.verticalCenter
                        echoMode: TextInput.Password; passwordCharacter: "●"
                        color: "white"; clip: true
                        font.family: Fluent.text; font.pixelSize: 14
                        Text { visible: !parent.text; text: root.tr("Enter the network security key", "Escribe la clave de seguridad de red")
                               color: Qt.rgba(1, 1, 1, 0.786); font: parent.font }
                        onAccepted: connectButton.clicked()
                    }
                }
                FluentButton {
                    id: connectButton
                    anchors.right: parent.right
                    text: row.active ? root.tr("Disconnect", "Desconectar") : actions.needsKey ? root.tr("Next", "Siguiente") : root.tr("Connect", "Conectar")
                    onClicked: {
                        if (row.active) handler.deactivateConnection(row.model.ConnectionPath, row.model.DevicePath)
                        else if (row.known) handler.activateConnection(row.model.ConnectionPath, row.model.DevicePath, row.model.SpecificPath)
                        else handler.addAndActivateConnection(row.model.DevicePath, row.model.SpecificPath, key.text)
                        fly.selected = ""
                    }
                }
            }
        }
    }
    // Quick tiles: Wi-Fi and Airplane mode (96 x 48, accent when on, label under them).
    Row {
        id: tiles
        x: 25.3 - 4
        anchors.bottom: parent.bottom; anchors.bottomMargin: 43.4
        spacing: 12
        Tile {
            visible: radios.wirelessHwEnabled
            glyph: "\uE701"; fallback: fly.pack + "wifi-4.svg"
            on: radios.wirelessEnabled
            label: "Wi-Fi"
            onClicked: handler.enableWireless(!radios.wirelessEnabled)
        }
        Tile {
            glyph: "\uE709"; fallback: "file:///usr/share/fenestra/assets/security/network-offline.svg"
            on: PlasmaNM.Configuration.airplaneModeEnabled
            label: root.tr("Airplane mode", "Modo avión")
            onClicked: { handler.enableAirplaneMode(!PlasmaNM.Configuration.airplaneModeEnabled); PlasmaNM.Configuration.airplaneModeEnabled = !PlasmaNM.Configuration.airplaneModeEnabled }
        }
    }
    component Tile: Item {
        id: tile
        property alias glyph: g.glyph
        property alias fallback: g.fallback
        property bool on: false
        property string label
        signal clicked()
        width: 96; height: 48
        Rectangle {
            anchors.fill: parent; radius: 4
            color: tile.on ? root.accent : m.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.06)
            border.width: 1; border.color: Qt.rgba(1, 1, 1, tile.on ? 0.0 : 0.09)
        }
        Glyph { id: g; anchors.centerIn: parent; size: 16; color: tile.on ? "black" : "white" }
        Text {
            anchors { horizontalCenter: parent.horizontalCenter; top: parent.bottom; topMargin: 8 }
            text: tile.label; color: Qt.rgba(1, 1, 1, 0.786)
            font.family: Fluent.text; font.pixelSize: 12; font.variableAxes: ({ "opsz": Fluent.opsz(12) })
            renderType: Text.QtRendering
        }
        MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; onClicked: tile.clicked() }
        Accessible.role: Accessible.CheckBox
        Accessible.name: label
        Accessible.checked: on
    }
}

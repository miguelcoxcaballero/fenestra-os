// SPDX-License-Identifier: GPL-3.0-or-later
// Accessibility flyout of the sign-in screen (Windows: 357.3 x 352 px, right edge 12.7 px from the
// screen's, rows of 48 px: 16 px glyph centred at 24.7, label at 44.7, "On/Off" right-aligned
// 74 px from the right, a 40 x 20 switch 19.3 px from the right). Each switch does it for real:
// Magnifier (KWin zoom), Contrast themes (this screen), Narrator (Orca), On-screen keyboard,
// Sticky keys and Filter keys (KWin, kaccessrc). Windows' Voice access has no Linux counterpart.
import QtQuick

Acrylic {
    id: fly
    width: 357.3
    height: col.height + 16
    property bool magnifier: false
    property bool narrator: false
    property bool sticky: false
    property bool filter: false
    readonly property string kconf: "env -u KDE_HOME_READONLY kwriteconfig6 --file kaccessrc --group Keyboard --key "
    readonly property string reconfigure: " && (qdbus6 org.kde.KWin /KWin reconfigure || qdbus org.kde.KWin /KWin reconfigure)"
    Component.onCompleted: {
        root.run("kreadconfig6 --file kaccessrc --group Keyboard --key StickyKeys --default false", (out) => fly.sticky = out.trim() === "true")
        root.run("kreadconfig6 --file kaccessrc --group Keyboard --key BounceKeys --default false", (out) => fly.filter = out.trim() === "true")
        root.run("pgrep -x orca", (out, code) => fly.narrator = code === 0)
    }
    // Glyphs matched against the reference capture (Segoe Fluent Icons): magnifier E8A3, contrast
    // E7A1, narrator ED4D, keyboard E765, Sticky keys E3BB, Filter keys E3BA (without the font:
    // the keyboard with a drawn badge).
    readonly property var rows: [
        { key: "magnifier", g: "\uE8A3", text: root.tr("Magnifier", "Lupa") },
        { key: "contrast", g: "\uE7A1", text: root.tr("Contrast themes", "Temas de contraste") },
        { key: "narrator", g: "\uED4D", text: root.tr("Narrator", "Narrador") },
        { key: "osk", g: "\uE765", text: root.tr("On-screen keyboard", "Teclado en pantalla") },
        { key: "sticky", g: Fluent.available ? "\uE3BB" : "\uE765", badge: "sticky", text: root.tr("Sticky keys", "Teclas especiales") },
        { key: "filter", g: Fluent.available ? "\uE3BA" : "\uE765", badge: "filter", text: root.tr("Filter keys", "Teclas filtro") }]
    function state(k) {
        return k === "magnifier" ? magnifier : k === "contrast" ? root.highContrast : k === "narrator" ? narrator
             : k === "osk" ? root.osk : k === "sticky" ? sticky : filter
    }
    function toggle(k) {
        const on = !state(k)
        if (k === "magnifier") { magnifier = on; root.run("qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.invokeShortcut " + (on ? "view_zoom_in" : "view_actual_size")) }
        else if (k === "contrast") root.highContrast = on
        else if (k === "narrator") { narrator = on; root.run(on ? "sh -c 'orca --replace >/dev/null 2>&1 &'" : "orca --quit") }
        else if (k === "osk") root.osk = on
        else if (k === "sticky") { sticky = on; root.run("sh -c '" + kconf + "StickyKeys " + on + reconfigure + "'") }
        else { filter = on; root.run("sh -c '" + kconf + "BounceKeys " + on + reconfigure + "'") }
    }
    Column {
        id: col
        y: 4
        width: parent.width
        Repeater {
            model: fly.rows
            Item {
                id: row
                width: col.width; height: 48
                readonly property bool on: fly.state(modelData.key)
                Rectangle { anchors.fill: parent; anchors.leftMargin: 4; anchors.rightMargin: 4; radius: 4
                            color: m.pressed ? Qt.rgba(1, 1, 1, 0.04) : m.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent" }
                Glyph { id: g; x: 24.7 - 8; anchors.verticalCenter: parent.verticalCenter; size: 16; glyph: modelData.g
                        scale: modelData.badge && !Fluent.available ? 0.8 : 1; transformOrigin: Item.TopLeft }
                // Badge of Sticky keys (two keys) / Filter keys (a "no" sign), bottom right of the keyboard.
                Row {
                    visible: modelData.badge === "sticky" && !Fluent.available
                    x: g.x + 8.5; y: g.y + 9.5; spacing: 1
                    Repeater { model: 2; Rectangle { width: 3.5; height: 3.5; radius: 0.7; color: "white" } }
                }
                Rectangle {
                    visible: modelData.badge === "filter" && !Fluent.available
                    x: g.x + 8.5; y: g.y + 8; width: 8; height: 8; radius: 4; color: "white"
                    Rectangle { anchors.centerIn: parent; width: 6; height: 1.2; rotation: -45; color: "#202020" }
                }
                Text {
                    x: 44.7; anchors.verticalCenter: parent.verticalCenter
                    text: modelData.text; color: "white"
                    font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                    renderType: Text.QtRendering
                }
                Text {
                    anchors { right: parent.right; rightMargin: 74; verticalCenter: parent.verticalCenter }
                    text: row.on ? root.tr("On", "Activado") : root.tr("Off", "Desactivado")
                    color: "white"
                    font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                    renderType: Text.QtRendering
                }
                // ToggleSwitch: 40 x 20, off = 1 px #CFCFCF ring with a 12 px knob, on = accent with a black 14 px knob.
                Rectangle {
                    id: sw
                    anchors { right: parent.right; rightMargin: 19.3; verticalCenter: parent.verticalCenter }
                    width: 40; height: 20; radius: 10
                    color: row.on ? root.accent : "transparent"
                    border.width: row.on ? 0 : 1; border.color: Qt.rgba(1, 1, 1, 0.6)
                    Rectangle {
                        width: row.on ? 14 : 12; height: width; radius: width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        x: row.on ? parent.width - width - 3 : 4
                        color: row.on ? "black" : Qt.rgba(1, 1, 1, 0.786)
                        Behavior on x { NumberAnimation { duration: 167; easing.type: Easing.OutCubic } }
                    }
                }
                MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; onClicked: fly.toggle(modelData.key) }
                Accessible.role: Accessible.CheckBox
                Accessible.name: modelData.text
                Accessible.checked: row.on
            }
        }
    }
}

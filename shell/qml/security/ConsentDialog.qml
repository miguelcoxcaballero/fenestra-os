// SPDX-License-Identifier: GPL-3.0-or-later
// Administrator consent (Q06, fenestra-consent): polkit authentication with the account-control
// layout: title bar with close, the question, shield + the real polkit message, "Show more details"
// (action ID), the password field (always asked), Yes / No. 456 px, dimmed background.
import QtQuick
import org.kde.layershell as LayerShell
import Fenestra.Shell

Window {
    id: consent
    color: Qt.rgba(0, 0, 0, 0.45)
    visible: PolkitAgent.active
    property bool details: false
    LayerShell.Window.scope: "fenestra-consent"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityExclusive
    onVisibleChanged: if (visible) { details = false; password.text = ""; requestActivate(); password.forceActiveFocus() }

    Rectangle {
        id: dialog
        anchors.centerIn: parent
        width: 456; height: col.height
        radius: 8
        color: Theme.dark ? "#2b2b2b" : "#f9f9f9"
        border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(0, 0, 0, 0.12)
        Column {
            id: col
            width: parent.width
            Rectangle {
                width: parent.width; height: titleBar.height + question.height
                topLeftRadius: 8; topRightRadius: 8
                color: Theme.dark ? "#333333" : "#eeeeee"
                Item {
                    id: titleBar
                    width: parent.width; height: 32
                    Text { x: 24; y: 9; text: Strings.tr("User Account Control"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                    Rectangle {
                        anchors.right: parent.right; width: 46; height: 32; topRightRadius: 7
                        color: xm.containsMouse ? "#c42b1c" : "transparent"
                        SymbolicIcon { anchors.centerIn: parent; size: 10; src: Metrics.assets + "consent/close.svg" }
                        MouseArea { id: xm; anchors.fill: parent; hoverEnabled: true; onClicked: PolkitAgent.cancel() }
                    }
                }
                Text {
                    id: question
                    y: 32; width: parent.width; leftPadding: 24; rightPadding: 24; topPadding: 16; bottomPadding: 22
                    wrapMode: Text.Wrap
                    text: Strings.tr("Do you want to allow this app to make changes to your device?")
                    color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 19
                }
            }
            Column {
                width: parent.width; padding: 24; topPadding: 20; spacing: 16
                Row {
                    spacing: 12; width: parent.width - 48
                    Image { width: 32; height: 32; source: Metrics.assets + "consent/shield.svg" }
                    Text { width: parent.width - 44; wrapMode: Text.Wrap; text: PolkitAgent.message
                           color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 14 }
                }
                Text {
                    text: Strings.tr(consent.details ? "Hide details" : "Show more details")
                    color: Theme.accentText; font.family: Metrics.fontFamily; font.pixelSize: 12
                    font.underline: dl.containsMouse
                    MouseArea { id: dl; anchors.fill: parent; hoverEnabled: true; onClicked: consent.details = !consent.details }
                }
                Text { visible: consent.details; text: Strings.tr("Action ID") + ": " + PolkitAgent.actionId
                       color: Theme.dark ? "#c5c5c5" : "#5c5c5c"; font.family: Metrics.fontFamily; font.pixelSize: 12 }
                Text { text: PolkitAgent.userName; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold }
                Rectangle {
                    width: 388; height: 34; radius: 4
                    color: Theme.dark ? Qt.rgba(1, 1, 1, 0.06) : "white"
                    border.color: password.activeFocus ? Theme.accentFill : (Theme.dark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0, 0, 0, 0.12))
                    TextInput {
                        id: password
                        x: 9; width: parent.width - 18; anchors.verticalCenter: parent.verticalCenter
                        echoMode: PolkitAgent.echo ? TextInput.Normal : TextInput.Password
                        color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: 13
                        Text { visible: !parent.text; text: Strings.tr("Password"); color: Theme.textSecondary; font: parent.font }
                        onAccepted: { PolkitAgent.respond(text); text = "" }
                        Keys.onEscapePressed: PolkitAgent.cancel()
                    }
                }
                Text { visible: PolkitAgent.error !== ""; width: parent.width - 48; wrapMode: Text.Wrap; text: PolkitAgent.error
                       color: "#ff99a4"; font.family: Metrics.fontFamily; font.pixelSize: 12 }
            }
            Rectangle {
                width: parent.width; height: 72
                bottomLeftRadius: 8; bottomRightRadius: 8
                color: Theme.dark ? "#202020" : "#f3f3f3"
                Row {
                    anchors.centerIn: parent; spacing: 8
                    Repeater {
                        model: [["Yes", true], ["No", false]]
                        delegate: Rectangle {
                            required property var modelData
                            width: 200; height: 32; radius: 3
                            color: modelData[1] ? (ym.containsMouse ? Theme.accentHover : Theme.accentFill)
                                                : (ym.containsMouse ? (Theme.dark ? "#454545" : "#f5f5f5") : (Theme.dark ? "#383838" : "white"))
                            border.color: modelData[1] ? "transparent" : (Theme.dark ? "#505050" : Qt.rgba(0, 0, 0, 0.12))
                            Text { anchors.centerIn: parent; text: Strings.tr(modelData[0]); color: modelData[1] ? Theme.accentOn : Theme.text
                                   font.family: Metrics.fontFamily; font.pixelSize: 13 }
                            MouseArea { id: ym; anchors.fill: parent; hoverEnabled: true
                                onClicked: modelData[1] ? (PolkitAgent.respond(password.text), password.text = "") : PolkitAgent.cancel() }
                        }
                    }
                }
            }
        }
    }
}

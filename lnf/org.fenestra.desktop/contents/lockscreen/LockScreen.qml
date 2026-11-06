// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra lock screen (L01, L02) for kscreenlocker: the picture, the large clock in the system
// locale (96 px / 600, date 18 px, at 13 % of the height), network and battery at the bottom right.
// A key, click or touch raises the sign-in: the clock moves up 12 % of the height in 300 ms
// (OutCubic), a dimmer rises to 82/255 and the account with its password field comes up 16 px.
// Fast unlock: success unlocks at once (no waiting for pending PAM messages).
import QtQuick

Item {
    id: root
    // Provided by kscreenlocker_greet: authenticator, kscreenlocker_userName, kscreenlocker_userImage, config.
    property bool prompting: false
    property real progress: prompting ? 1 : 0
    Behavior on progress { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
    readonly property bool es: Qt.locale().name.startsWith("es")
    property string message: ""

    function tr(en, sp) { return es ? sp : en }
    function showPrompt() {
        if (prompting) return
        prompting = true
        password.forceActiveFocus()
        authenticator.startAuthenticating()
    }
    function submit() {
        if (password.text === "") return
        busy.visible = true
        authenticator.respond(password.text)
        authenticator.tryUnlock()
    }

    Connections {
        target: authenticator
        function onFailed() {
            busy.visible = false
            password.text = ""
            root.message = root.tr("The password is incorrect. Try again.", "La contraseña no es correcta. Inténtalo de nuevo.")
            shake.restart()
            password.forceActiveFocus()
        }
        function onSucceeded() { Qt.quit() }
        function onPromptForSecretChanged() { busy.visible = false }
        function onErrorMessageChanged() { root.message = authenticator.errorMessage }
        function onInfoMessageChanged() { if (authenticator.infoMessage) root.message = authenticator.infoMessage }
    }

    Rectangle { anchors.fill: parent; color: "#202020" }
    Image {
        anchors.fill: parent
        source: config.Background ? "file://" + config.Background : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
    }
    Rectangle { anchors.fill: parent; color: "black"; opacity: root.progress * 82 / 255 }

    // ---- Clock ----
    Column {
        id: clock
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.13 - root.progress * root.height * 0.12
        opacity: 1 - root.progress
        spacing: 0
        property date now: new Date()
        Timer { interval: 1000; running: true; repeat: true; onTriggered: clock.now = new Date() }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            // System locale, AM/PM stripped (lock-clock face.js).
            text: Qt.formatTime(clock.now, Qt.locale().timeFormat(Locale.ShortFormat).replace(/\s*(AP|ap|A|a)\s*/g, "").replace(/[:.]ss/, ""))
            color: "white"; font.pixelSize: 96; font.weight: Font.DemiBold; font.family: "Segoe UI Variable Display"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: { const s = clock.now.toLocaleDateString(Qt.locale(), "dddd d MMMM"); return s.charAt(0).toUpperCase() + s.slice(1) }
            color: "white"; font.pixelSize: 18; font.family: "Segoe UI Variable Text"
        }
    }

    // ---- Sign-in ----
    Column {
        id: signin
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.30 + (1 - root.progress) * 16
        opacity: Math.max(0, (root.progress - 0.25) / 0.75)
        visible: opacity > 0
        spacing: 16
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 192; height: 192; radius: 96; clip: true
            color: "#3a3a3a"
            Image { anchors.fill: parent; source: kscreenlocker_userImage; fillMode: Image.PreserveAspectCrop; visible: kscreenlocker_userImage !== "" }
            Text { anchors.centerIn: parent; visible: kscreenlocker_userImage === ""; text: kscreenlocker_userName.charAt(0).toUpperCase()
                   color: "white"; font.pixelSize: 72 }
        }
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: kscreenlocker_userName; color: "white"; font.pixelSize: 28; font.weight: Font.DemiBold }
        Item {
            id: field
            anchors.horizontalCenter: parent.horizontalCenter
            width: 296; height: 36
            SequentialAnimation on x {
                id: shake; running: false; loops: 1
                NumberAnimation { from: 0; to: -12; duration: 40 } NumberAnimation { to: 12; duration: 80 } NumberAnimation { to: 0; duration: 40 }
            }
            Rectangle {
                anchors.fill: parent; radius: 4
                color: Qt.rgba(1, 1, 1, password.activeFocus ? 0.09 : 0.06)
                border.color: Qt.rgba(1, 1, 1, 0.14)
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: password.activeFocus ? 2 : 1; color: password.activeFocus ? "#4cc2ff" : Qt.rgba(1, 1, 1, 0.5) }
            }
            TextInput {
                id: password
                x: 12; width: parent.width - 52; anchors.verticalCenter: parent.verticalCenter
                echoMode: TextInput.Password; color: "white"; font.pixelSize: 14
                Text { visible: !parent.text; text: root.tr("Password", "Contraseña"); color: Qt.rgba(1, 1, 1, 0.6); font: parent.font }
                onAccepted: root.submit()
                Keys.onEscapePressed: { text = ""; root.prompting = false; root.forceActiveFocus() }
            }
            Rectangle {
                anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                width: 28; height: 28; radius: 4; color: go.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
                Text { anchors.centerIn: parent; text: "→"; color: "white"; font.pixelSize: 14 }
                MouseArea { id: go; anchors.fill: parent; hoverEnabled: true; onClicked: root.submit() }
            }
        }
        Text { id: busy; visible: false; anchors.horizontalCenter: parent.horizontalCenter; text: root.tr("Welcome", "Te damos la bienvenida"); color: "white"; font.pixelSize: 14 }
        Text { anchors.horizontalCenter: parent.horizontalCenter; width: 296; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
               text: root.message; visible: text !== ""; color: "white"; font.pixelSize: 13 }
    }

    // ---- Status: network and battery (bottom right) ----
    Row {
        anchors { right: parent.right; bottom: parent.bottom; margins: 24 }
        spacing: 16
        Text { visible: config.Network !== ""; text: config.Network; color: "white"; font.pixelSize: 13 }
        Text { visible: config.Battery >= 0; text: config.Battery + " %"; color: "white"; font.pixelSize: 13 }
    }

    focus: true
    Keys.onPressed: (e) => { if (!root.prompting) { showPrompt(); if (e.text.length === 1) password.text = e.text; e.accepted = true } }
    MouseArea { anchors.fill: parent; enabled: !root.prompting; onClicked: root.showPrompt() }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Renders lnf/org.fenestra.desktop's LockScreen.qml with a fake kscreenlocker authenticator:
// clock, sign-in, wrong password, success. Writes PNGs to $OUT and prints LOCK_* lines.
import QtQuick
import QtQuick.Window

Window {
    id: win
    width: 1920; height: 1080; visible: true; color: "black"
    // Arguments after "--": LockScreen.qml, background picture, output directory.
    readonly property var args: { const a = Qt.application.arguments; const i = a.indexOf("--"); return i >= 0 ? a.slice(i + 1) : [] }
    // What kscreenlocker_greet provides.
    property string kscreenlocker_userName: "Usuario Demo"
    property string kscreenlocker_userImage: ""
    // kscreenlocker passes a key/value map (entry names as in contents/config/main.xml).
    property var config: ({ Background: win.args.length > 1 ? win.args[1] : "",
                            Network: "Wi-Fi demo", Battery: 82 })
    property QtObject authenticator: QtObject {
        signal failed()
        signal succeeded()
        signal promptForSecretChanged()
        property string errorMessage: ""
        property string infoMessage: ""
        property string response: ""
        property int starts: 0
        function startAuthenticating() { starts++ }
        function respond(r) { response = r }
        function tryUnlock() { response === "demo" ? succeeded() : failed() }
    }
    Loader { id: lock; anchors.fill: parent; source: win.args.length > 0 ? "file://" + win.args[0] : ""; focus: true }
    property string out: args.length > 2 ? args[2] : "/tmp"
    function shot(name, next) { lock.grabToImage(r => { r.saveToFile(out + "/" + name + ".png"); console.info("LOCK_SHOT " + name); next() }) }
    Timer {
        interval: 800; running: lock.status === Loader.Ready
        onTriggered: win.shot("lock-1-clock", () => {
            lock.item.showPrompt()
            step2.start()
        })
    }
    Timer { id: step2; interval: 600; onTriggered: {
        console.info("LOCK_STARTED " + (authenticator.starts > 0))
        win.shot("lock-2-signin", () => { lock.item.children; wrong.start() })
    } }
    Timer { id: wrong; interval: 100; onTriggered: {
        authenticator.response = "x"; authenticator.tryUnlock()
        step3.start()
    } }
    Timer { id: step3; interval: 400; onTriggered: win.shot("lock-3-wrong", () => {
        console.info("LOCK_MESSAGE " + lock.item.message)
        authenticator.response = "demo"; authenticator.tryUnlock()
    }) }
    Connections { target: authenticator; function onSucceeded() { console.info("LOCK_SUCCEEDED"); Qt.quit() } }
}

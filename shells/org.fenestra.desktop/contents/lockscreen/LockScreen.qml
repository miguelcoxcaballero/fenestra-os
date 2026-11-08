// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra lock screen for KWin's screen locker (kscreenlocker_greet): Windows 11's lock screen,
// measured on Windows 11 24H2 at 2880 x 1800, 150 % (tests/lockscreen/MEASUREMENTS.md).
//  * Clock view: the picture under 20 % black, the time (Segoe UI Variable Semibold, 135 px at
//    1200 px of height) and the date, network and battery at the bottom right, media when playing.
//  * A key, click or tap: the clock leaves upwards in 120 ms, then in 500 ms (linear) the picture
//    zooms to 102 % and darkens to 46.6 % black (blurred: Windows' acrylic sign-in background), and
//    the account, the password box and the corner buttons fade in. The first typed character goes
//    into the box. 30 s without input: back to the clock.
//  * Unlocking: kscreenlocker's PAM authenticators (password; fingerprint and face run alongside:
//    fprintd and Howdy), Windows Hello's face animation while the camera looks and on success.
//  * Bottom right: network, accessibility and power, each with Windows' flyout.
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import QtCore
import org.kde.kscreenlocker as ScreenLocker

Item {
    id: root
    // kscreenlocker_greet's "magic" properties and signals (as Plasma's own lock screen has them).
    property bool viewVisible: false
    property string notification: ""
    signal clearPassword()
    signal notificationRepeated()

    implicitWidth: 1920; implicitHeight: 1200
    readonly property bool es: Qt.locale().name.startsWith("es")
    function tr(en, sp) { return es ? sp : en }
    // kscreenlocker gives "config" (kscreenlockerrc [Greeter][LnF][General], contents/lockscreen/config.xml).
    function cfg(key, fallback) { return typeof config !== "undefined" && config && config[key] !== undefined && config[key] !== "" ? config[key] : fallback }
    readonly property color accent: cfg("Accent", "#0078D4")
    // AccentTextFillColorPrimary (dark): the accent towards white; #0078D4 -> #99EBFF as measured.
    readonly property color lightAccent: Qt.colorEqual(accent, "#0078D4") ? "#99EBFF" : Qt.lighter(accent, 1.9)
    // A Spotlight / weather link clicked on the clock view: opened once the session is unlocked.
    property string pendingUrl: ""
    function openAfterUnlock(url) { pendingUrl = url; showSignin("") }
    readonly property string userName: typeof kscreenlocker_userName !== "undefined" ? kscreenlocker_userName : ""
    readonly property string userImage: typeof kscreenlocker_userImage !== "undefined" ? kscreenlocker_userImage : ""

    // ------------------------------------------------------------------ state ------
    // "clock" | "signin" | "welcome"; prompt: "password" | "face" | "fingerprint" | "message"
    property string phase: "clock"
    property string prompt: "password"
    property string message: ""          // the text over "OK" (wrong password, Hello errors)
    property string menu: ""             // "" | network | accessibility | power
    property string pendingPassword: ""
    property bool faceAvailable: false
    property bool fingerAvailable: false
    property string faceState: ""        // "" | searching | failed | success
    property string fingerState: ""      // "" | waiting | failed
    property bool highContrast: false     // accessibility flyout: Contrast themes (this screen)
    property bool osk: false              // accessibility flyout: On-screen keyboard

    // One clock for the whole reveal: 0..120 ms the clock leaves, 120..620 ms the background.
    property real t: 0
    readonly property real exitP: Math.min(1, t / 120)
    readonly property real p: Math.max(0, Math.min(1, (t - 120) / 500))
    NumberAnimation { id: revealAnim; target: root; property: "t"; to: 620; duration: Math.max(1, 620 - root.t); easing.type: Easing.Linear }
    NumberAnimation { id: hideAnim; target: root; property: "t"; to: 0; duration: Math.max(1, root.t); easing.type: Easing.Linear }

    function showSignin(firstChar) {
        idle.restart()
        if (phase === "clock") {
            phase = "signin"
            hideAnim.stop(); revealAnim.duration = Math.max(1, 620 - t); revealAnim.start()
            if (prompt === "message") prompt = defaultPrompt()
            quietSince = Date.now()
            // A face or fingerprint that matched while the clock came back (after 30 s idle): it
            // unlocks now that the user dismissed the clock, not before.
            if (deferredUnlock !== "") { const k = deferredUnlock; deferredUnlock = ""; unlock(k); return }
            // The heartbeat starts face, fingerprint and the password as soon as the reveal is over
            // (starting the PAM conversations during it cost a 36 ms frame); a password typed and
            // sent before then waits in pendingPassword.
        }
        // Windows: the key that raises the sign-in screen is not typed into the box.
        if (prompt === "password") password.forceActiveFocus()
    }
    function showClock() {
        if (phase !== "signin") return
        menu = ""; password.text = ""; reveal.held = false
        phase = "clock"
        revealAnim.stop(); hideAnim.duration = Math.max(1, t); hideAnim.start()
        root.forceActiveFocus()
    }
    function defaultPrompt() { return faceState === "searching" ? "face" : "password" }

    // Windows returns to the clock after a while without input on the sign-in screen.
    Timer { id: idle; interval: 30000; running: root.phase === "signin" && root.menu === "" && password.text === ""; onTriggered: root.showClock() }
    // Plasma's heartbeat: (re)starts the PAM conversations, only once the clock is dismissed: nothing
    // (face, fingerprint, password) is checked while the clock shows (the user's choice: no unlock
    // before the sign-in screen is up). The workers are not ready when the lock screen loads, so it
    // keeps trying every second while the sign-in screen is up (from the end of its reveal).
    Timer { interval: 1000; repeat: true; triggeredOnStart: true; running: !root.unlocking && root.phase === "signin" && !revealAnim.running && !authenticator.unlocked; onTriggered: authenticator.startAuthenticating() }
    property bool unlocking: false
    property string deferredUnlock: ""   // "face" | "other": matched while the clock was showing

    // Never locked out. kscreenlocker kills a PAM worker for good when it is cancelled or stopped
    // (PamAuthenticator::cancel(): no restart; "DBus worker not initialized" from then on), and a
    // PAM module can hang. If the password worker has not asked for the password for 5 s while
    // nothing is being checked (or it fails twice with no password sent: a crashed worker), the
    // lock screen starts again with new workers (see revive()).
    property real quietSince: Date.now()
    property int revivals: 0
    function revive() {
        if (unlocking) return
        revivals++
        root.log("FENESTRA_LOCK revive", revivals)
        // kscreenlocker builds new workers when the authenticator type changes (Smartcard, then
        // Regular: kde-smartcard's worker comes and goes). kscreenlocker_greet 6.8.2 crashes doing
        // so while a worker is dead (SIGSEGV, bench) — which also recovers: KWin's screen locker
        // (ksld) starts a new greeter with new workers at once, the session staying locked (after 3
        // restarts in one lock it shows its emergency screen). Either way the password works again.
        authenticator.authenticator = 2       // Authenticators.Smartcard
        Qt.callLater(() => { authenticator.authenticator = 0 })   // Authenticators.Regular
    }
    Timer {
        interval: 1000; repeat: true
        // Only while the sign-in screen is up (on the clock nothing is asked for, by design).
        running: !root.unlocking && !authenticator.unlocked && root.phase === "signin"
        onTriggered: {
            if (authenticator.promptForSecret !== "" || authenticator.busy || root.passwordInFlight) root.quietSince = Date.now()
            else if (Date.now() - root.quietSince > 5000) root.revive()
        }
    }

    // Commands of the buttons (power, accessibility) run from here: the flyouts close right away.
    Loader { id: execLoader; source: "Exec.qml" }
    function log(...args) { if (trace) console.info(...args) }
    function run(cmd, cb) { if (execLoader.item) execLoader.item.run(cmd, cb); else console.warn("FENESTRA_LOCK no executable engine for", cmd) }

    // ------------------------------------------------------------------ auth -------
    // Password: kscreenlocker's interactive "kde" PAM service, stock: nothing else ever runs in it, so
    // it answers whatever the camera or the reader do. Face and fingerprint: the non-interactive
    // "kde-fingerprint" worker, in parallel, through pam_fenestra_hello.so (Howdy and fprintd as
    // children with deadlines; packaging/lockscreen/fenestra-lock-hello).
    readonly property int fingerType: ScreenLocker.Authenticator.Fingerprint
    property bool promptPending: false   // PAM asked for the password and has no answer yet
    function isFaceMessage(m) { return /facial|face detection|autenticaci[oó]n facial|identified face|rostro|cara identificada/i.test(m || "") }
    function syncTypes() {
        fingerAvailable = (authenticator.authenticatorTypes & fingerType) !== 0
    }
    function submit() {
        if (password.text === "") return
        idle.restart()
        passwordSent = true
        if (promptPending) { promptPending = false; passwordInFlight = true; authenticator.respond(password.text) }
        else { pendingPassword = password.text; authenticator.startAuthenticating() }
    }
    function unlock(kind) {
        unlocking = true
        // The smile starts on this very frame; the PAM workers are stopped once it is drawn (stopping
        // them here cost one 26 ms frame).
        if (kind === "face") { faceState = "success"; prompt = "face"; hello.play("authentication"); return }  // quits after the smile
        authenticator.stopAuthenticating()
        phase = "welcome"
        quitTimer.start()
    }
    Timer {
        id: quitTimer; interval: 250
        onTriggered: {
            // The desktop portal opens it in the session (a child of the greeter would inherit its sandbox).
            if (root.pendingUrl !== "")
                root.run("gdbus call --session --dest org.freedesktop.portal.Desktop --object-path /org/freedesktop/portal/desktop --method org.freedesktop.portal.OpenURI.OpenURI '' '" + root.pendingUrl.replace(/'/g, "") + "' {}")
            Qt.quit()
        }
    }
    // A new PAM conversation: Howdy looks again (Windows: "Try again" / the face option).
    property bool faceMatched: false
    property bool passwordInFlight: false
    property int brokenFailures: 0
    property bool passwordSent: false
    // "Try again": pam_fenestra_hello tries the face twice per lock screen, then waits for this
    // (a file named after the greeter's pid, which is the worker's parent).
    function retryFace() {
        faceState = ""
        run("sh -c 'mkdir -p \"$XDG_RUNTIME_DIR/fenestra-hello\" && touch \"$XDG_RUNTIME_DIR/fenestra-hello/retry-$PPID\"'")
        authenticator.startAuthenticating()
    }
    function faceFailed() {
        if (faceState !== "searching") return
        faceState = "failed"; hello.stop()
        if (prompt === "face") prompt = "password"
    }
    Connections {
        target: authenticator
        function onSucceeded() {
            root.log("FENESTRA_LOCK succeeded", root.faceState, root.faceMatched)
            if (root.phase === "clock") { root.deferredUnlock = root.faceMatched ? "face" : "other"; return }
            root.unlock(root.faceMatched ? "face" : "other")
        }
        function onFailed(kind, auth) {
            root.log("FENESTRA_LOCK failed", kind)
            if (kind === root.fingerType) { root.fingerState = "failed"; root.faceFailed(); return }
            if (kind !== 0 || root.unlocking) return   // after a success the workers are being stopped
            root.promptPending = false
            if (!root.passwordInFlight) {
                // A failure with no password sent: the worker is dead or broken (a crashed worker
                // answers every call with "Not connected to D-Bus server"). Not a wrong password.
                if (++root.brokenFailures >= 2) { root.brokenFailures = 0; root.revive() }
                return
            }
            root.brokenFailures = 0
            root.passwordInFlight = false
            password.text = ""
            root.message = root.tr("The password is incorrect. Try again.", "La contraseña no es correcta. Inténtalo de nuevo.")
            root.prompt = "message"
            okButton.forceActiveFocus()
            authenticator.startAuthenticating()
        }
        function onInfoMessageChanged() {
            const m = authenticator.infoMessage
            root.log("FENESTRA_LOCK info", m)
            // Howdy 3: "Failure, timeout reached" / "Face detection timeout reached" when it gives up.
            if (root.faceState === "searching" && /timeout|failure|no face|not recogni|no se ha|tiempo/i.test(m)) { root.faceFailed(); return }
            if (root.isFaceMessage(m) && root.faceState !== "success") {
                root.faceAvailable = true; root.faceState = "searching"; hello.play("searching")
                if (root.prompt === "password" && password.text === "") root.prompt = "face"
            }
        }
        function onErrorMessageChanged() {
            root.log("FENESTRA_LOCK error", authenticator.errorMessage)
            if (root.isFaceMessage(authenticator.errorMessage)) root.faceFailed()
        }
        function onNoninteractiveInfo(kind, auth) {
            const m = auth ? auth.infoMessage : ""
            root.log("FENESTRA_LOCK ninfo", kind, m)
            if (kind !== root.fingerType) return
            // pam_fenestra_hello (face + fingerprint in the parallel worker) says what it is doing.
            if (/^Identified face/.test(m)) { root.faceMatched = true; return }
            if (/^Face not recognised/.test(m)) { root.faceFailed(); return }
            if (/^Fingerprint matched/.test(m)) { root.faceMatched = false; return }
            if (root.isFaceMessage(m)) {
                root.faceAvailable = true
                if (root.faceState !== "success") { root.faceState = "searching"; hello.play("searching") }
                if (root.prompt === "password" && password.text === "") root.prompt = "face"
                return
            }
            root.fingerAvailable = true; root.fingerState = "waiting"
        }
        function onNoninteractiveError(kind, auth) {
            if (kind === root.fingerType) root.fingerState = "failed"
        }
        function onPromptForSecretChanged() {
            root.promptPending = true
            root.passwordInFlight = false
            if (root.pendingPassword !== "") {
                root.promptPending = false
                root.passwordInFlight = true
                authenticator.respond(root.pendingPassword); root.pendingPassword = ""
            }
        }
        function onAuthenticatorTypesChanged() { root.syncTypes() }
    }
    Component.onCompleted: {
        syncTypes()
        // Nothing is checked until the clock is dismissed (showSignin starts face, fingerprint and
        // the password together).
        root.forceActiveFocus()
    }

    // ------------------------------------------------------------------ background --
    // "Picture": today's Spotlight photo (Fenestra Shell writes it); "Background": older shells' key.
    readonly property string background: cfg("Picture", cfg("Background", "/usr/share/backgrounds/fenestra/fenestra-bloom-dark.jpg"))
    Rectangle { anchors.fill: parent; color: "#000000" }
    Item {
        id: scene
        anchors.fill: parent
        visible: !root.highContrast
        scale: 1 + 0.02 * root.p
        Image {
            id: picture
            anchors.fill: parent
            source: root.background !== "" ? "file://" + root.background : ""
            fillMode: Image.PreserveAspectCrop
            sourceSize: Qt.size(Math.ceil(root.width * Screen.devicePixelRatio), Math.ceil(root.height * Screen.devicePixelRatio))
            smooth: true; cache: false; asynchronous: false
        }
        // Acrylic sign-in background: rendered once into a layer, faded in with the dim.
        Item {
            anchors.fill: parent
            visible: root.cfg("SigninBlur", true) !== false && root.cfg("SigninBlur", true) !== "false"
            // Never quite 0: the blur is rendered into its layer while the clock shows, so the first
            // frame of the reveal does not pay for it (it cost one 49 ms frame). 0.3 % is below 1/255.
            opacity: Math.max(0.003, root.p)
            layer.enabled: visible
            MultiEffect {
                anchors.fill: parent
                source: picture
                autoPaddingEnabled: false
                blurEnabled: true; blur: 1.0; blurMax: 64; blurMultiplier: 0.5
            }
        }
    }
    Rectangle { anchors.fill: parent; color: "#000000"; opacity: 0.194 + (0.458 - 0.194) * root.p }   // measured 0.202 / 0.466 (rendering adds 0.008)

    // ------------------------------------------------------------------ clock view --
    // Measured: 2880 x 1800 @ 150 % (1200 px high): time 135 px, digit tops at 163.3; 1920 x 1080
    // @ 150 % (720 px): 96.7 px, 128.7. Both grow linearly with the height.
    readonly property real clockPx: 96.7 + (height - 720) * (135 - 96.7) / 480
    readonly property real clockK: clockPx / 135
    Item {
        id: clockView
        anchors.fill: parent
        opacity: 1 - root.exitP
        visible: opacity > 0
        transform: Translate { y: -40 * root.exitP * root.exitP }
        property date now: new Date()
        Timer { interval: 1000; running: clockView.visible; repeat: true; onTriggered: clockView.now = new Date() }
        Text {
            id: time
            anchors.horizontalCenter: parent.horizontalCenter
            // digits' top = 128.7 + (h - 720) * 0.0721; the Text box starts above them by the font's
            // ascent minus its cap height (0.928 - 0.7 of the size for Segoe UI Variable Display).
            y: 128.7 + (root.height - 720) * (163.3 - 128.7) / 480 - root.clockPx * 0.3655
            text: Qt.formatTime(clockView.now, Qt.locale().timeFormat(Locale.ShortFormat).replace(/\s*(AP|ap|A|a)\s*/g, "").replace(/[:.]ss/, ""))
            color: "white"
            font.family: Fluent.text; font.pixelSize: root.clockPx; font.weight: Font.DemiBold
            font.variableAxes: ({ "opsz": 36 })
            renderType: Text.QtRendering
        }
        Text {
            id: date
            anchors.horizontalCenter: parent.horizontalCenter
            y: time.y + (306 - 163.3 + 0.3655 * 135 + 13.3 - 16) * root.clockK - 27.67 * root.clockK * 0.262
            text: { const s = clockView.now.toLocaleDateString(Qt.locale(), root.es ? "dddd, d 'de' MMMM" : "dddd, MMMM d"); return root.es ? s : s }
            color: "white"
            font.family: Fluent.text; font.pixelSize: 27.67 * root.clockK; font.weight: Font.DemiBold
            font.variableAxes: ({ "opsz": 36 })
            renderType: Text.QtRendering
        }
        Loader {
            // Network and battery at the bottom right (StatusIcons.qml): the rightmost glyph centred
            // 48 px from the right and 28 px over the bottom (measured, network glyph).
            id: statusIcons
            anchors { right: parent.right; bottom: parent.bottom
                      rightMargin: 48 - (item && item.hasBattery ? 8.75 : 7); bottomMargin: 28 - (item ? item.height / 2 : 7) }
            source: "StatusIcons.qml"
        }
        // Spotlight's "Learn more about this picture" (magnifier) and hotspots: left out at the
        // user's request (the picture alone, no info button). Spotlight.qml stays for opting back in.
        // Widgets (24H2): the weather card, bottom centre, 50 px over the bottom; media above it.
        WeatherCard {
            id: weatherCard
            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 50 }
            onForecast: root.openAfterUnlock("https://www.msn.com/weather")
        }
        Loader {
            anchors { horizontalCenter: parent.horizontalCenter; bottom: weatherCard.visible ? weatherCard.top : parent.bottom; bottomMargin: weatherCard.visible ? 16 : 50 }
            source: "MediaCard.qml"
        }
    }

    // ------------------------------------------------------------------ sign-in ----
    // The account block: its top (the picture's circle) at half the height minus 226.7 px.
    readonly property real stackTop: height / 2 - 226.67
    Item {
        id: signin
        anchors.fill: parent
        opacity: root.p
        visible: opacity > 0
        enabled: root.phase !== "clock"

        // Account picture: a 192 px circle (white at 5.5 %) with Windows' default person, or the
        // user's own picture.
        Item {
            id: avatar
            width: 192; height: 192
            x: (root.width - width) / 2; y: root.stackTop
            Rectangle { anchors.fill: parent; radius: width / 2; color: Qt.rgba(1, 1, 1, 0.055); visible: !userPic.visible }
            Shape {
                visible: !userPic.visible
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                // Head: 49.3 px circle, top 45 px under the circle's top; body 87.3 x 44 px.
                ShapePath {
                    fillColor: Qt.rgba(1, 1, 1, 0.92); strokeColor: "transparent"
                    PathAngleArc { centerX: 96; centerY: 45.3 + 24.7; radiusX: 24.7; radiusY: 24.7; startAngle: 0; sweepAngle: 360 }
                }
                ShapePath {
                    fillColor: Qt.rgba(1, 1, 1, 0.92); strokeColor: "transparent"
                    startX: 52.3 + 9; startY: 100.7
                    PathLine { x: 139.7 - 9; y: 100.7 }
                    PathArc { x: 139.7; y: 100.7 + 9; radiusX: 9; radiusY: 9 }
                    PathArc { x: 52.3; y: 100.7 + 9; radiusX: 43.7; radiusY: 35; useLargeArc: false }
                    PathArc { x: 52.3 + 9; y: 100.7; radiusX: 9; radiusY: 9 }
                }
            }
            Image {
                id: userPic
                anchors.fill: parent
                visible: root.userImage !== "" && status === Image.Ready
                source: root.userImage !== "" ? "file://" + root.userImage : ""
                sourceSize: Qt.size(192 * Screen.devicePixelRatio, 192 * Screen.devicePixelRatio)
                fillMode: Image.PreserveAspectCrop
                layer.enabled: visible
                layer.effect: MultiEffect { maskEnabled: true; maskSource: circleMask }
            }
            Rectangle { id: circleMask; anchors.fill: parent; radius: width / 2; visible: false; layer.enabled: true }
        }
        Text {
            id: name
            anchors.horizontalCenter: parent.horizontalCenter
            y: root.stackTop + 217.3 - 28 * 0.262 - 28 * 0.25
            text: root.userName
            color: "white"
            font.family: Fluent.text; font.pixelSize: 28; font.weight: Font.DemiBold
            font.variableAxes: ({ "opsz": Fluent.opsz(28) })
            renderType: Text.QtRendering
        }

        // ---- prompt: password box (296 x 32, top at +272.3) ----
        Item {
            id: field
            width: 296; height: 32
            x: (root.width - width) / 2; y: root.stackTop + 272.3
            visible: root.prompt === "password" && root.phase !== "welcome"
            property real shake: 0
            transform: Translate { x: field.shake }
            Rectangle {
                anchors.fill: parent; radius: 4
                color: password.activeFocus ? Qt.rgba(30 / 255, 30 / 255, 30 / 255, 0.70) : Qt.rgba(1, 1, 1, 0.06)
                border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.08)
            }
            // Bottom edge: 1 px grey, 2 px accent with the focus.
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 1.33; rightMargin: 1.33 }
                height: password.activeFocus ? 2 : 1
                color: password.activeFocus ? root.accent : Qt.rgba(1, 1, 1, 0.54)
            }
            TextInput {
                id: password
                x: 9.33; width: parent.width - x - (reveal.visible ? 64 : 40)
                anchors.verticalCenter: parent.verticalCenter
                echoMode: reveal.held ? TextInput.Normal : TextInput.Password
                passwordCharacter: "●"
                color: "white"; selectionColor: root.accent; selectedTextColor: "white"
                font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                font.letterSpacing: echoMode === TextInput.Password ? 0.2 : 0
                // Windows' caret: 2 device px wide, 19.3 px high.
                cursorDelegate: Rectangle { width: 1.33; height: 19.3; color: "white"; visible: password.cursorVisible }
                clip: true
                renderType: Text.QtRendering
                Text {
                    visible: !parent.text && !parent.preeditText
                    text: root.tr("Password", "Contraseña")
                    color: Qt.rgba(1, 1, 1, 0.786)
                    font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                    renderType: Text.QtRendering
                }
                onTextChanged: idle.restart()
                onAccepted: root.submit()
                // Windows: Esc closes a flyout or clears the box; it does not bring the clock back.
                Keys.onEscapePressed: { if (root.menu !== "") root.menu = ""; else text = "" }
            }
            // Reveal (press and hold) and submit, 24 x 24 each; hover: white 6 %.
            FieldButton {
                id: reveal
                visible: password.text !== ""
                property bool held: pressed
                anchors { right: submitButton.left; verticalCenter: parent.verticalCenter; verticalCenterOffset: -2.7; rightMargin: 8.7 }
                glyph: "\uE7B3"; fallback: Qt.resolvedUrl("icons/reveal.svg")
                onPressedChanged: password.forceActiveFocus()
            }
            FieldButton {
                id: submitButton
                anchors { right: parent.right; verticalCenter: parent.verticalCenter; verticalCenterOffset: -3.7; rightMargin: 8.3 }
                glyph: "\uE72A"; fallback: Qt.resolvedUrl("icons/arrow.svg")
                onClicked: root.submit()
            }
            SequentialAnimation {
                id: shake
                NumberAnimation { target: field; property: "shake"; to: -10; duration: 50 }
                NumberAnimation { target: field; property: "shake"; to: 10; duration: 100 }
                NumberAnimation { target: field; property: "shake"; to: 0; duration: 50 }
            }
        }

        // ---- prompt: Windows Hello (face) ----
        Column {
            id: faceBlock
            anchors.horizontalCenter: parent.horizontalCenter
            y: root.stackTop + 256
            spacing: 4
            visible: root.prompt === "face" && root.phase !== "welcome"
            Hello {
                id: hello
                anchors.horizontalCenter: parent.horizontalCenter
                size: 64
                onFinished: { authenticator.stopAuthenticating(); root.phase = "welcome"; quitTimer.interval = 1; quitTimer.start() }
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.faceState === "failed" ? root.tr("Couldn't recognise you", "No te hemos reconocido")
                    : root.faceState === "success" ? root.tr("Welcome", "Te damos la bienvenida")
                    : root.tr("Looking for you…", "Buscándote…")
                color: "white"
                font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                renderType: Text.QtRendering
            }
            FluentButton {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: root.faceState === "failed"
                text: root.tr("Try again", "Volver a intentarlo")
                onClicked: root.retryFace()
            }
        }

        // ---- prompt: fingerprint ----
        Column {
            id: fingerBlock
            anchors.horizontalCenter: parent.horizontalCenter
            y: root.stackTop + 272.3
            spacing: 12
            visible: root.prompt === "fingerprint" && root.phase !== "welcome"
            Glyph { anchors.horizontalCenter: parent.horizontalCenter; glyph: "\uE928"; size: 32; fallback: Qt.resolvedUrl("icons/fingerprint.svg") }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.fingerState === "failed" ? root.tr("Couldn't recognise that fingerprint. Try again.", "No se reconoció la huella digital. Inténtalo de nuevo.")
                    : root.tr("Scan your finger on the fingerprint reader", "Escanea tu dedo en el lector de huellas digitales")
                color: "white"
                font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                renderType: Text.QtRendering
            }
        }

        // ---- prompt: message + OK (wrong password); text tops at +301.3, button 120 x 32 at +355 ----
        Text {
            id: messageText
            anchors.horizontalCenter: parent.horizontalCenter
            width: 456; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
            y: root.stackTop + 301.3 - 14 * 0.262 - 14 * 0.25
            visible: root.prompt === "message" && root.phase !== "welcome"
            text: root.message
            color: "white"
            font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
            renderType: Text.QtRendering
        }
        FluentButton {
            id: okButton
            x: (root.width - width) / 2; y: root.stackTop + 355
            visible: messageText.visible
            text: root.tr("OK", "Aceptar")
            onClicked: { root.prompt = "password"; root.message = ""; password.forceActiveFocus() }
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            Keys.onSpacePressed: clicked()
        }

        // ---- Welcome: 32 px ring centred at +292.4, the text's tops at +350 ----
        Item {
            visible: root.phase === "welcome" && root.faceState !== "success"
            anchors.fill: parent
            ProgressRing { x: (root.width - 32) / 2; y: root.stackTop + 292.4 - 16 }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                y: root.stackTop + 350 - 24 * 0.262 - 24 * 0.25
                text: root.tr("Welcome", "Te damos la bienvenida")
                color: "white"
                font.family: Fluent.text; font.pixelSize: 24; font.weight: Font.DemiBold; font.variableAxes: ({ "opsz": Fluent.opsz(24) })
                renderType: Text.QtRendering
            }
        }

        // ---- Sign-in options (several ways to sign in) ----
        Column {
            id: options
            anchors.horizontalCenter: parent.horizontalCenter
            y: (root.prompt === "face" ? faceBlock.y + faceBlock.height : root.prompt === "fingerprint" ? fingerBlock.y + fingerBlock.height : root.stackTop + 272.3 + 32) + 20
            spacing: 8
            visible: (root.faceAvailable || root.fingerAvailable) && root.phase === "signin" && root.prompt !== "message" && root.faceState !== "success"
            property bool open: false
            Text {
                id: optionsLink
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.tr("Sign-in options", "Opciones de inicio de sesión")
                color: optMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.786) : "white"
                font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                renderType: Text.QtRendering
                MouseArea { id: optMouse; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true; onClicked: options.open = !options.open }
            }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 8
                visible: options.open
                Repeater {
                    model: [{ k: "face", g: "\uEB68", f: "icons/face.svg", show: root.faceAvailable, tip: root.tr("Facial recognition (Windows Hello)", "Reconocimiento facial (Windows Hello)") },
                            { k: "fingerprint", g: "\uE928", f: "icons/fingerprint.svg", show: root.fingerAvailable, tip: root.tr("Fingerprint recognition (Windows Hello)", "Reconocimiento de huellas digitales (Windows Hello)") },
                            { k: "password", g: "\uE8D7", f: "icons/key.svg", show: true, tip: root.tr("Password", "Contraseña") }]
                    CornerButton {
                        visible: modelData.show
                        glyph: modelData.g; fallback: Qt.resolvedUrl(modelData.f)
                        checked: root.prompt === modelData.k
                        onClicked: {
                            root.prompt = modelData.k
                            if (modelData.k === "face" && root.faceState === "failed") root.retryFace()
                            if (modelData.k === "password") password.forceActiveFocus()
                        }
                    }
                }
            }
        }

        // ---- Corner buttons: 40 x 40, centres 44.3 / 92.3 / 140.3 px from the right, 42.3 over the bottom ----
        Row {
            id: corner
            visible: root.phase === "signin"
            anchors { right: parent.right; bottom: parent.bottom; rightMargin: 44.3 - 20; bottomMargin: 42.3 - 20 }
            spacing: 8
            layoutDirection: Qt.RightToLeft
            CornerButton {
                id: powerButton
                glyph: "\uE7E8"; fallback: Qt.resolvedUrl("file:///usr/share/fenestra/assets/security/power.svg")
                checked: root.menu === "power"
                accessibleName: root.tr("Power", "Inicio/Apagado")
                onClicked: root.menu = root.menu === "power" ? "" : "power"
            }
            CornerButton {
                id: a11yButton
                glyph: "\uE776"; fallback: Qt.resolvedUrl("file:///usr/share/fenestra/assets/security/accessibility.svg")
                checked: root.menu === "accessibility"
                accessibleName: root.tr("Accessibility", "Accesibilidad")
                onClicked: root.menu = root.menu === "accessibility" ? "" : "accessibility"
            }
            CornerButton {
                id: netButton
                glyph: netStatus.item ? netStatus.item.glyph : "\uE839"
                fallback: netStatus.item && netStatus.item.kind !== "wired" ? netStatus.item.icon : "file:///usr/share/fenestra/assets/security/network-wired.svg"
                checked: root.menu === "network"
                accessibleName: root.tr("Network", "Red")
                onClicked: root.menu = root.menu === "network" ? "" : "network"
            }
            Loader {
                // Keyboard layout ("ESP"): only with more than one layout.
                source: "KeyboardButton.qml"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Loader { id: netStatus; source: "NetworkStatus.qml"; visible: false }

        // Click outside a flyout closes it (as Windows' light dismiss).
        MouseArea {
            anchors.fill: parent
            visible: root.menu !== ""
            z: 1
            onPressed: (m) => { root.menu = ""; m.accepted = true }
        }
        Loader {
            z: 2
            active: root.menu === "network"
            source: "NetworkFlyout.qml"
            anchors { right: parent.right; bottom: parent.bottom; rightMargin: 24.7; bottomMargin: 70.7 }
        }
        Loader {
            z: 2
            active: root.menu === "accessibility"
            source: "AccessibilityFlyout.qml"
            anchors { right: parent.right; bottom: parent.bottom; rightMargin: 12.7; bottomMargin: 76 }
        }
        Loader {
            z: 2
            active: root.menu === "power"
            source: "PowerMenu.qml"
            anchors { right: parent.right; bottom: parent.bottom; rightMargin: 1.3; bottomMargin: 66.7 }
        }
    }

    Loader {
        active: root.osk && root.phase === "signin"
        z: 3
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 96 }
        sourceComponent: Osk {
            onTyped: (t) => { root.prompt = "password"; password.insert(password.cursorPosition, t); password.forceActiveFocus() }
            onBackspace: { if (password.cursorPosition > 0) password.remove(password.cursorPosition - 1, password.cursorPosition) }
            onEnter: root.submit()
        }
    }

    // Volume, brightness, keyboard light and performance mode banners (Fenestra Shell sends them
    // while locked; kscreenlocker_greet finds the item by its objectName "onScreenDisplay").
    LockOsd { z: 4; accent: root.accent }

    // Frame trace for the bench (config Trace=true): one line per presented frame while something
    // moves, so dropped frames and the curves can be read from the greeter's log.
    readonly property bool trace: cfg("Trace", false) === true || cfg("Trace", false) === "true"
    property real lastSwap: 0
    Connections {
        target: root.trace ? root.Window.window : null
        function onFrameSwapped() {
            const now = Date.now()
            if (revealAnim.running || hideAnim.running || hello.mode !== "")
                console.info("FENESTRA_FRAME", now, now - root.lastSwap, root.t.toFixed(1), hello.cell)
            root.lastSwap = now
        }
    }

    // ------------------------------------------------------------------ input ------
    focus: true
    Keys.onPressed: (e) => {
        // Volume, brightness, keyboard light and media keys act on the lock screen (kscreenlocker
        // runs their shortcuts) without raising the sign-in screen, as on Windows.
        if ([Qt.Key_VolumeUp, Qt.Key_VolumeDown, Qt.Key_VolumeMute, Qt.Key_MicMute, Qt.Key_MonBrightnessUp, Qt.Key_MonBrightnessDown,
             Qt.Key_KeyboardBrightnessUp, Qt.Key_KeyboardBrightnessDown, Qt.Key_KeyboardLightOnOff, Qt.Key_MediaPlay, Qt.Key_MediaPause,
             Qt.Key_MediaTogglePlayPause, Qt.Key_MediaNext, Qt.Key_MediaPrevious, Qt.Key_MediaStop, Qt.Key_Launch0, Qt.Key_Launch1,
             Qt.Key_Launch2, Qt.Key_LaunchMedia, Qt.Key_Tools].indexOf(e.key) >= 0) { e.accepted = true; return }
        if (root.phase === "clock") {
            const ch = e.text.length === 1 && e.text.charCodeAt(0) >= 32 ? e.text : ""
            if (e.key === Qt.Key_Escape) { e.accepted = true; return }
            root.showSignin(ch); e.accepted = true
        } else if (e.key === Qt.Key_Escape && root.menu !== "") { root.menu = ""; e.accepted = true }
        else if ((root.prompt === "password" || root.prompt === "face") && !password.activeFocus && e.text.length === 1 && e.text.charCodeAt(0) >= 32) {
            // Typing while Hello looks (or anywhere): the characters go to the password box.
            root.prompt = "password"; password.forceActiveFocus(); password.insert(password.cursorPosition, e.text); e.accepted = true
        }
        idle.restart()
    }
    MouseArea {
        anchors.fill: parent
        z: -1
        enabled: root.phase === "clock"
        onClicked: root.showSignin("")
        // Swipe up on touch screens, as Windows' curtain.
        property real y0: 0
        onPressed: (m) => y0 = m.y
        onReleased: (m) => { if (y0 - m.y > 60) root.showSignin("") }
    }
}

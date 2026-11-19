// SPDX-License-Identifier: GPL-3.0-or-later
// Windows Hello face animation ("searching" loops while the camera looks, "authentication" plays
// once on success). The frames are one texture atlas made by tools/hello-atlas.py: every frame is
// a cell of it, and playing only moves the atlas under a clipping window (no texture upload, no
// decoding while it plays). The frame index follows the animation clock (vsync), not a Timer.
// Frames: the user's own (~/.local/share/fenestra/assets/hello-windows, made from their Windows'
// animation), else Fenestra's open drawing (/usr/share/fenestra/assets/hello).
import QtQuick
import QtCore

Item {
    id: hello
    property string mode: ""            // "" | "searching" | "authentication"
    property real size: 64              // canvas (the source's 300 x 300 box), logical px
    signal finished()                   // the authentication sequence reached its last frame

    readonly property var candidates: {
        const home = StandardPaths.writableLocation(StandardPaths.GenericDataLocation).toString()
        return [home + "/fenestra/assets/hello-windows/frames.qml", home + "/fenestra/assets/hello/frames.qml",
                "file:///usr/share/fenestra/assets/hello/frames.qml"]
    }
    property int candidate: 0
    Loader {
        id: manifest
        source: hello.candidate < hello.candidates.length ? hello.candidates[hello.candidate] : ""
        onStatusChanged: if (status === Loader.Error) hello.candidate++
    }
    readonly property var frames: manifest.status === Loader.Ready ? manifest.item : null
    readonly property bool ready: frames !== null && atlas.status === Image.Ready

    // Cumulative ends of the current sequence (ms) for a binary search per frame.
    readonly property var seq: frames && mode !== "" ? frames[mode] : []
    readonly property var ends: { let t = 0; return seq.map(f => t += f[1]) }
    readonly property real total: ends.length ? ends[ends.length - 1] : 1
    property real clock: 0
    readonly property int cell: {
        if (!ends.length) return 0
        let lo = 0, hi = ends.length - 1
        while (lo < hi) { const mid = (lo + hi) >> 1; if (clock < ends[mid]) hi = mid; else lo = mid + 1 }
        return seq[lo][0]
    }
    NumberAnimation on clock {
        id: player
        running: false; from: 0; to: hello.total
        duration: hello.total; easing.type: Easing.Linear
        onFinished: if (hello.mode === "authentication") hello.finished()
    }
    function play(m) {
        if (mode === m && player.running) return
        player.stop(); mode = m; clock = 0
        player.loops = m === "searching" ? Animation.Infinite : 1
        // The smile at its own speed, without the still frame it ends on (200 ms of the user's
        // Windows animation): the desktop fades in from that frame instead of after it.
        const end = m === "authentication" ? total - trailingHold() : total
        player.to = end; player.duration = end
        player.start()
    }
    function stop() { player.stop(); mode = "" }
    // A last entry that only shows again a frame already shown (a pause at the end).
    function trailingHold() {
        if (seq.length < 2) return 0
        const last = seq[seq.length - 1]
        for (let i = 0; i < seq.length - 1; ++i)
            if (seq[i][0] === last[0]) return last[1]
        return 0
    }

    width: size; height: size
    visible: mode !== "" && ready
    clip: true
    Image {
        id: atlas
        // Decoded while the lock screen starts, long before the camera answers.
        asynchronous: false
        cache: true
        smooth: true; mipmap: false
        source: hello.frames ? Qt.resolvedUrl(hello.candidates[hello.candidate]).toString().replace(/frames\.qml$/, hello.frames.atlas) : ""
        readonly property int cols: hello.frames ? hello.frames.cols : 1
        readonly property real k: hello.size / (hello.frames ? hello.frames.cellSize : 1)
        width: sourceSize.width * k; height: sourceSize.height * k
        x: -(hello.cell % cols) * hello.size
        y: -Math.floor(hello.cell / cols) * hello.size
    }
}

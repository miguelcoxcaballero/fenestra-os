// SPDX-License-Identifier: GPL-3.0-or-later
// Runs a command for the lock screen's buttons (Plasma's "executable" data engine): power, the
// accessibility switches. The greeter's environment sets KDE_HOME_READONLY; commands that write
// the user's settings unset it themselves.
import QtQuick
import org.kde.plasma.plasma5support as P5Support

P5Support.DataSource {
    id: ds
    engine: "executable"
    connectedSources: []
    property var callbacks: ({})
    onNewData: (source, data) => {
        const cb = callbacks[source]
        delete callbacks[source]
        disconnectSource(source)
        if (cb) cb(String(data["stdout"] || ""), Number(data["exit code"] || 0))
    }
    function run(cmd, cb) {
        // The same command twice in a row would be one source: make each run unique.
        const key = cmd + " #" + Date.now() + Math.random()
        callbacks[key] = cb
        connectSource(key)
    }
}

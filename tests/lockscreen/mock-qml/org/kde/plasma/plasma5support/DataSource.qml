// Bench stand-in for Plasma's data engines: "executable" logs the command (FENESTRA_EXEC) and
// answers like the real tools; "powermanagement" reports a laptop battery at 76 %, unplugged.
import QtQuick
QtObject {
    id: ds
    property string engine
    property var connectedSources: []
    property var data: engine === "powermanagement" ? { "Battery": { "Has Battery": true, "Percent": 76, "State": "Discharging" }, "AC Adapter": { "Plugged in": false } } : ({})
    signal newData(string sourceName, var data)
    function connectSource(s) {
        console.info("FENESTRA_EXEC", s.replace(/ #[0-9.]+$/, ""))
        Qt.callLater(() => ds.newData(s, { "stdout": s.indexOf("kreadconfig6") >= 0 ? "false\n" : "", "exit code": s.indexOf("pgrep") >= 0 ? 1 : 0 }))
    }
    function disconnectSource(s) {}
}

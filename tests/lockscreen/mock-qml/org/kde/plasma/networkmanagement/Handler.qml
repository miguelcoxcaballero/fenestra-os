// Logs what the lock screen asks NetworkManager to do ("FENESTRA_NM ..." on stderr).
import QtQuick
QtObject {
    function activateConnection(c, d, s) { console.info("FENESTRA_NM activate", c, d, s) }
    function addAndActivateConnection(d, s, p) { console.info("FENESTRA_NM add", d, s, p ? "with-key" : "no-key") }
    function deactivateConnection(c, d) { console.info("FENESTRA_NM deactivate", c, d) }
    function enableWireless(on) { console.info("FENESTRA_NM wireless", on) }
    function enableAirplaneMode(on) { console.info("FENESTRA_NM airplane", on) }
    function requestScan() { console.info("FENESTRA_NM scan") }
}

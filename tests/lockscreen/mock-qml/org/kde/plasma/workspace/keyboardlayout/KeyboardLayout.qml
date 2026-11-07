// Bench stand-in: two layouts, Spanish and US English (as the user's laptop).
import QtQuick
QtObject {
    property int layout: 0
    property var layoutsList: [{ shortName: "es", displayName: "", longName: "Español" }, { shortName: "us", displayName: "", longName: "English (US)" }]
    function switchToNextLayout() { layout = (layout + 1) % layoutsList.length; console.info("FENESTRA_KB", layoutsList[layout].shortName) }
}

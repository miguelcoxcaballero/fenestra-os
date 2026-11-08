// SPDX-License-Identifier: GPL-3.0-or-later
// The weather widget of Windows 11 24H2's lock screen (clock view, bottom centre), measured on the
// reference VM at 2880 x 1800 / 150 %: 296 x 142.7 px, #2C2C2C, radius 8, its bottom 50 px over the
// screen's; the place (14 px Semibold) at 14 / 16.7, a 54.7 px icon at 17.3 / 45.3, the
// temperature (48 px Semibold) with its unit (14 px) after it, the condition right-aligned 12.7 px
// from the right edge, and "See full forecast" (12 px) in the light accent, ink 120.7 px down. The data is
// the taskbar's weather, written by Fenestra Shell into the lock screen's settings.
import QtQuick

Item {
    id: card
    readonly property string temp: root.cfg("WeatherTemperature", "")
    visible: temp !== ""
    width: 296; height: 142.7
    signal forecast()
    // The text box's top above a glyph's ink top (Segoe UI Variable: ascent - cap height ≈ 0.512 em).
    function inkTop(ink, px) { return ink - px * 0.512 }
    Rectangle { anchors.fill: parent; radius: 8; color: "#2c2c2c" }
    Text {
        x: 14; y: card.inkTop(16.7, 14)
        width: parent.width - 28; elide: Text.ElideRight
        text: root.cfg("WeatherLocation", "")
        color: "white"
        font.family: Fluent.text; font.pixelSize: 14; font.weight: Font.DemiBold; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
        renderType: Text.QtRendering
    }
    Image {
        x: 17.3; y: 45.3; width: 54.7; height: 54.7
        source: root.cfg("WeatherIcon", "") !== "" ? "file://" + root.cfg("WeatherIcon", "") : ""
        sourceSize: Qt.size(Math.ceil(width * Screen.devicePixelRatio), Math.ceil(height * Screen.devicePixelRatio))
        smooth: true
    }
    Text {
        id: degrees
        x: 85.7; y: card.inkTop(66, 48)
        text: card.temp
        color: "white"
        font.family: Fluent.text; font.pixelSize: 48; font.weight: Font.DemiBold; font.variableAxes: ({ "opsz": 36 })
        renderType: Text.QtRendering
    }
    Text {
        anchors.left: degrees.right; anchors.leftMargin: -0.7
        y: card.inkTop(59.3, 14)
        text: root.cfg("WeatherUnit", "°C")
        color: "white"
        font.family: Fluent.text; font.pixelSize: 14; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
        renderType: Text.QtRendering
    }
    Column {
        anchors { right: parent.right; rightMargin: 12.7 }
        y: card.inkTop(61.3, 14)
        width: 120
        Repeater {
            model: [root.cfg("WeatherCondition", ""), root.cfg("WeatherFeelsLike", "") !== "" ? root.tr("Feels like ", "Sensación ") + root.cfg("WeatherFeelsLike", "") : ""]
            Text {
                width: 120; horizontalAlignment: Text.AlignRight
                visible: modelData !== ""
                text: modelData; color: "white"; elide: Text.ElideLeft
                lineHeightMode: Text.FixedHeight; lineHeight: 18.3
                font.family: Fluent.text; font.pixelSize: 14; font.weight: Font.DemiBold; font.variableAxes: ({ "opsz": Fluent.opsz(14) })
                renderType: Text.QtRendering
            }
        }
    }
    Text {
        id: link
        anchors.horizontalCenter: parent.horizontalCenter
        y: card.inkTop(120.7, 12)
        text: root.tr("See full forecast", "Ver pronóstico completo")
        // AccentTextFillColorPrimary in dark mode: the accent lightened (#0078D4 gives #99EBFF).
        color: root.lightAccent
        font.family: Fluent.text; font.pixelSize: 12; font.underline: linkMouse.containsMouse; font.variableAxes: ({ "opsz": Fluent.opsz(12) })
        renderType: Text.QtRendering
        MouseArea { id: linkMouse; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true; onClicked: card.forecast() }
    }
}

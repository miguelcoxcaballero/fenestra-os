import QtQuick
// Window under test: textured so position, scale and opacity can be measured on every frame.
Window { width: 640; height: 420; visible: true; title: "Motion Qt"; color: "#f3f3f3"
    Grid { anchors.fill: parent; anchors.margins: 24; columns: 8; spacing: 8
        Repeater { model: 40; Rectangle { width: 66; height: 62; radius: 4; color: Qt.hsla((index * 0.137) % 1, 0.6, 0.5, 1) } } } }

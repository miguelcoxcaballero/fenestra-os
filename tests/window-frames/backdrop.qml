import QtQuick
// Stand-in wallpaper: the user's sage green with a soft gradient, so shadows and corners show.
Window { visible: true; title: "Backdrop"; width: 1800; height: 1125; flags: Qt.FramelessWindowHint
    Rectangle { anchors.fill: parent; gradient: Gradient { GradientStop { position: 0; color: "#4d6b62" } GradientStop { position: 1; color: "#3f5a52" } } } }

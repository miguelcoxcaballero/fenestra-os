// Bench stand-in: one player (Spotify-like) playing. (Its Previous/PlayPause/Next are C++ slots in
// the real module and cannot be written in QML: the buttons are checked on a real session.)
import QtQuick
ListModel {
    Component.onCompleted: append({ track: "Mediterráneo", artist: "Joan Manuel Serrat", identity: "Spotify", artUrl: "", playbackStatus: 2, canGoPrevious: true, canGoNext: true, canControl: true })
}

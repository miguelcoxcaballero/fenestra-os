// SPDX-License-Identifier: GPL-3.0-or-later
// The live picture of one window in the taskbar preview (B03): KWin's screencast of the window
// (ScreencastStream, services/screencast.h) drawn by KPipeWire's PipeWireSourceItem, as Plasma's
// task manager does. Loaded by TaskPreview.qml through a Loader: without KPipeWire (org.kde.pipewire)
// this file does not load and the preview falls back to KWin's still pictures (WindowSnapshot).
import QtQuick
import org.kde.pipewire as PipeWire
import Fenestra.Shell

Item {
    id: thumb
    property string uuid
    property bool active: true
    // The stream draws (first frame in); false while it connects, and when KWin cannot stream.
    readonly property bool live: source.ready
    // KWin will never stream this window (no protocol, refused): the caller takes stills instead.
    readonly property bool unavailable: !stream.available
                                        || source.state === PipeWire.PipeWireSourceItem.StreamState.Error

    ScreencastStream { id: stream; uuid: thumb.uuid; enabled: thumb.active && thumb.uuid !== "" }
    PipeWire.PipeWireSourceItem {
        id: source
        anchors.fill: parent
        nodeId: stream.nodeId
        objectSerial: stream.objectSerial
        // Kept visible: KPipeWire only lets the stream run while the item is visible.
        opacity: ready ? 1 : 0
    }
}

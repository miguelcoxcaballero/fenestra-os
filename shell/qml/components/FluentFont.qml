// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick

QtObject {
    // Segoe Fluent Icons is installed (a Windows font pack): glyphs are drawn from it.
    readonly property bool available: Qt.fontFamilies().indexOf("Segoe Fluent Icons") >= 0
}

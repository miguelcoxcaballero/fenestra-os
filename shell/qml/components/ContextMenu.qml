// SPDX-License-Identifier: GPL-3.0-or-later
// Menu flyout: model is a list of {text, icon, action} (action: a JS function), "-" for a separator.
import QtQuick
import Fenestra.Shell

Flyout {
    id: menu
    property var items: []
    Column {
        spacing: 0
        Repeater {
            model: menu.items
            delegate: Loader {
                required property var modelData
                sourceComponent: modelData === "-" ? separator : entry
                Component {
                    id: entry
                    MenuRow {
                        text: modelData.text
                        iconName: modelData.icon || ""
                        iconSource: modelData.iconSource || ""
                        onTriggered: { menu.close(); modelData.action() }
                    }
                }
                Component {
                    id: separator
                    Item { width: 220; height: 9; Rectangle { anchors.centerIn: parent; width: parent.width - 8; height: 1; color: Theme.separator } }
                }
            }
        }
    }
}

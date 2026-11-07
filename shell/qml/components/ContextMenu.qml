// SPDX-License-Identifier: GPL-3.0-or-later
// Menu flyout: model is a list of {text, icon | iconSource, action} (action: a JS function),
// "-" for a separator and {header: "text"} for a section title. Metrics of the reference menus
// (menu.* in design/tokens.json): 1 px border, 2 px padding, 32 px rows, icon at 16, text at 44.
import QtQuick
import Fenestra.Shell

Flyout {
    id: menu
    property var items: []
    property int itemHeight: Metrics.menuItemHeight
    // Space above and below a separator line (0: the line touches the rows, taskbar menu).
    property int separatorMargin: 2
    property int minWidth: 0
    readonly property int rowWidth: Math.max(minWidth - 2 * padding, column.widest)
    padding: 1 + Metrics.menuPadding
    // Menus at the pointer reveal upwards with a quick fade (PopupMotion "menu"); the taskbar's
    // menus set "taskbar" (they rise from behind it like Quick settings).
    motion: "menu"
    background.color: Metrics.themed("menu.fill")
    background.border.color: Metrics.themed("menu.border")
    Column {
        id: column
        spacing: 0
        property int widest: {
            let w = 0
            for (let i = 0; i < children.length; ++i) w = Math.max(w, children[i].implicitWidth || 0)
            return w
        }
        Repeater {
            model: menu.items
            delegate: Loader {
                required property var modelData
                width: menu.rowWidth
                sourceComponent: modelData === "-" ? separator : modelData.header !== undefined ? header : entry
                Component {
                    id: entry
                    MenuRow {
                        inset: menu.padding
                        height: menu.itemHeight
                        text: modelData.text
                        iconName: modelData.icon || ""
                        iconSource: modelData.iconSource || ""
                        iconSize: modelData.iconSize || 16
                        onTriggered: { menu.close(); modelData.action() }
                    }
                }
                Component {
                    id: header
                    Item {
                        implicitWidth: label.implicitWidth + Metrics.menuIconX + Metrics.menuPaddingRight - 2 * menu.padding
                        height: menu.itemHeight
                        Text {
                            id: label
                            x: Metrics.menuIconX - menu.padding; anchors.verticalCenter: parent.verticalCenter
                            text: modelData.header
                            color: Metrics.themed("menu.header")
                            font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption
                        }
                    }
                }
                Component {
                    id: separator
                    Item {
                        implicitWidth: 0
                        height: 1 + 2 * menu.separatorMargin
                        // Full width of the menu, inside its border.
                        Rectangle { x: 1 - menu.padding; y: menu.separatorMargin; width: parent.width + 2 * (menu.padding - 1); height: 1
                                    color: Metrics.themed("menu.separator") }
                    }
                }
            }
        }
    }
}

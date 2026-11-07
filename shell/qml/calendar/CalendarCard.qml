// SPDX-License-Identifier: GPL-3.0-or-later
// Calendar card (N01, dark-100-16-calendar*): 49 px long-date header with collapse, then the month
// (title with ▲ ▼, weekday letters, six weeks of 47 × 42 cells, today in a 41 px accent circle)
// and the 48 px Focus footer (− 30 mins + and the Focus button). Collapsed: header and footer only.
// Positions in px from the card's outer edge (calendar.* tokens).
import QtQuick
import Fenestra.Shell

Card {
    id: cal
    width: Metrics.notificationsWidth
    readonly property int headerH: Metrics.n("calendar.header.height", 49)
    readonly property int bodyH: Metrics.n("calendar.body.height", 354)
    readonly property int footerH: Metrics.n("calendar.footer.height", 48)
    height: 1 + headerH + 1 + (collapsed ? 0 : bodyH + 1) + footerH + 1
    property bool collapsed: false
    property date shown: new Date()
    property int focusMinutes: 30
    readonly property date today: new Date()
    readonly property int cellW: Metrics.n("calendar.cell.width", 47)
    readonly property int cellH: Metrics.n("calendar.cell.height", 42)
    readonly property int button: Metrics.n("calendar.button", 24)
    function weekday(i) {
        const d = (Qt.locale().firstDayOfWeek + i) % 7
        return Strings.es ? Qt.locale().dayName(d, Locale.NarrowFormat).toUpperCase()
                          : Qt.locale().dayName(d, Locale.ShortFormat).slice(0, 2)
    }

    component ControlButton: Rectangle {
        id: cb
        property string glyph
        property string fluent          // Segoe Fluent Icons code point (when the font is there)
        property int fluentSize: 12
        signal clicked()
        height: cal.button; radius: Metrics.controlRadius
        color: m.pressed ? Theme.pressed : m.containsMouse ? Qt.tint(Metrics.pcol("panel.control"), Theme.hover) : Metrics.pcol("panel.control")
        border.color: Metrics.pcol("panel.control.border")
        SymbolicIcon { visible: cb.glyph !== "" && !(FluentFont.available && cb.fluent !== ""); anchors.centerIn: parent; name: cb.glyph; size: 12 }
        FluentGlyph { visible: FluentFont.available && cb.fluent !== ""; anchors.centerIn: parent; glyph: cb.fluent; size: cb.fluentSize }
        MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; onClicked: cb.clicked() }
    }

    // ---- Header ----
    Rectangle {
        x: 1; y: 1; width: parent.width - 2; height: cal.headerH
        topLeftRadius: Metrics.flyoutRadius - 1; topRightRadius: Metrics.flyoutRadius - 1
        color: cal.collapsed ? Metrics.pcol("panel.fill") : Metrics.pcol("panel.fill.alt")
        Text { x: 16; y: 15
               text: cal.today.toLocaleDateString(Qt.locale(), Strings.es ? "dddd, d 'de' MMMM" : "dddd, MMMM d")
               color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody }
        ControlButton {
            x: 294; y: 13; width: cal.button
            glyph: cal.collapsed ? "go-up-symbolic" : "go-down-symbolic"
            fluent: cal.collapsed ? "\ue70e" : "\ue70d"
            onClicked: cal.collapsed = !cal.collapsed
        }
    }
    Rectangle { x: 1; y: 1 + cal.headerH; width: parent.width - 2; height: 1; color: Metrics.pcol("panel.divider") }
    // ---- Month ----
    Item {
        id: month
        visible: !cal.collapsed
        y: Metrics.n("calendar.month.y", 51); width: parent.width; height: cal.bodyH
        Text { x: 17; y: 17
               text: cal.shown.toLocaleDateString(Qt.locale(), Strings.es ? "MMMM 'de' yyyy" : "MMMM yyyy")
               color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold }
        Repeater {
            model: [["▲", -1], ["▼", 1]]
            delegate: Rectangle {
                required property var modelData
                required property int index
                x: 255 + 40 * index; y: 12; width: 32; height: 32; radius: Metrics.controlRadius
                color: pm.pressed ? Theme.pressed : pm.containsMouse ? Theme.hover : "transparent"
                Text { anchors.centerIn: parent; text: modelData[0]; color: Theme.dark ? "#9b9b9b" : "#868686"; font.pixelSize: 12 }
                MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true
                    onClicked: cal.shown = new Date(cal.shown.getFullYear(), cal.shown.getMonth() + modelData[1], 1) }
            }
        }
        // Weekday headings: L M X J V S D (es), Mo Tu … (en).
        Row {
            x: Metrics.n("calendar.grid.x", 3); y: 57
            Repeater {
                model: 7
                delegate: Text {
                    required property int index
                    width: cal.cellW; height: cal.cellH; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    text: cal.weekday(index)
                    color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption; font.weight: Font.DemiBold
                }
            }
        }
        // Six weeks; the rows start 2 px below the heading row (today's circle at 194, dark-100-16-calendar).
        Grid {
            x: Metrics.n("calendar.grid.x", 3); y: 57 + cal.cellH + 2; columns: 7
            Repeater {
                model: 42
                delegate: Item {
                    required property int index
                    readonly property date first: new Date(cal.shown.getFullYear(), cal.shown.getMonth(), 1)
                    readonly property int offset: (first.getDay() - Qt.locale().firstDayOfWeek + 7) % 7
                    readonly property date day: new Date(first.getFullYear(), first.getMonth(), 1 - offset + index)
                    readonly property bool isToday: day.toDateString() === cal.today.toDateString()
                    readonly property bool other: day.getMonth() !== cal.shown.getMonth()
                    width: cal.cellW; height: cal.cellH
                    Rectangle { anchors.centerIn: parent; width: Metrics.calendarDay; height: width; radius: width / 2
                                color: parent.isToday ? (dm.containsMouse ? Theme.accentHover : Theme.accentFill) : dm.containsMouse ? Theme.hover : "transparent" }
                    Text { anchors.centerIn: parent; anchors.verticalCenterOffset: -1; text: parent.day.getDate(); font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody
                           font.features: { "tnum": 1 }
                           color: parent.isToday ? Theme.accentOn : parent.other ? Metrics.pcol("calendar.other") : Theme.text }
                    MouseArea { id: dm; anchors.fill: parent; hoverEnabled: true }
                }
            }
        }
    }
    Rectangle { visible: !cal.collapsed; x: 1; y: month.y + cal.bodyH; width: parent.width - 2; height: 1; color: Metrics.pcol("panel.divider") }
    // ---- Focus footer ----
    Item {
        id: focus
        x: 1; y: parent.height - 1 - cal.footerH; width: parent.width - 2; height: cal.footerH
        Row {
            x: 16; y: 12; spacing: 0
            visible: Notifications.focusRemaining === 0
            ControlButton { width: cal.button; glyph: "list-remove-symbolic"; fluent: "\ue738"; fluentSize: 16
                            onClicked: cal.focusMinutes = Math.max(5, Math.min(240, cal.focusMinutes + (cal.focusMinutes > 60 ? -15 : -5))) }
            Item {
                width: 81; height: cal.button
                Row { anchors.centerIn: parent; spacing: 4
                    Text { text: cal.focusMinutes; color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold
                           anchors.baseline: parent.children[1].baseline }
                    Text { text: Strings.tr("mins"); color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody } }
            }
            ControlButton { width: cal.button; glyph: "list-add-symbolic"; fluent: "\ue710"; fluentSize: 16
                            onClicked: cal.focusMinutes = Math.max(5, Math.min(240, cal.focusMinutes + (cal.focusMinutes >= 60 ? 15 : 5))) }
        }
        Text {
            x: 16; anchors.verticalCenter: parent.verticalCenter
            visible: Notifications.focusRemaining > 0
            text: Math.floor(Notifications.focusRemaining / 60) + ":" + String(Notifications.focusRemaining % 60).padStart(2, "0")
            color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontBody; font.weight: Font.DemiBold
        }
        ControlButton {
            x: parent.width - 16 - width; y: 12
            // dark-100-15-notifications: 113 × 24, 10 × 12 play glyph at +10, label at +25.
            width: Math.max(113, focusRow.implicitWidth + 20)
            Row {
                id: focusRow
                anchors.centerIn: parent; anchors.horizontalCenterOffset: -1; spacing: 1
                // Filled play glyph like the reference (status/media-play.svg).
                SymbolicIcon { anchors.verticalCenter: parent.verticalCenter; size: 14; monochrome: true; transform: Translate { x: -2; y: -1 }
                               name: Notifications.focusRemaining > 0 ? "media-playback-stop-symbolic" : ""
                               src: Notifications.focusRemaining > 0 ? "" : Metrics.assets + "status/media-play.svg" }
                Text { text: Strings.tr(Notifications.focusRemaining > 0 ? "End session" : "Focus")
                       color: Theme.text; font.family: Metrics.fontFamily; font.pixelSize: Metrics.fontCaption }
            }
            onClicked: Notifications.focusRemaining > 0 ? Notifications.endFocus() : Notifications.startFocus(cal.focusMinutes)
        }
    }
}

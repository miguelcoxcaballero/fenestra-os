// SPDX-License-Identifier: GPL-3.0-or-later
// A floating card of a multi-card flyout (quick settings + media, notifications + calendar).
import QtQuick
import Fenestra.Shell

Rectangle {
    radius: Metrics.flyoutRadius
    color: Theme.dark ? Qt.rgba(28 / 255, 28 / 255, 28 / 255, 0.96) : Qt.rgba(243 / 255, 243 / 255, 243 / 255, 0.94)
    border.color: Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
    border.width: 1
}

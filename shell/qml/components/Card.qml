// SPDX-License-Identifier: GPL-3.0-or-later
// A floating card of a multi-card flyout (quick settings + media, notifications + calendar):
// flat fill and 1 px outline as measured on the reference (panel.* in design/tokens.json).
import QtQuick
import Fenestra.Shell

Rectangle {
    radius: Metrics.flyoutRadius
    color: Metrics.col("panel.fill")
    border.color: Metrics.col("panel.border")
    border.width: 1
}

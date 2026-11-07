// SPDX-License-Identifier: GPL-3.0-or-later
// A floating card of a multi-card flyout (Quick settings + media, notifications + calendar): the
// popups' Acrylic material (translucent fill over KWin's blur, light border, shadow). The flyout
// lists each card's `material` in its blurItems. clipContent clips the card's content (subpage
// motion) without cutting its shadow.
import QtQuick
import Fenestra.Shell

Item {
    id: card
    property alias recipe: material.recipe
    property alias material: material
    property bool clipContent: false
    default property alias content: inner.data
    Acrylic { id: material; anchors.fill: parent; recipe: "panel" }
    Item { id: inner; anchors.fill: parent; clip: card.clipContent }
}

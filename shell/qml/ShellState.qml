// SPDX-License-Identifier: GPL-3.0-or-later
// Which shell flyout is open (one at a time). Start and Search are implemented in H3.
pragma Singleton
import QtQuick

QtObject {
    signal startRequested(var screen, real anchorX)
    signal searchRequested(var screen, real anchorX)
    function toggleStart(screen, x) { startRequested(screen, x) }
    function toggleSearch(screen, x) { searchRequested(screen, x) }
}

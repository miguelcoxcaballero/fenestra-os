// SPDX-License-Identifier: GPL-3.0-or-later
// Which shell flyout is open (one at a time). Start and Search are implemented in H3.
pragma Singleton
import QtQuick

QtObject {
    signal startRequested(var screen, real anchorX)
    signal searchRequested(var screen, real anchorX)
    signal quickSettingsRequested(var screen, real anchorX)
    signal calendarRequested(var screen, real anchorX)
    function toggleQuickSettings(screen, x) { quickSettingsRequested(screen, x) }
    signal inputSwitcherRequested(var screen)
    function showInputSwitcher(screen) { inputSwitcherRequested(screen) }
    function toggleCalendar(screen, x) { calendarRequested(screen, x) }
    function toggleStart(screen, x) { startRequested(screen, x) }
    function toggleSearch(screen, x) { searchRequested(screen, x) }
}

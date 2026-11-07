// Bench stand-in for plasma-nm (tests/lockscreen): the enum values plasma-nm exports.
import QtQuick
QtObject {
    enum ConnectionStatus { UnknownState = 0, Activating = 1, Activated = 2, Deactivating = 3, Deactivated = 4 }
    enum ConnectionType { Wired = 13, Wireless = 14 }
}

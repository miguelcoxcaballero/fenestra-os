// SPDX-License-Identifier: GPL-3.0-or-later
// UI strings: English source text, Spanish by system locale (M04). Same strings as the GNOME layer.
pragma Singleton
import QtQuick

QtObject {
    readonly property bool es: Qt.locale().name.startsWith("es")
    readonly property var table: ({
        "Start": "Inicio",
        "Search": "Buscar",
        "Task Manager": "Administrador de tareas",
        "Taskbar settings": "Configuración de la barra de tareas",
        "Pin to taskbar": "Anclar a la barra de tareas",
        "Unpin from taskbar": "Desanclar de la barra de tareas",
        "Close window": "Cerrar ventana",
        "Close all windows": "Cerrar todas las ventanas",
        "Show desktop": "Mostrar escritorio",
    })
    function tr(s) { return es && table[s] !== undefined ? table[s] : s }
}

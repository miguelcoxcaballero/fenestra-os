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
        "Show hidden icons": "Mostrar iconos ocultos",
        "Search for apps, settings, and documents": "Busca aplicaciones, configuración y documentos",
        "Pinned": "Anclado", "All": "Todo", "Show less": "Mostrar menos", "Show all": "Mostrar todo",
        "Recommended": "Recomendado", "Your recent files will appear here.": "Tus archivos recientes aparecerán aquí.",
        "Back": "Atrás", "View": "Vista", "Category": "Categoría", "Grid": "Cuadrícula", "List": "Lista",
        "Productivity": "Productividad", "Social": "Social", "Creativity": "Creatividad",
        "Utilities & Tools": "Utilidades y herramientas", "Games": "Juegos", "Other": "Otras",
        "Power": "Iniciar/Apagar", "Lock": "Bloquear", "Sleep": "Suspender", "Shut down": "Apagar", "Restart": "Reiniciar",
        "Sign out": "Cerrar sesión", "Switch user": "Cambiar de usuario", "Change account settings": "Cambiar la configuración de la cuenta",
        "Pin to Start": "Anclar a Inicio", "Unpin from Start": "Desanclar de Inicio",
        "Web": "Web", "Apps": "Aplicaciones", "Documents": "Documentos", "Settings": "Configuración", "Folders": "Carpetas", "Photos": "Fotos",
        "Recent searches": "Búsquedas recientes", "Your recent searches will appear here.": "Tus búsquedas recientes aparecerán aquí.",
        "Top apps": "Aplicaciones principales", "Searching…": "Buscando…", "No results": "No hay resultados",
        "Location": "Ubicación", "Last modified": "Última modificación", "App": "Aplicación", "System settings": "Configuración del sistema",
        "Document": "Documento", "File folder": "Carpeta de archivos", "Photo": "Foto",
        "Open": "Abrir", "Open results in browser": "Abrir resultados en el navegador", "Open file location": "Abrir ubicación del archivo",
        "Copy full path": "Copiar ruta de acceso completa",
    })
    function tr(s) { return es && table[s] !== undefined ? table[s] : s }
}

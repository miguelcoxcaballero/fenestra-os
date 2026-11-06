# Capturas de referencia de Windows 11

Capturas sacadas de una VM QEMU/KVM con Windows 11 Enterprise Evaluation (build 26100), a 1920×1080, para medir
el shell y los diálogos que copia Fenestra. Están en esta rama (`visual/screenshots`) para que se puedan medir en
otra máquina. No se fusionan en `main`: el código y los números van en `visual/reference`.

- Cuenta local «Usuario Demo», archivos de demo («Informe trimestral.txt», «Notas de la reunión.md»,
  «playa-verano.jpg» sintética y «demo-tono.wav») y notificaciones de demo. No contienen datos personales.
- Énfasis azul por defecto (#0078D4), barra centrada, «Cuadro de búsqueda», anclados: Explorador, Bloc de notas y Paint.
- Idioma de la interfaz: es-ES. Excepciones: algunas apps de la Store (Bloc de notas, Recortes, Reloj) y el diálogo
  «Abrir» salen en inglés. Lo indica el `.json` de cada captura o se ve en ella.
- La VM no tiene GPU: el acrílico, las sombras y las animaciones no son fiables al píxel.
- La marca de agua «Windows 11 Enterprise Evaluation» de abajo a la derecha está en todas las capturas del escritorio.

## Estructura

| Carpeta | Contenido |
|---|---|
| `solid/` | Shell sobre un fondo sólido `#1f1f1f`. Nombres `<tema>-<escala>-<NN>-<panel>.png` (`dark-100-06-start.png`); NN = número de panel de `tests/visual/panels.json` |
| `bloom/` | Mismos paneles (01, 06, 07, 10, 11, 12 y 15) sobre `assets/generated/wallpapers/fenestra-bloom-dark.jpg`, para el acrílico |
| `dialogs/` | «Guardar como» (30), «Abrir» (31), Imprimir (32), «Más opciones» (33) y Recortes (34), en `dark-100-` y `light-100-` |
| `apps/` | Explorador (40), Bloc de notas (41), Paint (42), Administrador de tareas (43), Configuración (44) y Microsoft Store (45), en `dark-100-` y `light-100-`, con los mismos estados que `dialogs/`. Nombres `<tema>-100-<NN>-<app>-<vista>-<estado>[-<control>]` (`dark-100-40-explorer-folder-menu-ver`) |
| `motion/` | Fotogramas (QMP screendump, entre 17 y 38 ms cada uno, `times.json` con su tiempo real) de la apertura de Inicio, Configuración rápida, Notificaciones y Búsqueda; `analysis.json` = resultado de `tests/visual/motion.py` |
| `fenestra/` | Las mismas pantallas de Fenestra Shell desde el banco KWin (`tests/visual/fenestra_bench.py`), recompuestas sobre `#1f1f1f`; `.mask.png` = forma exacta del panel (alfa de la superficie) |

Cada `.png` va acompañado de un `.json` con:
- `note`: qué se hizo;
- `pointer`: dónde estaba el ratón;
- `seed`: un punto dentro del panel (si se dio a mano);
- `wallpaper`/`bg`.

## Estados en `dialogs/`

`<prefijo>-normal`, `-hover-<control>` (ratón encima 0,9 s), `-pressed-<control>` (botón pulsado sin soltar),
`-focus-NN` (NN pulsaciones de Tab), `-menu-<control>` (menú desplegado), `-click-<algo>` (estado tras un clic).

## Qué no salió o no existe en esta VM

- OSD de volumen y de brillo: el teclado USB emulado no envía teclas multimedia, y la VM no tiene brillo.
- Subpágina Wi-Fi: la VM no tiene adaptador Wi-Fi.
- Desbordamiento «^» de la bandeja: no había iconos ocultos (el clic abre el flyout de OneDrive).
- Menú contextual del escritorio al 100 % (solo salió al 150 %). Snap Layouts al 150 %.
- Inicio › Todos solo tiene la vista de lista en la build 26100 (no hay 3 vistas).
- Imprimir: con «Microsoft Print to PDF» y el Bloc de notas nuevo solo hay Impresora, Orientación e «Imprimir en
  archivo». No hay copias, páginas, color ni vista previa («Esta aplicación no admite la vista previa de impresión»).
  «Más opciones» abre las Preferencias de impresión clásicas (Win32, siempre en claro).
- El diálogo «Abrir» no tiene botón dividido «Abrir ▾» en esta versión del Bloc de notas.
- En `dark-100-30-save-*` a partir de `pressed-header-nombre`, la columna «Nombre» queda al final (efecto de la
  captura de pulsado). Se restauró antes de `dark-100-31-open-*`.

## Notas de `apps/`

Las mismas capturas en los dos temas, con la ventana en la misma posición. Si una ventana se abría en otro sitio, se movía al de la otra pasada.
Las coordenadas de `pointer` valen para las dos pasadas.

- **Antes de capturar se quitó el widget del tiempo de la barra de tareas** (Configuración › Barra de tareas ›
  Widgets), porque mostraba el tiempo de la zona del anfitrión. Las capturas anteriores de `solid/` y `bloom/` lo tienen.
- **`-pressed-`:**
  - El ratón se suelta en el mismo sitio, así que el control se activa después. La captura sale antes, con el botón pulsado.
  - Excepción: las `dark-100-40-explorer-home-pressed-*`, donde se soltó arrastrando fuera de la ventana.
  - En los menús del Bloc de notas y de Paint, y en los interruptores, el menú o el cambio ya se ve al pulsar.
- **Bloc de notas (41):**
  - El texto es de demostración, pegado y sin guardar.
  - Los atajos siguen el teclado español aunque la interfaz esté en inglés: Ctrl+B busca, Ctrl+U abre una pestaña,
    Ctrl+E selecciona todo y Ctrl+F es «Search with Bing».
- **Paint (42):** «Shapes › Outline» y «Shapes › Fill» están desactivados si no hay una forma dibujada, así que sus menús no se capturaron.
- **Administrador de tareas (43):**
  - Se capturó con el tamaño con el que abre: la ventana tiene más privilegios y no deja moverla desde el agente.
  - Rendimiento › CPU muestra el modelo de CPU del portátil anfitrión, porque la VM usa `-cpu host`.
- **Store (45):**
  - El contenido de la tienda cambia cada vez, así que la portada y las fichas no coinciden entre `dark-` y `light-`.
- **Configuración (44):**
  - Los nombres de archivo usan inglés (`system`, `display`…).
  - Las páginas son Inicio, Sistema, Pantalla, Sonido, Notificaciones, Bluetooth y dispositivos, Red e Internet,
    Personalización (Fondo, Colores, Temas, Inicio, Barra de tareas), Aplicaciones, Cuentas, Hora e idioma,
    Accesibilidad, Privacidad y seguridad y Windows Update.
  - También están la búsqueda con sugerencias y dos desplegables abiertos («Modo de color» y el tipo de fondo).

## Qué no salió en `apps/`

- **Explorador:** el menú contextual tarda unos 2 s en aparecer en la VM. Las capturas esperan 3 s.
- **Store › Biblioteca:** no se capturó. La tienda no tiene sesión iniciada («Iniciar sesión»), pero la Biblioteca
  mostraba apps adquiridas que no son de la cuenta de demo.
- **Store, descarga en curso:**
  - Solo existe en oscuro: `dark-100-45-store-download-*`, la actualización del Centro de opiniones, que ya
    viene instalado.
  - En claro no quedaba nada por actualizar: `light-100-45-store-downloads-click-check-updates` se queda buscando.
    No se instaló ninguna app de terceros.
- **Asistente de primer inicio (OOBE, 46):** no se capturó. Solo sale al instalar Windows o al restablecer el
  equipo, y eso borraría la VM de referencia.


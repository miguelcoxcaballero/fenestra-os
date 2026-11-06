Repo github.com/miguelcoxcaballero/fenestra-os. Trabaja en la rama visual/reference (la crea Claude
desde feature/fenestra-shell-kwin). Las capturas de Windows 11 están en la rama visual/screenshots, carpeta
reference-shots/ (lee primero reference-shots/README.md: estructura, nombres, sidecars .json y lo que no se pudo
capturar). Otro agente programa el shell en paralelo: NO toques shell/, session/ ni apps/.

REGLAS
- No inventes medidas: cada valor lleva "source" (captura) y "at" ([x, y] del píxel). Lo que la VM no reproduce
  bien (acrílico, sombras, animaciones, peso de fuente estimado) va con "reliable": false.
- No copies ni fusiones capturas, iconos ni fuentes en visual/reference. Para medir, haz checkout de
  visual/screenshots en otra carpeta (git worktree add ../shots visual/screenshots).
- Commits pequeños, git pull --rebase antes de push, push a visual/reference. No abras PR ni fusiones.

TAREA 1. SHELL (paneles 01–29)
1. Ejecuta: python3 tests/visual/measure.py ../shots/reference-shots/solid ../shots/reference-shots/bloom
   --motion ../shots/reference-shots/motion. Se genera design/reference/measurements.json; ahora hay uno preliminar.
2. Revisa panel a panel y corrige:
   - las semillas o las exclusiones de tests/visual/panels.json donde measure.py dé cajas absurdas;
   - las claves marcadas "no cuadra con las otras pasadas";
   - el tamaño de los toasts en oscuro, la Búsqueda en dark-150 y los hover de los botones de ventana.

   Que cada clave de design/tokens.json que se vea en las capturas tenga un valor fiable a escala 1 (git pull antes:
   tokens.json cambia). Incluye: taskbar.icon, los indicadores, start.pinned.*, start.footer.height, quick.tile.*,
   search.box.*, menu.item.height, calendar.day, window.title.height, switcher.thumbnail.height y font.* (tamaño
   de texto por la altura de mayúsculas).
3. Ejecuta: python3 tests/visual/compare.py ../shots/reference-shots/solid ../shots/reference-shots/fenestra
   --md /tmp/t.md -o /tmp/compare. Las imágenes se quedan fuera del repo.
4. Escribe docs/fenestra-shell/VISUAL.md:
   - una tabla por panel con la diferencia (Δx, Δy, Δw, Δh, % de píxeles y % de color);
   - lo no fiable y lo no medido, con el motivo (sale en el README de las capturas);
   - sin imágenes.

TAREA 2. DIÁLOGOS (reference-shots/dialogs/, prefijos dark-100- y light-100-)
Mide «Guardar como» (30), «Abrir» (31), Imprimir (32), «Más opciones» (33) y Recortes (34) con precisión de píxel.
Añade a design/reference/measurements.json las secciones file_dialog_save, file_dialog_open, file_dialog_menus,
print_dialog, print_dialog_more, print_dialog_menus, snip_overlay, snip_toolbar y snip_after_capture. Cada una
tendrá light y dark y, cuando haya texto, es y en: «Guardar como» está en español; «Abrir», Recortes y las
Preferencias de impresión clásicas, en inglés.

Cada elemento lleva:
- x, y, ancho y alto, relativos a la ventana (o a la pantalla en Recortes);
- padding y radio;
- colores por estado (normal, hover, pulsado, foco, desactivado) en #rrggbb / #rrggbbaa: hover = -hover-*,
  pulsado = -pressed-*, foco = -focus-NN;
- tamaño de fuente en px (altura de mayúsculas y x), peso estimado (reliable false) y altura de línea;
- el texto exacto.

Qué medir en cada diálogo:
- **«Guardar como» y «Abrir»:**
  - la barra de título;
  - la fila de navegación (atrás, adelante, recientes, arriba, dirección con desplegable, actualizar, búsqueda);
  - la barra de comandos (Organizar ▾, Nueva carpeta, vista ▾, panel de vista previa, ayuda);
  - el panel de navegación (filas, sangría, iconos, selección y hover);
  - la lista en detalles (cabecera, filas, columnas y anchos, colores);
  - la zona inferior (etiquetas, campos, combos, Encoding, botones, márgenes y fondo);
  - los separadores;
  - los menús Organizar, Tipo, vista, Encoding, dirección, recientes y nombre (ancho, alto de fila, padding,
    radio, sombra, entradas en orden con su texto exacto).
- **Imprimir:** ventana, título, Impresora, «Agregar una impresora», Orientación, «Print to file» con su
  interruptor (-click-toggle-on/off), «Más opciones de configuración», casilla, Imprimir/Cancelar, flechas y
  ajuste de vista previa, menús de impresora y de orientación. «Más opciones» = Printing Preferences
  clásicas + Advanced.
- **Recortes:**
  - el oscurecido (color y opacidad: compáralo con el escritorio sin superposición, por ejemplo
    light-100-34-snip-printscreen frente a la misma zona en dialogs/*-normal);
  - la barra (posición, centrado, tamaño, radio, fondo, borde, sombra);
  - cada botón y su separación, el seleccionado, los separadores y el botón de cerrar;
  - los tooltips (-hover-*) con su texto exacto;
  - el selector Captura/Vídeo (-video-mode);
  - el menú de modo;
  - el rectángulo en curso (-rect-dragging: borde, color y zona seleccionada);
  - el modo ventana (-window-mode: cómo se resalta);
  - la notificación tras capturar (-after-capture: tamaño, posición y textos).

Escribe design/reference/dialogs.md con:
- el árbol de elementos de cada pantalla;
- qué cambia entre claro y oscuro;
- qué se desactiva y cuándo;
- los atajos de teclado: en el Bloc de notas en español, Abrir = Ctrl+A, Guardar como = Ctrl+Mayús+S,
  Imprimir = Ctrl+P; Recortes = Win+Mayús+S e Impr Pant.

Al terminar, una lista de lo que no se pudo medir y por qué.

TAREA 3. ICONOS
design/reference/icons.json lista los iconos vistos en las capturas con su origen en Windows (id de imageres o
shell32, glifo de Segoe Fluent Icons o logo del paquete). Haz lo siguiente:
- revisa las capturas por si falta algún icono;
- donde verificado=false, comprueba el id o el código con documentación pública (Microsoft Learn: «Segoe Fluent
  Icons font») y corrígelo;
- en docs/ICON-PACK-FORMAT.md propón (sin tocar apps/) cómo el extractor exportaría los glifos (por ejemplo
  glyphs/<nombre>.svg renderizados desde SegoeIcons.ttf) y los logos de los paquetes.

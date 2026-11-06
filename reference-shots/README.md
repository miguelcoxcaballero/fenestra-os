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

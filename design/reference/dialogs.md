# Reference dialogs: Save As, Open, Print, More options, Snipping Tool

Measured on Windows 11 Enterprise Evaluation (build 26100, es-ES, 1920×1080 at 100 %) in a QEMU/KVM VM
without GPU. Screenshots: branch `visual/screenshots`, `reference-shots/dialogs/` (`dark-100-*`, `light-100-*`).
They never enter this branch: only the numbers do.

- Script: `tests/visual/measure_dialogs.py [SHOTS_DIR]` (helpers in `tests/visual/dlglib.py`). It rewrites only
  its own top-level keys of `design/reference/measurements.json`: `file_dialog_save`, `file_dialog_open`,
  `file_dialog_menus`, `print_dialog`, `print_dialog_menus`, `print_dialog_more`, `snip_overlay`,
  `snip_toolbar`, `snip_after_capture`.
- Every value is `{"value", "source": <screenshot>, "at": [x, y] screen pixel}`; `"reliable": false` marks what
  the VM does not render faithfully (acrylic, shadows, animation) and estimates (font weight, colours of
  ClearType-fringed coloured text).
- Dialog coordinates are relative to the window's **outer** top-left (the 1 px frame included); Snipping Tool
  coordinates are screen pixels.
- Each section has `light` and `dark`, a `text` block per theme (exact string, ink box, colour, ascender,
  font size, estimated weight, baseline) and, where it maps onto Fenestra, a `fenestra_map` (Fenestra knob →
  path in the section + value), for `nautilus-file-chooser.ui` / the «Explorer open / save dialog» block of
  `gtk.css`, `desktop/portal/fenestra_portal/metrics.py` and `snip.*` in `design/tokens.json`
  (branch `feature/fenestra-shell-kwin`).
- Fonts: size = ascender height (l, d, b) / 0.727 (Segoe UI). The Win32 dialogs read 9 px ascender = **12 px**
  (9 pt); the WinUI print dialog, Snipping Tool and its toast read 10 px = **14 px**. On dark backgrounds the
  ascender often reads one pixel taller (light text bleeds): take the light value. Weight is always an
  estimate (`reliable: false`).

## Shortcuts

| Action | Shortcut (Windows, es-ES Notepad) |
|---|---|
| Abrir (Open) | Ctrl+A (the Spanish Notepad maps Abrir to Ctrl+A) |
| Guardar como (Save As) | Ctrl+Mayús+S |
| Imprimir (Print) | Ctrl+P |
| Recortes (Snipping overlay) | Win+Mayús+S, or Impr Pant (same overlay; measured identical apart from the teaching tip) |
| In the dialogs | Atrás Alt+Flecha izquierda, Adelante Alt+Flecha derecha, Subir Alt+Flecha arriba, Actualizar F5 (from the tooltips) |
| In Snipping Tool | Quick markup Ctrl+E, Text extractor ⊞+Shift+T, Close Esc (from the tooltips) |

## «Guardar como» (30) and «Abrir» (31)

Classic common item dialog (Win32), same geometry in both themes and in Save/Open: outer **946 × 533**,
square corners in the VM (DWM cannot round without GPU; real Windows 11 rounds 8 px). «Guardar como» has an
English title (`Save as`, Notepad is an English Store app) and Spanish labels; «Abrir» is English throughout.

Element tree (y/height relative to the window, light pass; dark identical unless noted):

```
window 946×533, 1 px frame (#ababab-ish light / #3e3e3e dark), soft shadow (unreliable)
├─ title bar        y 0, 30 px + 1 px frame        light #f3f3f3 · dark #202020
│  ├─ icon + «Save as» / «Open»   12 px, ink x 31
│  └─ close button  32 × 30 (x 914)   hover #c42b1c, pressed #c84031 light / #b22a1b dark
├─ navigation row   y 31, 55 px                    light #ffffff · dark #191919
│  ├─ Back, Forward (disabled, no history), Recent locations chevron, Up (hover box 33 × 32, #cce8ff / #434343)
│  ├─ address box   x 138, 581 × 34, 1 px #d9d9d9 / #535353; «› Documentos»
│  │  └─ history chevron and Refresh: hover boxes 34 × 33 (#e5f3ff / #434343)
│  └─ search box    x 731, 202 × 34, placeholder «Buscar en Documentos» / «Search Documentos» (#6d6d6d)
├─ command bar      y 86, 30 px + 1 px line #e8e9ea   light #f5f6f7 · dark #202020
│  ├─ «Organizar ▾» / «Organize ▾»  hover 95 × 25 #dcebf4 (+1 px #0078d4), pressed #c3e1f0; dark #4d4d4d / #666666
│  ├─ «Nueva carpeta» / «New folder»
│  └─ right: view (27 × 26) + view chevron (19 × 25), [Open only: preview pane toggle], help (?)
├─ navigation pane  x 1, 140 wide + 16 px scrollbar (#f0f0f0 / #171717) = Fenestra's 157 sidebar incl. frame
│  ├─ rows 32 px pitch: Inicio/Home, Galería/Gallery, OneDrive (selected) | divider 1 px #d6d6d6 / #383838 |
│  │  Escritorio, Descargas, Documentos, Imágenes (+ Música, Vídeos in Open: the pane is taller) — pinned rows
│  │  carry a pin glyph on the right
│  ├─ selected row 137 × 32: #d9d9d9 + 1 px #949494 (unfocused) → #cce8ff + 1 px #000000 when focused;
│  │  dark #333333 → #505050 with 1 px #c3c3c3
│  └─ hover row #e5f3ff / #4d4d4d
├─ details list     x 159 (1 px splitter #f7f7f7)  light #ffffff · dark #191919
│  ├─ header row 27 px: Nombre | Fecha de modificación | Tipo | Tamaño (Name | Date modified | Type | Size),
│  │  dividers #e5e5e5; header text light #4c6a93-ish (ClearType, unreliable) / dark #dedede;
│  │  hover #d9ebf9 / #434343, pressed (dark) #838383
│  └─ row 24 px: «Informe trimestral», «07/11/2026 2:00», «Text Document», «1 KB»; name #000000 / #ffffff,
│     other columns #6d6d6d / #dedede; hover #e5f3ff / #4d4d4d; selected #cce8ff (+ 1 px black focus rect)
├─ bottom (Save)    fields area y 375, 100 px #f9f9f9; buttons strip y 475, 58 px #f0f0f0; dark both #383838
│  ├─ «Nombre:» + field x 126, 814 × 23 (focused: 1 px #0078d4 light / #ffffff dark, text selected)
│  ├─ «Tipo:» + combo 814 × 23 #fdfdfd, 1 px #d2d2d2 (bottom #bcbcbc); dark #333333 / #9b9b9b
│  ├─ «⌃ Ocultar carpetas» (hover 110 × 20 #e5f3ff / #434343)
│  └─ «Encoding:» combo 150 × 23 · «Guardar» 86 × 24 (default: 1 px #0078d4) · «Cancelar» 86 × 24, gap 14,
│     radius 3; hover #e0eef9 + #0078d4, pressed #cce4f7 + #005499; dark #333333/#9b9b9b, hover #454545, pressed #666666
└─ bottom (Open)    one area y 451, 82 px #f0f0f0 / #383838
   ├─ «File name:» field x 190, 538 × 24 · type filter combo x 740, 188 × 23 («Text documents (*.txt)»)
   └─ «Encoding:» «Auto-Detect» · «Open» · «Cancel» (same sizes as Save)
```

Tooltips (hover 0.9 s): 20 px tall, 1 px border #e5e5e5 / #767676, background #f9f9f9 / #2b2b2b, 12 px text;
«Organiza el contenido de esta carpeta.» wraps to two lines (35 px). Texts: Atrás (Alt + Flecha izquierda),
Adelante (Alt + Flecha derecha), Ubicaciones recientes, Subir a "Escritorio" (Alt + Flecha arriba),
Ubicaciones anteriores, Actualizar "Documentos" (F5), Crea una nueva carpeta., Cambia la vista., Más opciones,
Muestra ayuda. — Open: Back (Alt + Left Arrow), Forward (Alt + Right Arrow), Recent locations,
Up to "Desktop" (Alt + Up Arrow), Previous Locations, Refresh "Documentos" (F5), Organize this folder's contents.,
Create a new folder., Change your view., More options, Show the preview pane., Get help.

Focus order (Tab from the initial state; `focus_order` lists what changed): Save — navigation pane, list row,
column header «Nombre», «Nombre» field, «Tipo», «Ocultar carpetas», «Encoding», «Guardar». Open — navigation
pane, list row, «Name» header, «File name», type filter, «Encoding», «Open», «Cancel». Focus visuals: 1 px
black rect (list/header/nav; #c3c3c3 in dark), dotted rect inside combos/buttons, the default button moves its
blue border to the focused button.

Light vs dark: the whole Win32 chrome is themed (title bar, rows, command bar, list, bottom area, buttons,
Organize menu, tooltips). **Not themed in dark**: the view slider menu (stays light #f9f9f9) and the
selection blue of combo lists (#0078d4/#0078d7 frame). In dark the bottom area is a single #383838 block (no
lighter fields area / darker strip).

Disabled: Back/Forward without history (no hover); Organize menu without a selection: Cortar/Copiar/Pegar/
Deshacer/Rehacer, Opciones, Eliminar, Cambiar nombre, Quitar propiedades, Cerrar (#9f9f9f light / #6d6d6d dark);
«Seleccionar todo» disabled in Save (only one file of the filtered type) but «Select all» enabled in Open;
«Diseño/Layout ›» and «Propiedades/Properties» always enabled.

### Menus (`file_dialog_menus`)

| Menu | Box (w × h) | Look | Rows | Entries (in order) |
|---|---|---|---|---|
| Organizar / Organize | 185 × 328 | #f9f9f9 / #2b2b2b, 1 px #e5e5e5 / #808080, square, no shadow in VM | 22 px pitch, hover row 22 px #f0f0f0 / #353535; separators 1 px #d7d7d7 / #3e3e3e | Cortar, Copiar, Pegar, Deshacer, Rehacer — Seleccionar todo — Diseño ›, Opciones — Eliminar, Cambiar nombre, Quitar propiedades, Propiedades — Cerrar · (en) Cut, Copy, Paste, Undo, Redo — Select all — Layout ›, Options — Delete, Rename, Remove properties, Properties — Close |
| View (slider) | 182 × 265 (opens upwards) | always light #f9f9f9, 1 px #646464, shadow ≈5 px | grouped tiles #f0f0f0, 29 px | Iconos muy grandes, Iconos grandes, Iconos medianos, Iconos pequeños, Lista, Detalles (thumb), Mosaicos, Contenido · Extra large icons, Large icons, Medium icons, Small icons, List, Details, Tiles, Content |
| Encoding list | 150 wide | combo list, 1 px #0078d7, white / #383838 | 15 px | Save: ANSI, UTF-16 LE, UTF-16 BE, UTF-8 (selected #0078d4), UTF-8 with BOM · Open: Auto-Detect (selected), ANSI, UTF-16 LE, UTF-16 BE, UTF-8, UTF-8 with BOM |
| Tipo / type filter | field width | same | 16–17 px | Text documents (*.txt) (selected), All files · Open adds Markdown file (*.md) |
| Nombre / File name history, address history | field width | empty lists (no history in the VM) | — | — |

«Ubicaciones recientes» (chevron) did not open a menu in the capture: it only put the address bar in edit mode.

## Print (32)

Modern print dialog of Win32 Notepad (Ctrl+P), outer **852 × 734**, same in both themes. With Microsoft Print
to PDF and this Notepad only Printer, Orientation and Print to file exist (no copies, pages, colour, margins,
preview: «Esta aplicación no admite la vista previa de impresión»). Mixed languages exactly as shown.

```
window 852×734 (frame 1 px), body light #f9f9f9 · dark #282828
├─ «Printing from Win32 application - Impresión»   14 px, ink x 26 (looks semibold; weight unreliable)
├─ close X (hover 47 × 34 #c42b1c) · preview header: ◀ ▶ (disabled), fit-page button (40 × 40 focus box)
├─ left column (x 25 … 292)
│  ├─ «Impresora» 14 px
│  ├─ printer combo 267 × 32 (radius 3 on the orientation combo, diagonal estimate), fill #fefefe / #414141, border #eeeeee (bottom #d4d4d4) / #484848;
│  │  3 px accent pill (#0067c0 / #4cc2ff) left of the value; initial keyboard focus ring:
│  │  2 px #1a1a1a / #ffffff + 2 px inner gap, 4 px outside the border box
│  ├─ «＋ Agregar una impresora» link #003e92 / #99ebff (hover bg #f0f0f0 / #353535, 167 × 22)
│  ├─ «Orientation» · combo 267 × 38 (icon + «Portrait»), #fdfdfd / #353535
│  ├─ «Print to file» · toggle 40 × 20 radius 10: off track #f3f3f3 / #242424 with 1 px #8a8a8a / #9b9b9b,
│  │  knob 12 px #5c5c5c / #cdcdcd at x 29; on: track #0067c0 / #4cc2ff, knob #ffffff / #000000 at x 49;
│  │  label «Desactivado» → «Activado»; hover track #eaeaea / #313131 (knob grows, covered by the pointer)
│  ├─ «Stores printing output to a file» #8a8a8a / #9d9d9d
│  └─ «Más opciones de configuración» link
├─ preview area x 316, 511 × 548, 1 px #d1d1d1 / #3c3c3c, radius 3 (estimate)
└─ footer y 652: 1 px separator #eaeaea / #373737, background #f3f3f3 / #202020 (82 px incl. frame)
   ├─ checkbox 20 × 20 radius 3 (estimate), checked #0067c0 / #4cc2ff (hover #1875c5 / #47b2e9),
   │  «Permitir que la aplicación cambie las preferencias de / impresión.» (two lines, 18 px apart)
   └─ «Imprimir» 193 × 32 · «Cancelar» 192 × 32, gap 8, radius 3 (estimate): #fbfbfb / #2d2d2d,
      hover #f6f6f6 / #323232, pressed #f5f5f5 / #272727, border #e5e5e5 + bottom #cccccc (light)
```

Menus (`print_dialog_menus`): both pop-ups open *over* their combo (selected entry aligned with it), 267 wide,
radius 7 (from the changed-pixel corner), flat #f9f9f9 / #2c2c2c (acrylic not rendered), border #eaeaea / #202020. Printer: «Microsoft Print to
PDF» (selected, row 33 px #f3f3f3 / #343434 + pill). Orientation: «Landscape», «Portrait» (selected), 50 px pitch
(icon rows, selected row 40 px).

Focus order: fit-page button, (invisible stop), «Agregar una impresora», Orientation, toggle,
«Más opciones de configuración», checkbox; ring colour #1a1a1a / #ffffff.

Disabled: ◀ ▶ page buttons (single page, no preview).

## More options (33): Printing Preferences + Advanced

Classic Win32 property sheets, **always light** even in dark mode (dark pass identical).

```
Printing Preferences 533×472 — title bar 30 px #f3f3f3, body #f0f0f0
├─ tab «Layout» · tab page #f9f9f9, 1 px #dcdcdc
├─ «Orientation:» · combo 200 × 25 (white, 1 px #8d8d8d), value «Portrait» highlighted #0078d4
├─ preview frame with page thumbnail
├─ «Advanced...» 86 × 24 · «Aceptar» 73 × 21 (default, 1 px #0078d4) · «Cancelar» 73 × 21
└─ orientation list: Landscape, Portrait (selected), 19 px rows, 1 px #0078d7
Advanced Options 461×478 «Microsoft Print To PDF Advanced Options» (parent title greys to #919191)
├─ tree (white, sunken 1 px #696969/#e3e3e3): «Microsoft Print To PDF Advanced Document Settings» ›
│  «Paper/Output» › «Paper Size:» [Letter ▾] · «Copy Count:» «1 Copy» (link-style underline)
└─ «OK» 86 × 24 (default) · «Cancel» 86 × 24
```
Buttons: hover #e0eef9 + 1 px #0078d4; text 12 px #000000.

## Snipping Tool (34)

English UI, screen coordinates. Win+Mayús+S and Impr Pant give the same overlay.

- **Dimming** (`snip_overlay.dim`): fitted pixel-by-pixel against the same screen undimmed (`-after-capture`):
  overlay = 0.395 × screen + 0.7 → black scrim at **opacity 0.60 (#00000099/9a)** in both themes
  (mean residual < 0.1 level).
- **Rectangle in progress**: the selection is shown undimmed with a **1 px white dashed outline (4 on / 3 off)**
  just outside it; no fill tint. **Window mode**: the window under the pointer is undimmed with a 1 px white
  outline just outside its frame.
- **Toolbar** (`snip_toolbar.bar`): fill 330 × 48 at (795, 13), centred (centre x 960), radius 7 (diagonal estimate), background
  #1f1f1f dark / #e6e6e6 light (acrylic flattened, unreliable), 1 px outline #3d3d3d visible only in dark;
  shadow not visible on the dimmed screen.
  - Snapshot / Video segmented control at x 803, 76 × 32 (two 38 × 32 segments): selected #292929 / #f6f6f6
    with 1 px #454545 / #bfbfbf, accent underline 16 × 4 #4cc2ff / #0067c0 under the icon; unselected segment
    flat (#1c1c1c / #e1e1e1 in video mode).
  - Mode button 56 × 32 (rectangle icon + chevron), Quick markup 32 × 32 (disabled in Video mode), separator,
    Color picker, Text extractor (both with a blue «new» dot), separator, Close. Separators x 987 and 1076,
    1 × 24 at y 25, #313131 / #d4d4d4. Buttons radius 3 (estimate); hover #2c2c2c / #dddddd.
  - Tooltips (32 px tall, #2c2c2c / #f9f9f9, 12 px): «Snip» (photo; the video one was captured before it
    updated), «Snipping area», «Quick markup (Ctrl + E)», «Color picker», «Text extractor ( ⊞ + Shift + T)»,
    «Close (Esc)».
  - Mode menu: 125 × 158 at (887, 15), radius 7–10 (estimate), #2c2c2c / #f9f9f9, rows 35 px: Rectangle (selected, 33 px
    #383838 / #f0f0f0 row + accent pill), Window, Full screen, Freeform; 14 px.
  - First-run teaching tip (dark pass only): «Annotate live on your screen» / «Quick markup lets you draw on your
    screen in real time.» / [Got it], 309 × 134 incl. beak, #282828.
- **After capture** (`snip_after_capture`): overlay closes at once; toast 364 × 157 at (1540, 862) dark,
  #1c1c1c, 1 px #3d3d3d: app line «Snipping Tool» (12 px) · «Screenshot copied to clipboard» (14 px) ·
  «Automatically saved to screenshots folder.» (#cbcbcb) · button «Markup and share» 332 × 32. Unchanged 2 s later.

Light vs dark: only colours change; geometry is identical.

## Could not be measured (and why)

- **Acrylic / mica** (Snipping toolbar, menus, print pop-ups, toast): the VM has no GPU, surfaces render flat;
  their background colours carry `reliable: false`.
- **Shadows** (dialogs, menus, pop-ups, toolbar, toast): absent or truncated in the VM; extents listed as
  `reliable: false` (Organize menu shows none).
- **Window corner radius**: square in the VM (DWM without GPU); real Windows 11 rounds top-level windows 8 px.
- **Animations** (tooltip fade, toast slide-in): not measurable from stills; the light after-capture toast was
  caught mid-slide (flagged unreliable, use the dark geometry). Some tooltips overlap the previous one while it
  fades and are marked «not separable»; the «Up» tooltip did not appear in the capture.
- **Font weight**: estimated from stem width, always `reliable: false`; ClearType fringes make coloured text
  (command bar links, header labels) approximate (`reliable: false` on those colours).
- **Hover states that do not show in the captures**: print dialog Printer/Orientation combos and Imprimir/
  Cancelar boxes (only a 1–5 level colour change, recorded at the seed pixel), page arrows (disabled), Snipping
  segments; the toggle knob on hover is hidden under the pointer.
- **Print options that do not exist here**: copies, pages, colour, margins, preview (Microsoft Print to PDF +
  this Notepad); «Más opciones» opens the classic dialog, so there is no modern «More settings» page.
- **Open's split «Abrir ▾» button**: not present in this Notepad build.
- **Dark Save focus/menus/clicks after `pressed-header-nombre`**: the «Nombre» column moved to the end; the list
  numbers come from `-normal`/`-hover` only.
- **«Ubicaciones recientes» menu, file name / address history**: empty (no history in the VM).
- **Tooltip delay** (`snip.tooltip.delay`): captures are taken after a fixed 0.9 s, no timing information.

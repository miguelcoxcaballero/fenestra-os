# Fenestra Shell: visual comparison with Windows 11

Reference: Windows 11 Enterprise Evaluation (build 26100, es-ES) in a QEMU/KVM VM without GPU, 1920×1080, captured on a solid `#1f1f1f` background in four passes (dark/light × 100/150 %). The screenshots live on the `visual/screenshots` branch (`reference-shots/`); this branch holds only the scripts and the numbers. Fenestra: the same screens from the headless KWin bench (`tests/visual/fenestra_bench.py`, `reference-shots/fenestra/`), dark 100 % only (plus Start in light), with the exact panel mask from the surface alpha.

```
python3 tests/visual/measure.py ../shots/reference-shots/solid ../shots/reference-shots/bloom --motion ../shots/reference-shots/motion
python3 tests/visual/compare.py ../shots/reference-shots/solid ../shots/reference-shots/fenestra --md /tmp/t.md -o <outside the repo>
python3 tools/apply-measurements.py --dry-run   # what design/tokens.json would take
```

Conventions: Δ = Fenestra − Windows in pixels of the capture (scale 1 here, both at 100 %). "% pixels" = share of the aligned crop (top-left corners matched, the larger of both boxes) whose largest channel difference is above 16 levels; "% colour" = mean channel difference of that crop. "Mismatches" = measurements of the capture (box, radius, elements, controls, colours) that differ by more than 1 px or 3 % colour; in brackets the ones that are not reliable. Every value in `design/reference/measurements.json` carries `source` (capture) and `at` (pixel).

## Summary of the comparison

| Capture | Windows box (x, y, w, h) | Fenestra box | Δx | Δy | Δw | Δh | % pixels | % colour | Mismatches (unreliable) |
|---|---|---|---|---|---|---|---|---|---|
| dark-100-01-taskbar | 0, 1032, 1920, 48 | 0, 1032, 1920, 48 | 0 | 0 | 0 | 0 | 97.2 | 8.1 | 14 (2) |
| dark-100-03-preview | 1017, 860, 201, 160 | 990, 972, 268, 48 | -27 | 112 | 67 | -112 | 64.3 | 9.2 | 24 (1) |
| dark-100-04-taskbar-menu | 1400, 959, 277, 73 | 834, 940, 228, 80 | -566 | -19 | -49 | 7 | 15.8 | 6.9 | 14 (2) |
| dark-100-05-app-menu | 968, 849, 296, 171 | 1010, 904, 228, 116 | 42 | 55 | -68 | -55 | 35.6 | 8.6 | 17 (2) |
| dark-100-06-start | 639, 294, 642, 726 | 544, 156, 832, 864 | -95 | -138 | 190 | 138 | 14.3 | 3.2 | 48 (0) |
| dark-100-07-start-all | 639, 294, 642, 726 | 544, 156, 832, 864 | -95 | -138 | 190 | 138 | 15.0 | 3.1 | 44 (0) |
| dark-100-08-power-menu | 1150, 861, 116, 102 | 698, 868, 228, 152 | -452 | 7 | 112 | 50 | 8.8 | 4.1 | 16 (2) |
| dark-100-09-account-menu | 654, 833, 362, 128 | 61, 895, 228, 125 | -593 | 62 | -134 | -3 | 13.5 | 7.3 | 17 (2) |
| dark-100-10-search | 785, 294, 776, 726 | 544, 169, 832, 851 | -241 | -125 | 56 | 125 | 29.2 | 4.5 | 59 (0) |
| dark-100-11-search-query | 785, 294, 776, 726 | 544, 169, 832, 851 | -241 | -125 | 56 | 125 | 28.7 | 4.3 | 45 (0) |
| dark-100-12-quick | 1548, 685, 360, 335 | 1459, 659, 400, 361 | -89 | -26 | 40 | 26 | 31.1 | 6.1 | 42 (2) |
| dark-100-15-notifications | 1572, 321, 336, 232 | 1527, 97, 332, 922 | -45 | -224 | -4 | 690 | 50.5 | 10.8 | 12 (1) |
| dark-100-17-toast | 1540, 910, 364, 109 | 1498, 887, 360, 132 | -42 | -23 | -4 | 23 | 24.8 | 6.1 | 15 (2) |
| dark-100-20-secure-attention | 0, 0, 1920, 1080 | 0, 0, 1920, 1080 | 0 | 0 | 0 | 0 | 0.3 | 0.1 | 10 (0) |
| dark-100-27-snap-layouts | 1053, 201, 344, 274 | 557, 12, 806, 108 | -496 | -189 | 462 | -166 | 39.0 | 5.9 | 12 (2) |
| light-100-06-start | 639, 294, 642, 726 | 545, 157, 830, 862 | -94 | -137 | 188 | 136 | 87.6 | 12.2 | 59 (2) |

Fenestra captures with no comparable Windows capture (the Windows one is excluded, see below): `dark-100-18-osd-volume`, `dark-100-22-tray-overflow`, `dark-100-23-desktop-menu`.

Reading the summary: positions of pointer-anchored popups (taskbar menu, jump list, power and account menus, preview) depend on where the bench clicked, so Δx/Δy there say little; the sizes do. Fenestra draws Notification Center as one full-height column and Quick Settings together with the media card, so their boxes cover more than the Windows card. The taskbar row compares the whole bar (the bench has other pinned apps and no weather).

## Per panel

Windows box per pass (x, y, w, h in capture pixels; at 150 % divide by 1.5 for scale 1). `*` = reliable=false (the note says why). Fenestra row = comparison above, when there is one.

### 01 taskbar

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-01-taskbar | `taskbar` | 0 | 1032 | 1920 | 48 | — |  |
| dark-150-01-taskbar | `taskbar` | 0 | 1008 | 1920 | 72 | — |  |
| light-100-01-taskbar | `taskbar` | 0 | 1032 | 1920 | 48 | — |  |
| light-150-01-taskbar | `taskbar` | 0 | 1008 | 1920 | 72 | — |  |

Fenestra `dark-100-01-taskbar`: Δx 0, Δy 0, Δw 0, Δh 0, 97.2 % pixels, 8.1 % colour, 14 mismatches (2 unreliable).

### 02 taskbar-hover (`taskbar.button.hover`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-02-taskbar-hover | `taskbar.button.hover` | 1097 | 1036 | 40 | 38 | 8* | no cuadra con las otras pasadas (mediana 5 px a escala 1) |
| light-100-02-taskbar-hover | `taskbar.button.hover` | 1120 | 1037 | 38 | 38 | 5 |  |
| light-150-02-taskbar-hover | `taskbar.button.hover` | 1165 | 1014 | 60 | 60 | 7 |  |

Fenestra: no bench capture of this screen yet.

- Not measured `dark-150-02-taskbar-hover`: al 150 % (oscuro) el botón del Bloc de notas no muestra fondo de hover ni de atención: el hover no llegó a pintarse.

### 03 preview (`preview`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-03-preview | `preview` | 1017 | 860 | 201* | 160 | 8 | no cuadra con las otras pasadas (mediana 211.333 px a escala 1) |
| dark-150-03-preview | `preview` | 1037 | 750 | 317 | 240 | 12 |  |
| light-150-03-preview | `preview` | 1037 | 750 | 317 | 240 | 12 |  |

Fenestra `dark-100-03-preview`: Δx -27, Δy 112, Δw 67, Δh -112, 64.3 % pixels, 9.2 % colour, 24 mismatches (1 unreliable).

- Not measured `light-100-03-preview`: el ratón quedó sobre Paint: salió la etiqueta «Paint», no la vista previa del Bloc de notas.

### 04 taskbar-menu (`menu.taskbar`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-04-taskbar-menu | `menu.taskbar` | 1400 | 959 | 277 | 73 | 8 |  |
| light-100-04-taskbar-menu | `menu.taskbar` | 1400 | 959 | 277 | 73 | 9 |  |

Fenestra `dark-100-04-taskbar-menu`: Δx -566, Δy -19, Δw -49, Δh 7, 15.8 % pixels, 6.9 % colour, 14 mismatches (2 unreliable).

- Not measured `dark-150-04-taskbar-menu`: al 150 % el clic derecho cayó sobre ^ de la bandeja: no se abrió el menú de la barra.
- Not measured `light-150-04-taskbar-menu`: al 150 % el clic derecho cayó sobre ^ de la bandeja: no se abrió el menú de la barra.

### 05 app-menu (`jumplist`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-05-app-menu | `jumplist` | 968 | 849 | 296 | 171 | 8 |  |
| dark-150-05-app-menu | `jumplist` | 973 | 732 | 444 | 258 | 12 |  |

Fenestra `dark-100-05-app-menu`: Δx 42, Δy 55, Δw -68, Δh -55, 35.6 % pixels, 8.6 % colour, 17 mismatches (2 unreliable).

- Not measured `light-100-05-app-menu`: el clic derecho cayó sobre Paint: no se abrió la lista de saltos del Bloc de notas.
- Not measured `light-150-05-app-menu`: el relleno de la lista de saltos es idéntico a la ventana blanca de detrás: no se puede separar del fondo.

### 06 start (`start`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-06-start | `start` | 639 | 294 | 642 | 726 | 7 |  |
| dark-100-06-start | `start.footer` | — | — | — | 63 | — |  |
| dark-100-06-start | `start.pinned.pitch` | 96 | 84 | — | — | — |  |
| dark-100-06-start | `start.pinned.tile` | — | — | 96* | 84* | — | sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso horizontal de la rejilla; sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso vertical de la rejilla |
| dark-150-06-start | `start` | 478 | 69 | 964 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |
| dark-150-06-start | `start.footer` | — | — | — | 94 | — |  |
| dark-150-06-start | `start.pinned.pitch` | 144 | 126 | — | — | — |  |
| dark-150-06-start | `start.pinned.tile` | — | — | 144* | 126* | — | sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso horizontal de la rejilla; sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso vertical de la rejilla |
| light-100-06-start | `start` | 639 | 294 | 642 | 726 | 7 |  |
| light-100-06-start | `start.footer` | — | — | — | 63 | — |  |
| light-100-06-start | `start.pinned.pitch` | 96 | 84 | — | — | — |  |
| light-100-06-start | `start.pinned.tile` | — | — | 96* | 84* | — | sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso horizontal de la rejilla; sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso vertical de la rejilla |
| light-150-06-start | `start` | 478 | 69 | 964 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |
| light-150-06-start | `start.footer` | — | — | — | 94 | — |  |
| light-150-06-start | `start.pinned.pitch` | 144 | 126 | — | — | — |  |
| light-150-06-start | `start.pinned.tile` | — | — | 144* | 126* | — | sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso horizontal de la rejilla; sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso vertical de la rejilla |

Fenestra `dark-100-06-start`: Δx -95, Δy -138, Δw 190, Δh 138, 14.3 % pixels, 3.2 % colour, 48 mismatches (0 unreliable).
Fenestra `light-100-06-start`: Δx -94, Δy -137, Δw 188, Δh 136, 87.6 % pixels, 12.2 % colour, 59 mismatches (2 unreliable).

### 07 start-all (`start.all`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-07-start-all | `start.all` | 639 | 294 | 642 | 726 | 7 |  |
| dark-150-07-start-all | `start.all` | 478 | 69 | 964 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |
| light-100-07-start-all | `start.all` | 639 | 294 | 642 | 726 | 7 |  |
| light-150-07-start-all | `start.all` | 478 | 69 | 964 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |

Fenestra `dark-100-07-start-all`: Δx -95, Δy -138, Δw 190, Δh 138, 15.0 % pixels, 3.1 % colour, 44 mismatches (0 unreliable).

### 08 power-menu (`menu.power`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-08-power-menu | `menu.item` | — | — | — | 32 | — |  |
| dark-100-08-power-menu | `menu.power` | 1150 | 861 | 116 | 102 | 8 |  |
| dark-150-08-power-menu | `menu.item` | — | — | — | 47 | — |  |
| dark-150-08-power-menu | `menu.power` | 1245 | 754 | 174 | 151 | 12 |  |
| light-100-08-power-menu | `menu.item` | — | — | — | 32 | — |  |
| light-100-08-power-menu | `menu.power` | 1150 | 861 | 116 | 102 | 8 |  |
| light-150-08-power-menu | `menu.item` | — | — | — | 47 | — |  |
| light-150-08-power-menu | `menu.power` | 1245 | 754 | 174 | 151 | 12 |  |

Fenestra `dark-100-08-power-menu`: Δx -452, Δy 7, Δw 112, Δh 50, 8.8 % pixels, 4.1 % colour, 16 mismatches (2 unreliable).

### 09 account-menu (`menu.account`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-09-account-menu | `menu.account` | 654 | 833 | 362 | 128 | 8 |  |
| dark-150-09-account-menu | `menu.account` | 502 | 708 | 543 | 194 | 12 |  |
| light-100-09-account-menu | `menu.account` | 654 | 833 | 362 | 128 | 8 |  |
| light-150-09-account-menu | `menu.account` | 502 | 708 | 543 | 194 | 12 |  |

Fenestra `dark-100-09-account-menu`: Δx -593, Δy 62, Δw -134, Δh -3, 13.5 % pixels, 7.3 % colour, 17 mismatches (2 unreliable).

### 10 search (`search`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-10-search | `search` | 785 | 294 | 776 | 726 | 7 |  |
| dark-150-10-search | `search` | 697 | 69 | 1164 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |
| light-100-10-search | `search` | 785 | 294 | 776 | 726 | 7 |  |
| light-150-10-search | `search` | 697 | 69 | 1164 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |

Fenestra `dark-100-10-search`: Δx -241, Δy -125, Δw 56, Δh 125, 29.2 % pixels, 4.5 % colour, 59 mismatches (0 unreliable).

### 11 search-query (`search.query`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-11-search-query | `search.query` | 785 | 294 | 776 | 726 | 7 |  |
| dark-150-11-search-query | `search.query` | 697 | 69 | 1164 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |
| light-100-11-search-query | `search.query` | 785 | 294 | 776 | 726 | 7 |  |
| light-150-11-search-query | `search.query` | 697 | 69 | 1164 | 921* | 11 | no cuadra con las otras pasadas (mediana 726 px a escala 1) |

Fenestra `dark-100-11-search-query`: Δx -241, Δy -125, Δw 56, Δh 125, 28.7 % pixels, 4.3 % colour, 45 mismatches (0 unreliable).

### 12 quick (`quick`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-12-quick | `quick` | 1548 | 685 | 360 | 335 | 8 |  |
| dark-100-12-quick | `quick.footer` | — | — | — | 47 | — |  |
| dark-100-12-quick | `quick.tile` | — | — | 96 | 48 | — |  |
| dark-150-12-quick | `quick` | 1362 | 486 | 540 | 504 | 11 |  |
| dark-150-12-quick | `quick.footer` | — | — | — | 71 | — |  |
| dark-150-12-quick | `quick.tile` | — | — | 144 | 70 | — |  |
| light-100-12-quick | `quick` | 1548 | 685 | 360 | 335 | 8 |  |
| light-100-12-quick | `quick.footer` | — | — | — | 47 | — |  |
| light-100-12-quick | `quick.tile` | — | — | 96 | 48 | — |  |
| light-150-12-quick | `quick` | 1362 | 486 | 540 | 504 | 11 |  |
| light-150-12-quick | `quick.footer` | — | — | — | 71 | — |  |
| light-150-12-quick | `quick.tile` | — | — | 144 | 71 | — |  |

Fenestra `dark-100-12-quick`: Δx -89, Δy -26, Δw 40, Δh 26, 31.1 % pixels, 6.1 % colour, 42 mismatches (2 unreliable).

### 13 quick-wifi (`quick.wifi`)

Not captured: la VM no tiene adaptador Wi-Fi: no hay subpágina Wi-Fi.

### 14 quick-media (`quick.media`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-14-quick-media | `quick.media` | 1548 | 495 | 360 | 178 | 8 |  |
| light-100-14-quick-media | `quick.media` | 1548 | 495 | 360 | 178 | 8 |  |
| light-150-14-quick-media | `quick.media` | 1362 | 201 | 540 | 267 | 11 |  |

Fenestra: no bench capture of this screen yet.

- Not measured `dark-150-14-quick-media`: una ventana de Seguridad de Windows abierta toca la tarjeta multimedia: no se puede separar.

### 15 notifications (`notifications`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-15-notifications-2 | `notifications.more` | 1572 | 8 | 336 | 545 | 8 |  |
| dark-100-15-notifications | `notifications` | 1572 | 321* | 336 | 232* | 8 | no cuadra con las otras pasadas (mediana 266.667 px a escala 1); solo dos pasadas y no coinciden (321 / 8 px a escala 1) |
| dark-150-15-notifications-2 | `notifications.more` | 1398 | 12 | 504 | 400* | 12 | limitado por la altura de la pantalla al 150 % (mediana 545 px a escala 1) |
| dark-150-15-notifications | `notifications` | 1398 | 12 | 504 | 400 | 12 |  |
| light-100-15-notifications-2 | `notifications.more` | 1572 | 8 | 336 | 545 | 8 |  |
| light-100-15-notifications | `notifications` | 1572 | 8* | 336 | 545* | 8 | no cuadra con las otras pasadas (mediana 266.667 px a escala 1); solo dos pasadas y no coinciden (321 / 8 px a escala 1) |
| light-150-15-notifications-2 | `notifications.more` | 1398 | 12 | 504 | 400* | 12 | limitado por la altura de la pantalla al 150 % (mediana 545 px a escala 1) |
| light-150-15-notifications | `notifications` | 1398 | 12 | 504 | 400 | 12 |  |

Fenestra `dark-100-15-notifications`: Δx -45, Δy -224, Δw -4, Δh 690, 50.5 % pixels, 10.8 % colour, 12 mismatches (1 unreliable).

### 16 calendar (`calendar`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-16-calendar-collapsed | `calendar.collapsed` | 1572 | 920 | 336 | 100 | 8 |  |
| dark-100-16-calendar | `calendar` | 1572 | 565 | 336 | 455 | 8 |  |
| dark-150-16-calendar | `calendar` | 1398 | 430 | 504 | 560* | 12 | no cuadra con las otras pasadas (mediana 455 px a escala 1) |
| light-100-16-calendar-collapsed | `calendar.collapsed` | 1572 | 920 | 336 | 100 | 8 |  |
| light-100-16-calendar | `calendar` | 1572 | 565 | 336 | 455 | 8 |  |
| light-150-16-calendar | `calendar` | 1398 | 430 | 504 | 560* | 12 | no cuadra con las otras pasadas (mediana 455 px a escala 1) |

Fenestra: no bench capture of this screen yet.

- Not measured `dark-150-16-calendar-collapsed`: una ventana de Seguridad de Windows tapa el escritorio y el calendario no está plegado.
- Not measured `light-150-16-calendar-collapsed`: al 150 % (claro) el calendario no se plegó: es la misma vista que 16-calendar.

### 17 toast (`toast`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-17-toast | `toast` | 1540 | 910 | 364 | 109 | 7 |  |
| dark-150-17-toast | `toast` | 1350 | 825 | 546 | 163 | 11 |  |
| light-100-17-toast | `toast` | 1540 | 910 | 364 | 109 | 7 |  |
| light-150-17-toast | `toast` | 1350 | 825 | 546 | 163 | 11 |  |

Fenestra `dark-100-17-toast`: Δx -42, Δy -23, Δw -4, Δh 23, 24.8 % pixels, 6.1 % colour, 15 mismatches (2 unreliable).

### 18 osd-volume (`osd`)

Fenestra: no bench capture of this screen yet.

- Not measured `dark-100-18-osd-volume`: el teclado USB emulado de QEMU no envía teclas multimedia: Windows no mostró el OSD.
- Not measured `dark-150-18-osd-volume`: el teclado USB emulado de QEMU no envía teclas multimedia: Windows no mostró el OSD.
- Not measured `light-100-18-osd-volume`: el teclado USB emulado de QEMU no envía teclas multimedia: Windows no mostró el OSD.
- Not measured `light-150-18-osd-volume`: el teclado USB emulado de QEMU no envía teclas multimedia: Windows no mostró el OSD.

### 19 osd-brightness (`osd.brightness`)

Not captured: la VM no tiene brillo y el teclado emulado no envía teclas multimedia: no hay OSD de brillo.

### 20 secure-attention (`secure`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-20-secure-attention | `secure` | 0 | 0 | 1920 | 1080 | 0 |  |
| dark-150-20-secure-attention | `secure` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-100-20-secure-attention | `secure` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-150-20-secure-attention | `secure` | 0 | 0 | 1920 | 1080 | 0 |  |

Fenestra `dark-100-20-secure-attention`: Δx 0, Δy 0, Δw 0, Δh 0, 0.3 % pixels, 0.1 % colour, 10 mismatches (0 unreliable).

### 21 uac (`uac`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-21-uac | `uac` | 732 | 352 | 456 | 376 | 0 |  |
| dark-150-21-uac | `uac` | 618 | 258 | 684 | 564 | 0 |  |
| light-150-21-uac | `uac` | 618 | 258 | 684 | 564 | 0 |  |

Fenestra: no bench capture of this screen yet.

- Not measured `light-100-21-uac`: el diálogo de UAC no llegó a mostrarse en esta pasada (escritorio normal).

### 22 tray-overflow (`flyout.overflow`)

Fenestra: no bench capture of this screen yet.

- Not measured `dark-100-22-tray-overflow`: la bandeja no tiene iconos ocultos fijos: el clic abre otro flyout (OneDrive), no el desbordamiento.
- Not measured `dark-150-22-tray-overflow`: la bandeja no tiene iconos ocultos fijos: el clic abre otro flyout (OneDrive), no el desbordamiento.
- Not measured `light-100-22-tray-overflow`: la bandeja no tiene iconos ocultos fijos: el clic abre otro flyout (OneDrive), no el desbordamiento.
- Not measured `light-150-22-tray-overflow`: la bandeja no tiene iconos ocultos fijos: el clic abre otro flyout (OneDrive), no el desbordamiento.

### 23 desktop-menu (`menu.desktop`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| light-150-23-desktop-menu | `menu.desktop` | 952 | 60 | 344 | 476 | 20 |  |

Fenestra: no bench capture of this screen yet.

- Not measured `dark-100-23-desktop-menu`: el clic derecho en el escritorio no abrió el menú en las pasadas al 100 % (sí al 150 %).
- Not measured `dark-150-23-desktop-menu`: salió el menú de sistema de la ventana de Seguridad de Windows, no el del escritorio.
- Not measured `light-100-23-desktop-menu`: el clic derecho en el escritorio no abrió el menú en las pasadas al 100 % (sí al 150 %).

### 24 caption-buttons (`window.caption`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-24-caption-close-hover | `window.caption` | 1249 | 201 | 45 | 29 | 0 |  |
| dark-100-24-caption-min-hover | `window.caption` | 1157 | 201 | 45 | 29 | 0 |  |
| light-100-24-caption-buttons | `window.title` | — | — | — | 32 | — |  |

Fenestra: no bench capture of this screen yet.

- Not measured `dark-100-24-caption-buttons`: estado de referencia sin hover para medir los botones de ventana (se usa como ref).
- Not measured `dark-150-24-caption-buttons`: estado de referencia sin hover para medir los botones de ventana (se usa como ref).
- Not measured `dark-150-24-caption-close-hover`: al 150 % la ventana del Bloc de notas sale por la derecha de la pantalla (o está en otro sitio): el ratón no está sobre un botón.
- Not measured `dark-150-24-caption-min-hover`: al 150 % la ventana del Bloc de notas sale por la derecha de la pantalla (o está en otro sitio): el ratón no está sobre un botón.
- Not measured `light-100-24-caption-buttons`: estado de referencia sin hover para medir los botones de ventana (se usa como ref).
- Not measured `light-100-24-caption-close-hover`: la ventana del Explorador tapa los botones del Bloc de notas: el ratón no está sobre un botón.
- Not measured `light-100-24-caption-min-hover`: la ventana del Explorador tapa los botones del Bloc de notas: el ratón no está sobre un botón.
- Not measured `light-150-24-caption-buttons`: estado de referencia sin hover para medir los botones de ventana (se usa como ref).
- Not measured `light-150-24-caption-close-hover`: al 150 % la ventana del Bloc de notas sale por la derecha de la pantalla (o está en otro sitio): el ratón no está sobre un botón.
- Not measured `light-150-24-caption-min-hover`: al 150 % la ventana del Bloc de notas sale por la derecha de la pantalla (o está en otro sitio): el ratón no está sobre un botón.

### 25 alt-tab (`alttab`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-25-alt-tab | `alttab` | 492* | 317 | 937 | 399 | 8 | solo dos pasadas y no coinciden (492 / 229 px a escala 1) |
| dark-100-25-alt-tab | `switcher.thumbnail` | — | — | — | 243 | — |  |
| dark-150-25-alt-tab | `alttab` | 496 | 285 | 928* | 438* | 12 | no cuadra con las otras pasadas (mediana 399 px a escala 1); no cuadra con las otras pasadas (mediana 937 px a escala 1) |
| dark-150-25-alt-tab | `switcher.thumbnail` | — | — | — | 202* | — | imagen de la ventana dentro de la tarjeta seleccionada (sin la tira del título); depende de la proporción de la ventana; no cuadra con las otras pasadas (mediana 243 px a escala 1) |
| light-100-25-alt-tab | `alttab` | 229* | 317 | 1463* | 399 | 7 | no cuadra con las otras pasadas (mediana 937 px a escala 1); solo dos pasadas y no coinciden (492 / 229 px a escala 1) |
| light-100-25-alt-tab | `switcher.thumbnail` | — | — | — | 243 | — |  |
| light-150-25-alt-tab | `alttab` | 496 | 285 | 928* | 438* | 12 | no cuadra con las otras pasadas (mediana 399 px a escala 1); no cuadra con las otras pasadas (mediana 937 px a escala 1) |
| light-150-25-alt-tab | `switcher.thumbnail` | — | — | — | 202* | — | imagen de la ventana dentro de la tarjeta seleccionada (sin la tira del título); depende de la proporción de la ventana; no cuadra con las otras pasadas (mediana 243 px a escala 1) |

Fenestra: no bench capture of this screen yet.

### 26 task-view (`taskview`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-26-task-view | `taskview` | 0 | 0 | 1920 | 1080 | 0 |  |
| dark-150-26-task-view | `taskview` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-100-26-task-view | `taskview` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-150-26-task-view | `taskview` | 0 | 0 | 1920 | 1080 | 0 |  |

Fenestra: no bench capture of this screen yet.

### 27 snap-layouts (`snap`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-27-snap-layouts | `snap` | 1053 | 201 | 344 | 274 | 20 |  |

Fenestra `dark-100-27-snap-layouts`: Δx -496, Δy -189, Δw 462, Δh -166, 39.0 % pixels, 5.9 % colour, 12 mismatches (2 unreliable).

- Not measured `dark-150-27-snap-layouts`: al 150 % el hover no cayó sobre Maximizar: no apareció el panel de ajuste.
- Not measured `light-100-27-snap-layouts`: el ratón no quedó sobre Maximizar: no apareció el panel de ajuste.
- Not measured `light-150-27-snap-layouts`: al 150 % el hover no cayó sobre Maximizar: no apareció el panel de ajuste.

### 28 lock (`lock`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-28-lock | `lock` | 0 | 0 | 1920 | 1080 | 0 |  |
| dark-150-28-lock | `lock` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-100-28-lock | `lock` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-150-28-lock | `lock` | 0 | 0 | 1920 | 1080 | 0 |  |

Fenestra: no bench capture of this screen yet.

### 29 login (`login`)

| Capture | Key | x | y | w | h | radius | Note |
|---|---|---|---|---|---|---|---|
| dark-100-29-login | `login` | 0 | 0 | 1920 | 1080 | 0 |  |
| dark-150-29-login | `login` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-100-29-login | `login` | 0 | 0 | 1920 | 1080 | 0 |  |
| light-150-29-login | `login` | 0 | 0 | 1920 | 1080 | 0 |  |

Fenestra: no bench capture of this screen yet.

## Tokens (design/tokens.json) at scale 1

What `tools/apply-measurements.py` would take: the reliable value at scale 1, dark theme preferred. Placeholder = current value in `design/tokens.json` (taken from the GNOME layer). This branch does not change `tokens.json`; running the tool applies them.

| Token | Placeholder | Measured (scale 1) | Reliable | Source, at | How / note |
|---|---|---|---|---|---|
| `taskbar.height` | 48 | 48 | yes | dark-100-01-taskbar [4, 1032] |  |
| `taskbar.button` | 44 | 40 | yes | dark-100-02-taskbar-hover [1053, 1036] | moda de 10 de 10 capturas de la pasada; fondo del botón (atención / hover), no la separación entre iconos |
| `taskbar.icon` | 24 | 24 | yes | dark-100-01-taskbar [1108, 1044] | lado mayor de los iconos anclados (Explorador, Bloc de notas, Paint) |
| `taskbar.indicator.focused` | 16 | 16 | yes | light-100-02-taskbar-hover [1043, 1072] | moda de 2 de 2 capturas de la pasada |
| `taskbar.indicator.unfocused` | 6 | 6 | yes | dark-100-04-taskbar-menu [1114, 1072] | moda de 7 de 9 capturas de la pasada |
| `taskbar.indicator.height` | 3 | 3 | yes | dark-100-04-taskbar-menu [1114, 1072] | moda de 7 de 9 capturas de la pasada |
| `flyout.gap` | 12 | 12 | yes | dark-100-12-quick [1728, 1020] | = `quick.gap.taskbar` |
| `flyout.edge` | 13 | 12 | yes | dark-100-12-quick [1908, 852] | = `quick.edge.right` |
| `flyout.radius` | 8 | 8 | yes | dark-100-12-quick [1548, 685] | = `quick.radius` |
| `control.radius` | 4 | — | — | — | no probe yet (the control boxes are in `*.control[i]` but their corner radius is not fitted) |
| `menu.item.height` | 36 | 32 | yes | dark-100-08-power-menu [1168, 872] | distancia entre filas de 3 elementos del menú de apagado (sin separadores) |
| `menu.width.min` | 220 | — (only 344 at 150 %) | no | light-150-23-desktop-menu [952, 298] | no capture at 100 % |
| `search.box.width` | 228 | 220 | yes | dark-100-01-taskbar [785, 1056] |  |
| `search.box.height` | 32 | 32 | yes | dark-100-01-taskbar [961, 1040] |  |
| `start.width` | 832 | 642 | yes | dark-100-06-start [639, 657] |  |
| `start.height` | 864 | 726 | yes | dark-100-06-start [960, 294] |  |
| `start.pinned.columns` | 8 | 6 | yes | dark-100-06-start [704, 447] | iconos por fila en Anclado |
| `start.pinned.tile.width` | 80 | 96 | no | dark-100-06-start [704, 447] | sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso horizontal de la rejilla |
| `start.pinned.tile.height` | 69 | 84 | no | dark-100-06-start [704, 447] | sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso vertical de la rejilla |
| `start.footer.height` | 64 | 63 | yes | dark-100-06-start [659, 956] | sin el borde exterior de 1 px |
| `search.width` | 832 | 776 | yes | dark-100-10-search [785, 657] |  |
| `search.height` | 851 | 726 | yes | dark-100-10-search [1173, 294] |  |
| `search.results.width` | 328 | — | — | — | no probe yet: the results / preview split of capture 11 is visible but not read |
| `search.preview.width` | 376 | — | — | — | no probe yet: the results / preview split of capture 11 is visible but not read |
| `quick.width` | 400 | 360 | yes | dark-100-12-quick [1548, 852] |  |
| `quick.tile.width` | 104 | 96 | yes | dark-100-12-quick [1680, 708] | moda de 4 botones de 5 |
| `quick.tile.height` | 48 | 48 | yes | dark-100-12-quick [1680, 708] | moda de 4 botones de 5 |
| `quick.footer.height` | 48 | 47 | yes | dark-100-12-quick [1568, 972] | sin el borde exterior de 1 px |
| `notifications.width` | 332 | 336 | yes | dark-100-15-notifications [1572, 437] |  |
| `toast.width` | 362 | 364 | yes | dark-100-17-toast [1540, 964] |  |
| `calendar.day` | 40 | 41 | yes | dark-100-16-calendar [1767, 759] | diámetro del círculo de hoy |
| `osd.width` | 192 | — | — | — | no capture: the emulated USB keyboard sends no media keys, Windows showed no volume OSD |
| `osd.height` | 48 | — | — | — | no capture (see osd.width) |
| `osd.gap` | 24 | — | — | — | no capture (see osd.width) |
| `osd.timeout` | 1500 | — | — | — | no capture (see osd.width); a timing, not a screenshot value |
| `motion.popup.open` | 200 | 180.2 | no | motion/start-open/f059 [639, 294] | QMP screendump every ~36.5 ms, no GPU; start-open |
| `motion.popup.close` | 120 | — | — | — | only opening animations were captured (motion/) |
| `motion.popup.offset` | 96 | 141 | no | motion/start-open/f059 [639, 294] | QMP screendump every ~36.5 ms, no GPU; start-open |
| `motion.osd.fade` | 150 | — | — | — | no OSD capture |
| `motion.preview.delay` | 400 | — | — | — | a delay, not readable from screenshots |
| `font.family` | Segoe UI Variable Text | — | — | — | not identifiable from pixels with confidence (no reference fonts in the repo to compare glyphs with) |
| `font.body` | 14 | 14 | yes | dark-100-08-power-menu [1195, 875] | primer elemento del menú de apagado: altura de la mayúscula / 0.7 (capHeight de Segoe UI); el peso no se mide; único tamaño compatible con las 4 pasadas (10 px al 100 %, 15 px al 150 %, 10 px al 100 %, 15 px al 150 %): 14 px a escala 1 |
| `font.caption` | 12 | 12 | yes | dark-100-06-start [680, 488] | etiqueta de icono anclado de Inicio: altura de la mayúscula / 0.7 (capHeight de Segoe UI); el peso no se mide; único tamaño compatible con las 4 pasadas (8 px al 100 %, 13 px al 150 %, 8 px al 100 %, 13 px al 150 %): 12 px a escala 1 |
| `desktop.icon` | 32 | — | — | — | no probe yet (Recycle Bin and Edge are in every capture, top-left) |
| `desktop.cell.width` | 76 | — | — | — | no probe yet (see desktop.icon) |
| `desktop.cell.height` | 84 | — | — | — | no probe yet (see desktop.icon) |
| `desktop.margin` | 8 | — | — | — | no probe yet (see desktop.icon) |
| `desktop.label` | 12 | — | — | — | no probe yet (see desktop.icon) |
| `window.button.width` | 46 | 45 | yes | dark-100-24-caption-close-hover [1249, 215] | = `window.caption.width` |
| `window.button.height` | 32 | 29 | yes | dark-100-24-caption-close-hover [1271, 201] | = `window.caption.height` |
| `window.title.height` | 32 | 32 | yes | light-100-24-caption-buttons [100, 815] | diálogo Ejecutar (Win32 clásico, inactivo): del borde superior exterior a la primera fila del área cliente; una sola pasada: sin comprobación cruzada |
| `window.radius` | 8 | — | — | — | not measured: window corners in this VM (no GPU) are not a reliable render |
| `snap.zone.gap` | 4 | — | — | — | no probe yet (Snap Layouts only in dark-100-27) |
| `switcher.thumbnail.height` | 180 | 243 | yes | dark-100-25-alt-tab [936, 414] | imagen de la ventana dentro de la tarjeta seleccionada (sin la tira del título); depende de la proporción de la ventana |
| `snip.toolbar.top` | 8 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.toolbar.radius` | 8 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.toolbar.padding` | 4 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.toolbar.shadow` | 8 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.button.width` | 40 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.button.height` | 36 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.button.radius` | 4 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.button.spacing` | 2 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.icon` | 16 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.separator.height` | 20 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.dim.opacity` | 0.5 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.border.width` | 2 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.border.color` | #ffffff | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |
| `snip.tooltip.delay` | 600 | — | — | — | measured by the dialog measurements (`snip_*` sections of the same file) |

## Never reliable (VM render)

- Acrylic and mica: every `*.background`, `*.background.acrylic*` (bloom pass), `taskbar.background`, `*.border` colour. The VM has no GPU, so blur and noise are not what a real machine draws.
- Shadows: the VM draws no panel shadows (`*.shadow.extent` is 0 or noise). Window shadows exist and change with focus; `mask_tol` keeps them out of the preview box.
- Motion (`motion.*`): QMP screendumps every 17–38 ms, no GPU; durations and offsets are indicative.
- Font weight: not measured. Text sizes (`font.body`, `font.caption`) come from cap heights (Segoe UI capHeight 0.70 em) and are reliable only when one size fits all four passes.

## Measured but not reliable, and why

Geometry flagged by the cross-pass check (the same panel in four passes should scale by 1.5):

- `02 taskbar.button.hover` (dark-100): no cuadra con las otras pasadas
- `03 preview` (dark-100): no cuadra con las otras pasadas
- `06 start` (dark-150, light-150): no cuadra con las otras pasadas
- `06 start.pinned.tile` (dark-100, dark-150, light-100, light-150): sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso horizontal de la rejilla
- `06 start.pinned.tile` (dark-100, dark-150, light-100, light-150): sin captura con hover o foco en un anclado: la placa del icono no se ve; valor = paso vertical de la rejilla
- `07 start.all` (dark-150, light-150): no cuadra con las otras pasadas
- `10 search` (dark-150, light-150): no cuadra con las otras pasadas
- `11 search.query` (dark-150, light-150): no cuadra con las otras pasadas
- `15 notifications` (dark-100, light-100): no cuadra con las otras pasadas
- `15 notifications` (dark-100, light-100): solo dos pasadas y no coinciden (321 / 8 px a escala 1)
- `15 notifications.gap` (dark-150, light-150): no cuadra con las otras pasadas
- `15 notifications.more` (dark-150, light-150): limitado por la altura de la pantalla al 150 %
- `15 notifications.more.gap` (dark-150, light-150): no cuadra con las otras pasadas
- `16 calendar` (dark-150, light-150): no cuadra con las otras pasadas
- `21 uac.gap` (dark-100): no cuadra con las otras pasadas
- `25 alttab` (dark-150, light-100, light-150): no cuadra con las otras pasadas
- `25 alttab` (dark-100, light-100): solo dos pasadas y no coinciden (492 / 229 px a escala 1)
- `25 alttab.edge` (dark-100, light-100): solo dos pasadas y no coinciden (491 / 228 px a escala 1)
- `25 alttab.edge` (dark-100, light-100): solo dos pasadas y no coinciden (492 / 229 px a escala 1)
- `25 alttab.gap` (dark-150, light-150): no cuadra con las otras pasadas
- `25 switcher.thumbnail` (dark-150, light-150): imagen de la ventana dentro de la tarjeta seleccionada (sin la tira del título); depende de la proporción de la ventana; no cuadra con las otras pasadas

Content, not design: the preview and Alt+Tab thumbnails follow the window aspect (the windows differ at 150 %); Notification Center height follows the number of notifications; Alt+Tab width follows the number of windows (light-100 had the Run dialog open); Start, Search and the calendar at 150 % are cut by the 1080 px screen.

## Not measured, and why

- `18-osd-volume` (dark-100, dark-150, light-100, light-150): el teclado USB emulado de QEMU no envía teclas multimedia: Windows no mostró el OSD.
- `22-tray-overflow` (dark-100, dark-150, light-100, light-150): la bandeja no tiene iconos ocultos fijos: el clic abre otro flyout (OneDrive), no el desbordamiento.
- `23-desktop-menu` (dark-100, light-100): el clic derecho en el escritorio no abrió el menú en las pasadas al 100 % (sí al 150 %).
- `24-caption-buttons` (dark-100, dark-150, light-100, light-150): estado de referencia sin hover para medir los botones de ventana (se usa como ref).
- `02-taskbar-hover` (dark-150): al 150 % (oscuro) el botón del Bloc de notas no muestra fondo de hover ni de atención: el hover no llegó a pintarse.
- `04-taskbar-menu` (dark-150, light-150): al 150 % el clic derecho cayó sobre ^ de la bandeja: no se abrió el menú de la barra.
- `14-quick-media` (dark-150): una ventana de Seguridad de Windows abierta toca la tarjeta multimedia: no se puede separar.
- `16-calendar-collapsed` (dark-150): una ventana de Seguridad de Windows tapa el escritorio y el calendario no está plegado.
- `23-desktop-menu` (dark-150): salió el menú de sistema de la ventana de Seguridad de Windows, no el del escritorio.
- `24-caption-close-hover` (dark-150, light-150): al 150 % la ventana del Bloc de notas sale por la derecha de la pantalla (o está en otro sitio): el ratón no está sobre un botón.
- `24-caption-min-hover` (dark-150, light-150): al 150 % la ventana del Bloc de notas sale por la derecha de la pantalla (o está en otro sitio): el ratón no está sobre un botón.
- `27-snap-layouts` (dark-150, light-150): al 150 % el hover no cayó sobre Maximizar: no apareció el panel de ajuste.
- `03-preview` (light-100): el ratón quedó sobre Paint: salió la etiqueta «Paint», no la vista previa del Bloc de notas.
- `05-app-menu` (light-100): el clic derecho cayó sobre Paint: no se abrió la lista de saltos del Bloc de notas.
- `21-uac` (light-100): el diálogo de UAC no llegó a mostrarse en esta pasada (escritorio normal).
- `24-caption-close-hover` (light-100): la ventana del Explorador tapa los botones del Bloc de notas: el ratón no está sobre un botón.
- `24-caption-min-hover` (light-100): la ventana del Explorador tapa los botones del Bloc de notas: el ratón no está sobre un botón.
- `27-snap-layouts` (light-100): el ratón no quedó sobre Maximizar: no apareció el panel de ajuste.
- `05-app-menu` (light-150): el relleno de la lista de saltos es idéntico a la ventana blanca de detrás: no se puede separar del fondo.
- `16-calendar-collapsed` (light-150): al 150 % (claro) el calendario no se plegó: es la misma vista que 16-calendar.
- Panel 13 `quick-wifi`: la VM no tiene adaptador Wi-Fi: no hay subpágina Wi-Fi.
- Panel 19 `osd-brightness`: la VM no tiene brillo y el teclado emulado no envía teclas multimedia: no hay OSD de brillo.
- Token `font.family`: la familia no se identifica con fiabilidad a partir de píxeles (no hay fuentes de referencia en el repositorio para comparar glifos).
- `start.pinned.tile.width` / `.height`: no capture with hover or focus on a pinned app, so the tile plate is not visible; the value given is the grid pitch (96 × 84 at scale 1), marked not reliable. `start.pinned.pitch.x` / `.y` are the reliable numbers.
- `menu.width.min`: the desktop menu only opened at 150 % (light), so there is no scale-1 value (229 px from 344 / 1.5).
- `window.button.*` and `window.title.height` come from single captures: the caption-button hovers are valid only in dark-100 (Notepad, a WinUI title bar: 45 × 29); the title bar is the classic Run dialog in light-100 (32 px from the outer edge to the client area).


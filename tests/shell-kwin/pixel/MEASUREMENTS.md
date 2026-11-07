# Taskbar acrylic and desktop grid: measurements (2026-11-07)

Reference: `reference-shots/` (Windows 11 26100, 1920×1080). Bench: `tests/shell-kwin` (KWin
QPainter, software Qt Quick), default wallpaper `fenestra-bloom-dark.jpg`. The values these
measurements drive are in `design/tokens.json` (`taskbar.acrylic.*`, `desktop.*`, with `_sources`).

## Taskbar material

- `solid/` and `bloom/` `dark-100-01-taskbar` have the **same** taskbar pixels: flat `#1c1c1c`,
  border `#404040` (light: `#eeeeee` / `#bebebe`). The VM had no GPU, so Windows drew the acrylic's
  fallback colour. Those colours are exactly the FallbackColor of WinUI's
  `AcrylicBackgroundFillColorBase`, so the acrylic is that brush's recipe
  (`shell/src/core/acrylic.h`): blur σ 30, luminosity blend, colour blend, 2 % noise.
- `acrylic_ref.py` = independent numpy model of the recipe (no noise); `cmp_taskbar.py` compares
  the empty taskbar background (x 150–700, 1200–1680, rows 1–47).

| Bench taskbar (bloom wallpaper) | vs Windows shot (fallback) | vs recipe model |
|---|---|---|
| before, dark (flat `#1c1c1c`) | max 0, mean 0.00 | — |
| after, dark (acrylic) | max 25, mean 7.72 (expected: acrylic ≠ fallback) | **max 5, mean 2.05** |
| before, light (flat `#eeeeee`) | max 0, mean 0.00 | — |
| after, light (acrylic) | max 15, mean 7.23 | **max 6, mean 2.35** |

The residual vs the model is the noise layer (2 % of a grey texture, ±2.5 levels, mean shift ~2).
`Appearance/Transparency=false` in shell.conf gives the measured fallback (diff 0).

## Desktop grid (100 %)

`measure_desk.py` (content bounding boxes against the cover-scaled wallpaper, first column):

| | Windows (`bloom/dark-100-01`) | before | after |
|---|---|---|---|
| icon size | 48 | 32 | 48 |
| column centre x | 47.5 | 45.5 | 47.0–47.5 |
| row pitch | 124 | 84 | 124 |
| icon top, row 1 | 131 | 101 | (folder glyph 136; 48 box at 131) |
| label glyph top, rows 0 / 1 | 61 / 185 | 53 / 138 | 60 / 185 |
| line pitch of a wrapped label | 15 | 17 | 15 |

Column pitch (96) is not measurable (no reference shot has a second column): derived from the
icon centre (48 → a column from x = 0 is 96 wide), consistent with the label wrapping.
Hover / selection colours are not in any shot either (Explorer ListView colours, estimated alpha).

## Label shadow

`fitshadow.py` on `solid/{dark,light}-100-01-taskbar.png` (white labels on `#1f1f1f`):
black, Gaussian σ 1.6 px, offset (+0.5, +1), alpha = 1.7 × blurred coverage, rmse 1.5 levels.
The same fit on the bench output gives σ 1.8, (+0.5, +1.25), 1.6, rmse 1.7 (the bench font is
Noto Sans, not Segoe UI, and Windows draws the text with ClearType, so glyph coverage differs).

## Popups at 100 %, 150 % and the user's 160 % (2026-11-07)

The user's panel is 2880×1800 at scale **1.6** (1800×1125 logical, `kscreen-doctor -o`), not 1.5.
Bench: `SCALE=1.5 WIDTH=1920 HEIGHT=1080` against `solid/dark-150-*` (Windows at 150 % on 1080p, 1280×720
logical), `SCALE=1.6 WIDTH=2880 HEIGHT=1800` for the user's geometry, plain 1920×1080 against `solid/dark-100-*`;
`Appearance/Transparency=false`, Segoe fonts of the user's pack mounted. `cmp_popup.py`: mean absolute
difference (max of RGB) inside Windows' panel box, and the share of pixels off by more than 24 levels.

| Surface | 100 % before → after | 150 % before → after |
|---|---|---|
| Start (dark-*-06) | 6.80 / 5.0 % → 6.03 / 4.4 % | 10.70 / 6.8 % → 7.29 / 5.1 % |
| Search home (dark-*-10) | 8.16 / 5.1 % → 7.08 / 4.8 % | 12.62 / 6.2 % → 8.95 / 5.8 % |
| Quick settings, whole card (dark-*-12) | 20.29 / 11.2 % → 19.83 / 11.0 % | 20.62 / 11.2 % → 20.18 / 10.9 % |
| Quick settings, slider + footer only | 3.93 / 3.3 % → 3.37 / 3.1 % | 4.89 / 4.2 % → 4.31 / 3.9 % |
| Calendar (dark-*-15, lower card) | 6.00 / 4.1 % → 5.13 / 3.6 % | 11.97 / 6.9 % → 11.90 / 6.9 % |
| Taskbar (dark-*-01) | 11.07 / 7.8 % → 10.96 / 7.7 % | 16.83 / 11.6 % → 16.79 / 11.6 % |

Before = origin/feature/fenestra-shell-kwin 3143301, after = pixel/popups2, same bench and references.
At 160 % the panels are exactly 1.6 × the 100 % ones (Start 1027 × 1162 device px).

Residuals: app icons the bench has no theme for, demo content (Windows' pinned apps, Edge, notifications),
the Quick settings tile set (the VM has Live captions, Nearby sharing and Cast, the bench Airplane mode,
Night light, Accessibility), grey-scale antialiasing against ClearType (Qt draws Segoe UI Variable about
25 % lighter in ink), and at 150 % the calendar, which Windows cuts to four weeks on a 720 px screen.

## Taskbar against the user's own Windows 11 at 150 % (2026-11-07)

Reference: `reference-shots/user-win11/shots/Screenshot 2026-11-04 160039 / 160049 / 163657.png`
(the 2880 x 1800 panel cropped to 2878 x 1798 at the right and bottom: x, y are screen pixels).
Bench: the KWin lab at 2880 x 1800, scale 1.5, `QT_QUICK_BACKEND` unset (Qt's OpenGL renderer on
llvmpipe, as the live session renders; the software renderer rounds fractional rectangles up and
does not show what the user sees), the user's shell.conf, wallpaper, icon overrides, packs, fonts
and icon theme, stand-in windows with Brave's, Explorer's and Spotify's app ids, the pointer and
keys through `org_kde_kwin_fake_input` inside the container. Device px:

| Element | Windows | before | after |
|---|---|---|---|
| top border, rows 1728-1729 | (62.3, 72.0, 69.5) | (64, 64, 64) | (62.5, 71.8, 69.8): #767676 at 40 % |
| bar fill | (25.5, 41.5, 37.5) | (25.7, 41.4, 38.0) | unchanged |
| Start logo | 1290-1324 x 1747-1781 | 1290-1324 x 1746-1780 | 1290-1324 x 1747-1781 (gradients refitted) |
| Search lens (icon mode) | 1357-1391 x 1746-1781 | 1359-1387 x 1749-1778 (20 px) | 1357-1391 x 1746-1781 |
| app cells | 1 px right of the 66 px grid Start starts | on the grid | Start's cell 1 px wider |
| Explorer hover plate | 1477-1536 x 1734-1792, (39, 54, 50), top rows (49, 64, 60), no ring | opaque #2f2f2f, 60 x 60 | 1477-1536 x 1734-1792, (39, 54, 51), top (49, 64, 62) |
| Start open plate (160039) | cell+2 .. +63, rows 1734-1792, ring (44, 59, 55), fill (38, 53, 49) | opaque #292929 | same extent, ring (44, 58, 55), fill (38, 53, 50) |
| unfocused dash (Brave) | 1437-1445 x 1788-1791, (151, 158, 156) | 1436-1444 x 1788-1792, (152, 152, 152) | 1437-1445 x 1788-1791, (151, 159, 157) |
| chevron | 2509-2524 x 1759-1767 | 2545-2558 x 1760-1767 | 2509-2524 x 1759-1767 |
| "ENG" / "ES" | 2558-2590 / 2566-2582, tops 1746 / 1769 | "SPA", one line | 2558-2591 / 2566-2582, tops 1746 / 1769 |
| wifi / volume / battery | 2619 / 2661 / 2703-2732 x 1752-1771 | not drawn on the bench, 24 apart | 2619 / 2661 / 2703-2732 x 1752-1771 |
| clock | 2758-2850, glyph tops 1745 / 1769, "04/11/2026" | ISO date (Qt.formatDate bug), 2762-2848, 1 px low, blurred | 2758-2850, tops 1745 / 1769, hinted |
| preview card | 1383-1631 x 1470-1709, fill (30, 57, 50), top border (57, 82, 75) | opaque card, 12 px gap, no shadow | 1470-1709, fill (28, 55, 49), top border (59, 82, 77), shadow |

Residuals: app icon rasters (Brave and Spotify are the hicolor PNGs, not Windows' own icons), the
preview's content (no live thumbnail), the clock's ink (Qt's grey-scale antialiasing is 0.8 level
lighter than ClearType on average), the attention plate's translucency (only measured on the VM's
opaque fallback: #7f434a, dash #ff99a4, 32 px).

Widgets board (Windows 11 VM, 26100, 100 %): 12 from the left and top edges and above the taskbar,
1000 wide, radius 8; opens ~600 ms after the pointer rests on the weather (~230 ms slide from the
left), closes ~850 ms after the pointer leaves the weather without entering the board, ~270 ms
after it leaves the board; a click opens it at once and keeps it until a click outside (~150 ms
slide out).
## Start, Search and the popups' material against the user's own Windows 11 (2026-11-07)

Reference: `reference-shots/user-win11/shots/Screenshot 2026-11-04 1600{39,49,110,127}.png` — the
user's Windows 11 on this laptop, 2880×1800 at 150 %, dark, transparency on, wallpaper (72, 104, 96).
Bench: `tests/shell-kwin/popups-gl.sh` (KWin `--virtual` with OpenGL compositing on the host's render
node and its blur effect, 2880×1800 at 1.5, the user's wallpaper, fonts, icon theme and icon pack;
`popups-ctl.sh` drives it and captures with ScreenShot2). The captures are 2878×1798 with the same
origin as the screen (Start's panel centre = 1440).

Geometry (logical px = device / 1.5, from the panel's outer top-left; tokens `start.*`, `search.*`):
Start and Search panels 834 × 866, 18 device px above the taskbar's top edge; Start header band 66,
footer band 64.67, 1.33 px dividers; search field 33.33..801.33 × 17.33..49.33; Pinned 8 × 96 × 84
from x 33.33 (icons 32 at y 141.33, two rows, "Show all ˅"); Recent 3 × 256 × 56 (icons at y 382.67);
All: category tiles 156 px, 183.33 / 204.67 px apart, from (65.33, 555.33), 2 × 2 icons of 32 at 28 / 96,
the fourth slot 2 × 2 × 16 px when the category has more apps. Search: Recent searches (18 px semibold,
40 px tiles, 60 px rows), chips 31.33 px high from x 64.67, Best match row 328.67 × 56, preview pane
376.67..800.67 × 120.67..840.67. `cmpbb.py`-style bounding boxes of every element: within 1 device px of
the reference except content (other icons and file names) and the power glyph (2 px taller).

Text: Qt's default instance of Segoe UI Variable is opsz 8 (4 % wider than Windows' text); DirectWrite
uses the device size in points (opsz 15.75 for 14 px at 150 %): `font.opsz`. Qt Quick's distance-field
text drew ClearType-like colour fringes (fontconfig rgba); Windows' shell text is greyscale:
`QSG_DISTANCEFIELD_ANTIALIASING=gray`.

Material: KWin 6.8's blur (default settings, as the user's session; there is no contrast effect any
more) saturates what it blurs: the flat wallpaper (72, 104, 97) comes out (62, 110, 99) ± 1.4 under a
transparent surface. Each fill is the (alpha, grey) whose composite over that is the reference colour:
Start's body (34, 50, 46) = #141414 at 67 %, header/footer (26, 42, 38) = #080808 at 67 % (separate
fills: an overlay on the body cannot keep the chroma), the edge = white 20.5 % over the fill (28 % on
top), menus over Start (38, 49, 45) = #2D2D2D at 57 % with a black 15 % edge. White/black overlays
inside the panel (tiles, chips, hover, text) composite exactly like plain "over" and keep the measured
alphas. Over a bright window Windows' acrylic pins the luminosity and this overlay cannot (no colour
matrix in KWin): the panel follows the backdrop's brightness there.
Shadow (`fitshadow-popup.py`, rms 0.004): black Gaussians σ 2.30 / 8.74 device px, dy 3.18 / 12.68,
opacity 0.217 / 0.346, cut at the taskbar's edge; nothing under the panel.

| Surface (150 %, vs user-win11) | before (origin 7fe14be) | after |
|---|---|---|
| Start, panel box incl. shadow: mean / > 24 levels | 39.99 / 40.9 % | 8.59 / 5.2 % |
| Start, empty body / header / footer patches (mean colour) | 54.6 / 62.5 / 13.5 | 0.1 / 0.1 / 0.2 |
| Start, shadow left / right / gap below / top | 4.6 / 4.6 / 25.6 / 1.7 | 1.2 / 1.1 / 1.0 / 1.2 |
| Search home | 39.72 / 57.8 % | 3.78 / 2.3 % |
| Search results + preview | 41.01 / 62.8 % | 4.18 / 2.3 % |
| Power menu over Start | 45.85 / 68.2 % | 16.35 / 8.0 % (the bench has no Sleep row) |

Motion: the blur region is the moving panel's rounded rectangle cut at the surface's bottom edge,
sent on every frame (`ShellUtil.setBlurItems`); a capture 1 frame into Start's opening shows the
blurred panel half risen and sharp wallpaper where it will land (no ghost). The surface reaches the
taskbar's top edge (input region = panel only), so the panel is clipped there as on Windows.
Quick settings, Notification Center and calendar have no capture on real hardware: same material,
their inner VM greys turned into overlays (`*.acrylic` tokens), layout unchanged.

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

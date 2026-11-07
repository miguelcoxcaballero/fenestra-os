# Pixel pass plan (2026-11-07, deadline 08:00)

Goal: Fenestra Shell on KWin matches the Windows 11 reference shots (`visual/screenshots`,
`reference-shots/`) at the pixel, in both themes. Reference = Windows 11 26100, es-ES, 1920×1080, 100 %.

Each workstream runs on its own branch off `feature/fenestra-shell-kwin` (its own worktree), is
checked with the KWin bench (`tests/shell-kwin`) against the reference shots, and is merged into
`feature/fenestra-shell-kwin` → `main` when its bench diff is better than before.

| # | Workstream | Branch | Reference | Done when |
|---|---|---|---|---|
| 1 | App icons: catalogue the icons of `apps/` (40–45) into `icons.json`, regenerate `ReferenceIcons.g.cs`, build the extractor, export a pack on the Windows 11 VM, import it into this PC | `pixel/icons` | `apps/*` | extractor exports every catalogued icon; pack installed and selected on the host |
| 2 | Popup motion: open/close of Start, Search, Quick settings, Notifications, Calendar, tray flyouts, context menus, as in `motion/` (`times.json`, `analysis.json`) | `pixel/motion` | `motion/*` | same curve, distance, duration and fade as the frames, ±1 frame |
| 3 | Taskbar acrylic + desktop: taskbar transparency/tint/noise as in `bloom/`; desktop icon grid (cell size, spacing, origin, label wrap) and label text shadow | `pixel/desktop` | `bloom/*`, `solid/*-01-taskbar`, `solid/*-23-desktop-menu`, desktop shots | bench diff of taskbar on bloom and desktop grid within ±1 px / ±3 per channel |
| 4 | Popups pixel pass: Start, All apps, Search, Quick settings (+media), Notifications, toasts, Calendar, power/account/app menus, Task view, lock/login | `pixel/popups` | `solid/*`, `fenestra/*` | each panel's geometry, radii, paddings, fonts, colours and icons match |
| 5 | Apps pixel pass: Explorer, Notepad, Paint, Task Manager, Settings, Store, file dialogs | `pixel/apps` | `apps/*`, `dialogs/*` | remaining differences of each app view fixed |

Rules: never copy Microsoft artwork into the repo (icons come from the user's own Windows via the
extractor); one VM at a time (16 GB); measurements recorded next to the code they drive.

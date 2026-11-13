# Drag and drop bench

Runs in the popups bench (`tests/shell-kwin/popups-gl.sh BUILD OUT`, `XWAYLAND=1` for X11 apps),
driven by `tests/lockscreen/fakeinput.c` built inside the container (`fakeinput drag X0 Y0 X1 Y1
[steps] [hold-ms]`: one process for the whole gesture, KWin releases a client's buttons when it
disconnects) and listed in a `.desktop` file with `X-KDE-Wayland-Interfaces=org_kde_kwin_fake_input`.

- `source.py FILE copy|all`: a window that offers FILE as `text/uri-list`, copy/link only (what a
  browser's download row offers) or with move too. Prints `drag-end`.
- `target.py`: a window that prints the files dropped on it (`GDK_BACKEND=x11 DISPLAY=:0` for the
  Xwayland path).

Cases checked by hand on 2026-11-13 (cells are 75.33 x 102 logical px at 150 %):
an icon to a free cell, onto a folder, onto the Recycle Bin, out to target.py (Wayland and
Xwayland); source.py onto the desktop (the file appears at the cell) and onto a folder; Brave's
download bubble onto the desktop.

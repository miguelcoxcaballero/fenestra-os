# Window motion bench

App windows open, close, minimize, restore and maximize as on Windows 11. The motion is
`kwin/effects/fenestra-window-motion`, a KWin scripted effect. The shell installs it, and
`shell/src/services/kwinintegration.cpp` enables it in kwinrc. The same code switches off KWin's
scale, glide, fade, squash, magic lamp and maximize effects.

## Where the Windows values come from

On the reference VM, DWM shows and hides windows with no transition. The VM has no GPU, so DWM uses
WARP. Filming Windows Terminal while it opened gave a window that is complete in its first frame.
So the values below were not filmed. They were read from Windows' own files on the VM disk.

1. **Get the files.** Export the VM disk read-only and pull two files from it:
   - `Windows/System32/uDWM.dll`
   - `Windows/Resources/Themes/aero/aero.msstyles`

   To export the disk, run
   `qemu-storage-daemon … --blockdev driver=raw,offset=<partition>,… --export type=fuse`.
   To read the files, run `7z x` on the exported file. Both files are CompactOS-compressed, so
   7-Zip also writes a `:WofCompressedData` stream next to each one.
2. **Decompress them.** Run `windows/wof.py STREAM SIZE OUT`. This handles XPRESS8K chunks.
3. **Map transitions to storyboards.** Run `windows/udwm_map.py uDWM.dll`. It finds the function
   in uDWM that turns a DWM transition into a theme storyboard (`0x18000c1c4` in 26100), runs it
   for each transition, and prints:
   - 1 open → 100
   - 2 maximize → 104
   - 3 minimize → 94
   - 4 restore from maximized → 104
   - 5 restore from minimized → 95
   - 6 close → 101
   - 12, 13, 18 → 104

   The transition numbers follow DWM's `WindowAnimationType`.
4. **Read the storyboards.** Run `windows/amap.py aero.msstyles 94 95 100 101 104`. It prints
   those storyboards from the theme's animation map (resource `AMAP`), with their transforms and
   cubic-Bézier timing functions. `design/motion.json` lists the result under `"window"`:

| Transition | Windows 11 (26100) |
|---|---|
| Open | Scale 0.8 → 1 about the centre, 250 ms, cubic-bezier(0, 0, 0, 1). Opacity 0 → 1, linear, 0–83 ms. |
| Close | Scale 1 → 0.95 about the centre, 175 ms, cubic-bezier(1, 1, 0, 1). Opacity 1 → 0, linear, 25–175 ms. |
| Minimize | Scale 1 → 0 about the top-left corner while that corner moves to the taskbar button, 167 ms, cubic-bezier(1, 0, 1, 1). No fade. |
| Restore from minimized | The reverse: 175 ms, cubic-bezier(0, 0, 0, 1). |
| Maximize, restore from maximized, snap | Size and position morph from the old frame to the new one, 300 ms, cubic-bezier(0.8, 0, 0, 1). No cross-fade. |

## The effect

KWin's scripted effects only take Qt's easing types, so each Bézier is played as a chain of short
linear pieces:

- A knot every 8 ms, with more knots wherever the curve bends, down to whole milliseconds.
- Scale and Opacity pieces multiply; Translation pieces add.
- Scale is anchored at the top-left corner, so pieces add up exactly.

`simulate.py` runs the effect in a QJSEngine and replays AnimationEffect's arithmetic. The drawn
rect follows the Windows curve within 0.3–3.7 device px, plus up to ~26 px inside the last
millisecond of minimize, where the window moves about 25 px per ms.

Three KWin 6.8 quirks shaped the code. Each has a comment in `main.js`:

- **A piece with a source value ignores its delay.** Its timeline runs while it waits. Delayed
  pieces therefore start from KWin's default source.
- **The id in `animationEnded` reaches the script as 0** (it is a `quint64`).
- **Calling `cancel()` inside `animationEnded` crashes KWin.** Finished motions are swept at the
  next pointer motion or window event instead.

Snapping has no signal of its own in the effect API, so a frame change counts as a snap when it
is not interactive, moves an edge by 32 px or more, and one of the two rects lies against at least
two edges of the screen.

X11 clients repaint at the new size a few frames after a maximize or snap. With a server-side
frame, the morph cross-fades from the old picture. An X11 window that draws its own frame
(Chromium, Electron) keeps its old picture at the old place, cropped by `fenestra-corners` to hide
the new empty pixmap, until the client's picture arrives; the morph starts then. A window that only
shrinks starts at once.

The window shrinks into the centre of its taskbar button. Fenestra's taskbar sends that position
with `org_kde_plasma_window.set_minimized_geometry` (`TaskbarModel::setButtonGeometry`).

## Bench

`./run.sh OUT [fenestra|stock]` starts KWin `--virtual` in the `fenestra-kwinlab` image:
OpenGL on the host's render node, 2880×1800 at scale 1.5. It opens a Qt (Wayland) window and a
GTK 3 window on Xwayland. Each window is opened, minimized, restored, maximized, unmaximized and
closed. Every frame is captured with ScreenShot2 (`record.py`), every 9–14 ms around the window
and every 30–40 ms full screen.

On the host:

- `analyse.py DIR` measures each frame's scale, centre and opacity with no threshold. A window
  scaled by s and drawn at opacity a changes each pixel by `a·D(c + (x − c)/s)`, so the
  difference image's moments give s, c and a.
- `compare.py OUT` fits each recording against the Windows curves. For each frame it prints the
  timing error: how far the Windows curve has to move in time to give the measured value.

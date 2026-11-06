# Boot, restart and update animations

`desktop/libexec/fenestra-plymouth-theme` draws Fenestra's Plymouth screens. Their two
animations were measured frame by frame on Windows 11 25H2 in the reference VM
(`tests/vm/win11.sh`, 1920×1080, 100 % scale). The tables in the generator come from this
analysis; this page says how they were obtained so they can be measured again.

## Recording

`tests/vm/capture.py QMP OUT SECONDS [X Y W H]` records a region of the VM screen through
QMP `screendump` (30–45 fps) with a timestamp per frame. Recorded:

- boot (power on): the progress ring, ~22 s (10 cycles);
- restart from the sign-in screen (power button › Restart): the 5-dot variant on the blue
  sign-in background, 60 s (14 cycles);
- `shutdown /r /t 0` from a session: the black "Restarting" screen with 6 dots, 30 s
  (7 cycles) at 45 fps.

Frames the VM did not redraw (identical to the previous one) are dropped before analysis.

## Dots (restart, shut down, updates)

Each frame is sampled on the dots' circle (an angle-vs-intensity profile, 0.5° bins); peaks
are dots. Dots are tracked frame to frame (they never overtake each other).

Geometry at 1080p: circle radius 29.04 px, centre at 48.47 % of the height, dots 6.5 px.

Timing, measured directly from pop-in / pop-out events:

- 6 dots; dot *n* pops in *n*/6 s after the first and pops out *n*/6 s after the first
  one does (0, 0.167, 0.333 … 0.833 s and 3.20 … 4.03 s);
- the cycle is 4.31 s, so the screen is empty for 0.28 s;
- every dot lives 3.20 s and runs almost two turns.

Path: the dots are not simply delayed copies of each other. In the slow parts they are
0.21–0.23 s apart, where they pop in and out only 0.167 s. A model where dot *n* follows the
same path *n*/6 s later **and 5.25° behind** explains every frame (median error 1.9°, 90 %
under 5°, against 4.6° for the best model without the angular lag). The path was fitted as
55 knots (angle → time) to all frames at once, with a smoothness penalty on the speed.
The speed depends on the position: ~500°/s when the dot appears at the bottom left (185°),
~105°/s across the upper left, ~1400°/s at the lower right (125°), ~105°/s on the upper
left again, and ~500°/s when it disappears on the right (829° = 109°). Dots appear and
disappear at full brightness (no fade).

The sign-in screen variant uses the same timing with 5 dots on a 17.7 px circle.

## Ring (boot)

Each frame is sampled on the ring's circle; the lit arc gives tail and head angles, corrected
for the round caps (half the stroke, 9.8° at this radius).

Geometry at 1080p: stroke axis radius 17.47 px, stroke 6.24 px (area-based), round caps,
centre at 78.35 % of the height.

Timing: a cycle is 3.778 s. The arc grows from a dot (7.5°) to 175° and back, almost
linearly, with the maximum at mid-cycle, while the tail turns exactly 1080°. Every cycle
therefore starts and ends with a dot at the same place (349°, top, slightly left). Tail and
head were fitted per cycle as Fourier series (5 harmonics) of the cycle phase; the VM stalls
during boot make single cycles vary between 3.63 and 3.89 s, so the phase is normalised per
cycle.

## Playback

Frames are rendered at the built-in panel's pixel size (2880×1800 on the Galaxy Book4 Pro)
and Plymouth runs with `DeviceScale=1`. Without it Plymouth uses scale 2 on this panel,
renders at 1440×900 and stretches everything. The frame shown is computed from the time
Plymouth reports through the boot-progress callback (50 frames per second of animation), so
late or dropped refreshes do not slow the animation down.

Checked in QEMU at 2880×1800 (`tests/plymouth/`): every captured frame is one of the
generated frames, and playback runs at 48–51 frames/s per segment.

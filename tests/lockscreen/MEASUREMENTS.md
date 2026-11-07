# Lock screen: Windows 11 measured, Fenestra compared

Reference: Windows 11 Enterprise 24H2 (build 26100) in the reference VM at **2880 x 1800, 150 %**,
dark mode, a local account with a password, the lock picture set to the user's own current
Windows lock photo (`LockScreen___2880_1800_notdimmed.jpg` = Spotlight
`c0bde338…a4b9.jpg`, the same file the GNOME layer used from `/var/lib/windows-spotlight`).
Captures: `~/.cache/fenestra-ref-shots/reference-shots/lock-2880/` (not in the repository: they
contain Windows and the user's photo). Frame recordings: QMP `screendump` back to back (17-50 ms
apart; the VM renders with WARP, so its frame pacing is not Windows' — curves and durations were
read from the frames' timestamps).

Fenestra: `tests/lockscreen/greeter-gl.sh` (real `kscreenlocker_greet --testing`, nested KWin
with OpenGL at 2880 x 1800, scale 1.5, the same photo), shots through KWin ScreenShot2.
Device pixels below; "lp" = logical px (device / 1.5).

## What Windows does

| Element | Windows 11 (measured) |
|---|---|
| Clock view picture | photo at 100 %, black 20.2 % over it (linear fit, residual < 1.3 levels) |
| Time | Segoe UI Variable Display Semibold, 135 lp at 1200 lp of height (96.7 lp at 720); digit tops 245 px (163.3 lp; 128.7 lp at 720) |
| Date | same face, 27.67 lp, ink 1217-1663 x 459-494 ("sábado, 7 de noviembre") |
| Clock view status | network glyph 21 x 21 px centred 48 lp from the right, 28 lp over the bottom |
| Key / click | the clock and widgets go up (−33 px at the first rendered frame) and fade in ~120 ms; the key is not typed into the box |
| Sign-in background | zoom 102 % about the centre, black 46.6 % (fit: residual 1.1-1.5 levels); 500 ms, linear (progress 0.08/0.17/0.25/0.37/0.51/0.60/0.75 at 162-533 ms) |
| Sign-in background blur | not drawn by the VM (no GPU: LogonUI's acrylic falls back to flat colours); Windows on a GPU blurs it (acrylic) |
| Account circle | 288 px (192 lp), white ≈ 5.5 % (+13 levels), top at H/2 − 226.7 lp |
| Default picture | person: head 49.3 lp circle, body 87.3 x 44 lp, ink 1375-1504 x 628-776 |
| Name | Segoe UI Variable Semibold 28 lp, ink 1307-1572 x 879-908 |
| Password box | 296 x 32 lp (underline 1220-1659), fill #1E1E1E at 70 %, 2 lp accent underline (#0078D4) at 1013-1015 with focus |
| Placeholder / dots | 14 lp "Contraseña" at 1234; dots 9 px, 13 px apart; caret 2 x 28 px |
| Reveal / submit | E7B3 / E72A, 12 lp glyphs; ink 1574-1591 / 1622-1639 |
| Wrong password | "La contraseña no es correcta. Inténtalo de nuevo." 14 lp, ink top 1010; "Aceptar" 120 x 32 lp with a 2 px white focus ring 3 px out (1346-1533 x 1087-1142) |
| Welcome | 32 lp progress ring centred 292 lp under the circle's top, "Te damos la bienvenida" 24 lp Semibold |
| Corner buttons | 40 x 40 lp, 16 lp glyphs E839 / E776 / E7E8, centres 2670 / 2742 / 2814 x 1736; hover white 13 %, radius 4 |
| Network flyout | 2300-2843 x 1337-1694: right 24.7 lp, bottom 70.7 lp from the screen edges; LogonUI fallback colour = #0C0C0C at 54.5 % over the mean below; 2 px light border |
| Accessibility flyout | 2325-2861 x 1159-1686, 7 rows of 48 lp (Magnifier E8A3, Contrast E7A1, Narrator ED4D, Voice access, On-screen keyboard E765, Sticky keys, Filter keys), "Desactivado" + 40 x 20 switch |
| Power menu | 2698-2879 x 1573-1699, 40 lp items (Apagar E7E8, Reiniciar E777; Suspender E708 on hardware that sleeps); #191919 at 44 % over the mean below |
| Idle | the sign-in screen goes back to the clock after a while without input; Esc does not |

The Windows Hello face animation itself cannot run in the VM (no camera): Fenestra plays the
user's own copy of Windows' animation (`searching.gif`, 500 frames, 30 ms, 15.37 s loop;
`authentication.gif`, 90 frames, 30 ms, the smile moves for 810 ms) — 122 distinct frames.

## Fenestra against it (same photo, `SigninBlur=false` to compare with the VM)

| Element | Windows | Fenestra | Δ (px) |
|---|---|---|---|
| Whole sign-in screen | — | — | mean diff 1.55 levels, 0.21 % of pixels > 16 (centre block 2.94 / 2.09 %) |
| Whole wrong-password screen | — | — | mean diff 1.67 levels, 0.36 % > 16 |
| Clock view dim | 20.2 % | 19.9 % | −0.3 % |
| Sign-in dim (and 102 % zoom) | 46.6 % | 46.7-48.6 % | ≤ 2 % |
| Time digits (height, top) | 148, 245 | 145-147, 245-246 | ≤ 2 (different minutes) |
| Date ink | 1217-1663 x 459-494 | 1218-1663 x 458-493 | ≤ 1 |
| Default picture ink | 1375-1504 x 628-776 | 1375-1504 x 628-776 | 0 |
| Name ink | 1307-1572 x 879-908 | 1309-1571 x 879-909 | ≤ 2 |
| Focus underline | 1220-1659 x 1013-1015 | 1220-1659 x 1013-1015 | 0 |
| Submit arrow | 1622-1639 x 978-994 | 1623-1639 x 978-993 | ≤ 1 |
| Reveal | 1574-1591 x 983-994 | 1574-1590 x 983-993 | ≤ 1 |
| Password dots, caret | 1235-1243, 1248…, pitch 13; caret 1284-1285 | 1234-1242, 1247…, pitch 13; caret 1283-1284 | ≤ 1 |
| Wrong-password text | 1216-… x 1010-1025 | 1217-… x 1010-1023 | ≤ 2 |
| Corner glyphs | 2658/2732/2803 x 1725-1748 | same | ≤ 1 |
| "Aceptar" + ring | 1346-1533 x 1087-1142 | 1346-1533 x 1086-1142 | ≤ 1 |
| Network flyout right/bottom | 2843 / 1694 | 2842 / 1693 | 1 |
| Accessibility flyout right/bottom | 2861 / 1686 | 2860 / 1685 | 1 |
| Power menu right/bottom | 2879 / 1699 | 2877 / 1699 | 2 |
| Reveal animation | 500 ms linear after 120 ms | same | — |
| Frame pacing (reveal + Hello, 381 frames) | — | median 17 ms, max 25 ms, none dropped | — |

## Behaviour checked end to end (`tests/lockscreen/run.sh`, real kscreenlocker_greet + PAM)

Password (wrong → message + OK → right → unlock), face (Howdy stand-in in the `kde` PAM service:
search loop, smile, unlock), fingerprint (`kde-fingerprint` stand-in), the network flyout
(connect a new secured network with its key, Wi-Fi off), the accessibility switches (Magnifier,
Narrator, Sticky keys commands), the power menu (Sleep, Shut down, Restart commands), the
on-screen keyboard, frame pacing of the reveal and of the Hello animation: QA_RESULT PASS.
The plasma modules are stand-ins on the bench (`mock-qml`); the real ones were checked on the
PC headless (`NetworkModel` roles and `Enums`, `Handler` methods, power and executable engines,
keyboard layouts, MPRIS): same names and values.

## Not measurable on the reference VM

* The acrylic blur of the sign-in background and of the flyouts (no GPU in the VM): Fenestra
  blurs (MultiEffect, blurMax 64) as Windows does on real hardware; `SigninBlur=false` turns it off.
* Windows Hello's layout on the sign-in screen (no camera): the 64 px animation sits where the
  password box is, "Buscándote…" under it.
* Wi-Fi in the network flyout (the VM has Ethernet): the list follows the Ethernet card's
  geometry (glyph, text column, tiles) with Windows' Wi-Fi states.
* The weather / news widgets of the 24H2 clock view (MSN content): not drawn.
* The idle timeout (30 s in Fenestra).

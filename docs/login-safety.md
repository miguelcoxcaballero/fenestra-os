# Login after Fedora 45: causes, fixes and the safety net

Fedora 45 (GNOME Shell / GDM / Mutter 51) left the Galaxy Book on a black screen: the login form
appeared for a fraction of a second after a key press, then disappeared. This page records why,
what was changed, what is verified where, and the mechanisms that keep it from happening again.
They are written to be reused by the KWin-based Fenestra Shell (see the end).

## Causes (verified in the code and in the test bench)

1. **Mutter 51 removed `Meta.Background.set_file()`.** GNOME 51 loads backgrounds as glycin
   textures through a private cache (`BackgroundTextureCache` in `ui/background.js`).
   `createNativeBackground()` in the `face.js` of fenestra-login / single-user-gdm@local,
   fenestra-spotlight / windows-spotlight@local and fenestra-lock-clock called it
   (`TypeError: background.set_file is not a function`).
2. **The login curtain hid the form before it was complete.** single-user-gdm (`_showCurtain`) set
   the LoginDialog's user list to opacity 0 and added a reactive full-screen curtain *before*
   creating the background. The exception left the form invisible under a curtain that no longer
   reacted correctly. That was the black screen with the login flashing.
3. **The lock screen did not lock on GNOME 51** (same exception inside `UnlockDialog`).
4. **Local services:** howdy-preload and galaxy-book-guard had `python3.14` written into them
   (`ModuleNotFoundError: paths_factory`). Fedora 45 moved GDM's PAM files to `/usr/lib/pam.d`
   (`gdm-password` now uses `gdm-password-auth-substack`) and left the old
   `/etc/pam.d/gdm-password` as `.rpmsave`, so Howdy was no longer asked at login.

## Fixes

| Problem | Change |
|---|---|
| `set_file` | `HAS_SET_FILE` in every `face.js`: without it, the picture is an `St.Widget` with `background-image` + `background-size: cover` (GNOME 49, 50, 51) |
| Dead curtain | single-user-gdm / fenestra-login: `_supported()` checks the LoginDialog internals first; `_failSafe()` brings back the user list and removes the curtain on any error (`_showCurtain`, `_dismiss`) |
| Laptop's system copies | `extras/fedora-upgrade/system-extensions/` (windows-spotlight@local, single-user-gdm@local), patched |
| Re-enabling them | `extras/fedora-upgrade/restore-login-extensions.sh`: backup, install, Spotlight first and the login curtain later, `--rollback`, never restarts GDM |
| Local services | `extras/fedora-upgrade/fix-local-services.sh`: version-free `python3`, site-packages of the running Python, `/etc/pam.d/gdm-password` regenerated from the vendor file with Howdy before the password substack. `--dry-run` and `--rollback` are available. The release upgrade runs it again after every upgrade |
| Repo content | The 122 Hello animation frames inside `system-extensions/windows-spotlight@local/hello-assets` were removed. Nothing used them, and they looked extracted from Windows. Fenestra's own frames come from `assets/generated/hello` |

## Safety net (prevention)

1. **Compatibility matrix:** `extras/compat/login-extensions.json`. It lists every extension
   that runs on the login screen (`gdm`) or the lock screen (`unlock-dialog`), with the GNOME
   majors where it was validated (`real` = used on a machine, `bench` = passed the bench).
2. **Removed-API linter:** `tools/lint-shell-extensions.py`.
   - Its rules cover what GNOME 44–51 removed: `set_file`, St `vertical`,
     `gdm/util.js` → `gdm/userVerifier.js`, `_onVerificationComplete`, positional
     `_queueMessage`, `Shell.GLSLEffect`, `affectsInputRegion`, `Clutter.Container`, legacy `imports`.
   - A rule applies only when the extension declares a GNOME without that API, and a feature
     check in the file counts as a guard. `--target N` checks a release before upgrading to it.
   - It flags the pre-fix versions and finds nothing in the current tree.
3. **Module syntax:** `gjs -m tools/check-js-syntax.js FILE...`. GJS parses a module before
   resolving its imports, so a `SyntaxError` is reported while missing shell-only imports are ignored.
4. **Greeter bench:** `tests/greeter/bench.sh`. It starts headless GNOME Shell in `--mode=gdm`
   and in a user session, in a fedora:N container, with:
   - real AccountsService users;
   - a fake logind and a fake GDM that implements the greeter channel (`OpenSession` with the
     `Greeter` / `UserVerifier` interfaces of GDM's `gdm-session.xml`);
   - the Hello assets;
   - a forced-failure scenario (no background).

   Each run ends with a verdict, `QA_RESULT PASS|FAIL`: is the login form visible and usable,
   with no curtain on top, and no tested extension in the ERROR state? The bench must also
   **fail** with the versions before the fix (taken from git), which proves it detects the
   Fedora 45 black screen.
5. **CI:** `.github/workflows/login-safety.yml` runs the linter, the syntax check (fedora:45)
   and the bench (`matrix.fedora` takes the next release when it exists).
6. **Fenestra Update gate:** `fenestra-release-upgrade`.
   - Before the restart into a new release, it works out the target GNOME from the release's
     repositories.
   - It runs `fenestra-login-guard disable-unvalidated`: login extensions that are not
     validated for that GNOME are turned off in the GDM settings, so the standard login stays.
     Lock-screen extensions are turned off at that user's next login.
   - Settings lists them before the upgrade starts.
7. **Automatic greeter recovery:** `fenestra-greeter-guard.service` →
   `fenestra-login-guard watch`, for 3 minutes after every GDM start.
   - It reads the greeter's GNOME Shell messages (uid `gdm` / dynamic `gdm-greeter`, never a user
     session) and attributes errors to an extension: `Extension <uuid>:` or the extension's path
     in the stack trace.
   - It turns off **only that extension** in `/etc/dconf/db/gdm.d`, with a backup. A crash loop
     with no identifiable culprit (3 restarts in 90 s) turns off all greeter extensions.
   - At most 3 per boot. Logged in `/var/log/fenestra-login-guard.log`, state in
     `/var/lib/fenestra/login-guard.json`.
   - The user is told at the next login. `fenestra-login-guard revert [UUID]` undoes it.
   - GDM is restarted only when no user session exists. GDM itself is never disabled, so the
     standard login always remains.

## What is verified where

| Check | Where | Result |
|---|---|---|
| Fixed extensions on the greeter (curtain → password), forced failure (fail-safe → standard login), Spotlight only (restore step 1), lock screen in a user session | `tests/greeter/bench.sh`, fedora:45, GNOME Shell 51.1, GDM 51.1.1 | PASS |
| Pre-fix versions | same | FAIL, as required. Screenshots: black screen; after the key, background without the form |
| Linter / syntax | repo | no findings / 309 modules without syntax errors; the pre-fix files are flagged |
| restore-login-extensions.sh, fix-local-services.sh (install, idempotence, rollback) | fedora:45 container with the laptop's layout reproduced | OK |
| fenestra-login-guard: attribution on the real broken greeter log, nothing on the fixed logs, revert, `disable-unvalidated` | fedora:45 container | OK |
| Typing the password, Howdy and fingerprint at the real GDM, the guard on the real journal, GDM restarts | **only on the laptop** | not verified |

## Restoring the Fenestra login on the laptop

Each step is separate. Nothing restarts GDM; the changes apply at the next login screen.

1. `sudo bash extras/fedora-upgrade/fix-local-services.sh --dry-run` shows the changes. Then
   run it without `--dry-run`. This fixes howdy-preload and galaxy-book-guard, and Howdy in gdm-password.
2. `sudo bash extras/fedora-upgrade/restore-login-extensions.sh` (step 1). It installs the
   guard, then the fixed copies, and enables **windows-spotlight only**.
   - Lock and unlock (Super+L).
   - Log out, or restart when it suits you: the picture behind GNOME's user list.
3. `sudo bash extras/fedora-upgrade/restore-login-extensions.sh --enable-login` (step 2):
   Fenestra's clock curtain on the login screen.
4. At any point: `--status`, or `--rollback` (back to the standard login).

## If the login screen breaks again

1. **Ctrl+Alt+F3** (or GRUB `e` → add `systemd.unit=multi-user.target`) gives a text console. Sign in there.
2. Run `sudo /usr/local/libexec/fenestra/fenestra-login-guard status` to see what the guard
   already turned off.
3. Run `sudo bash extras/fedora-upgrade/restore-login-extensions.sh --rollback` to get the
   standard GNOME login.
4. Run `journalctl -b -u gdm` and `journalctl -b _COMM=gnome-shell | grep -i "JS ERROR\|Extension"`
   to find the cause.

## Reuse in the KWin architecture (feature/fenestra-shell-kwin)

None of this depends on GNOME specifically:
- the matrix keyed by component and validated platform versions;
- the linter's "removed in version N, guard" rules;
- a headless bench whose verdict is "the login form is usable";
- the gate before restarting into a new platform;
- a guard that turns off **only the customization layer**, never the login manager itself.

With SDDM and a Fenestra QML theme, the same pattern means:
- validate the theme per SDDM/Qt version;
- the guard switches SDDM back to its stock theme when the greeter logs QML errors or restarts in a loop;
- the GNOME/GDM session stays installed as the known-good fallback.

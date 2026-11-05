# Fenestra OOBE

First-boot setup ("out-of-box experience") for Fenestra (Fedora 43 / GNOME 49).
It replaces GNOME Initial Setup with a full-screen flow whose geometry is
matched to reference captures of the familiar desktop OOBE (1920×1080):

- a single light translucent card, 1200×760 at (360,160), radius 8, on a pale
  blue-grey background with soft blue/periwinkle blobs;
- the illustration is centred in the left half;
- the title (28 px) starts at x≈1007;
- lists start at y≈313, with 58 px rows on a 62 px pitch, 18 px text, and the
  selected row filled solid with the #0067c0 accent;
- the suggested item is pinned on top, with type-ahead instead of a search
  box;
- the primary button is 127×38 at the bottom right;
- secondary actions are accent-coloured text;
- a back arrow sits at the card's top-left;
- a single accessibility button sits under the card's bottom-right corner;
  its popover also holds the volume slider;
- progress pages show a 64 px ring and a 20 px caption.

`tools/compare.py` renders the matching pages and writes side-by-side
`screenshots/compare-*.png` images (reference left, Fenestra right). Measured
deviations are within about 2 px; the illustrations and branding are
intentionally different.

Written in Python 3.14 + PyGObject + GTK 4.20, with its own CSS (no
libadwaita). It only uses Fedora Workstation packages: python3-gobject, gtk4,
python3-cairo, librsvg2, NetworkManager (nmcli), accountsservice,
systemd-localed/timedated/hostnamed, and the `Gdm-1.0` typelib from gdm.
All illustrations in `data/illustrations/` are original SVGs.

## Flow

**System mode.** GDM starts this when the system has no users. It runs as the
dynamic initial-setup user in GDM's `gnome-initial-setup` session.

| # | page id | Title |
|---|---------|-------|
| 1 | `region` | Is this the right country or region? (searchable; guessed from time zone, then locale) |
| 2 | `keyboard` | Is this the right keyboard layout or input method? (xkb `evdev.lst`, translated) |
| 3 | `keyboard-second` → `keyboard-pick` | Want to add a second keyboard layout? (Add layout / Skip) |
| 4 | `network` (+ `network-offline`) | Let's connect you to a network. Wi‑Fi through nmcli, with the password entered inline. "I don't have internet" leads to "Continue with limited setup". The page is skipped when a wired or full connection already exists. |
| 5 | `updates` | "Checking for updates" progress ring, for at least 3 s while `nmcli networking connectivity check` runs. Shown only when online. |
| 6 | `device-name` | Let's name your device. Up to 15 characters; letters, digits and hyphens; not only digits. |
| 7 | `account-name`, `account-password`, `account-confirm`, `account-hint` | Who's going to use this device? / Create a super memorable password / Confirm your password / Add a password hint |
| 8 | `applying` | Progress ring: "Getting things ready for you", then "Thanks for your patience". Applies hostname, locale, keyboard and time zone, creates the account, then logs in automatically. |

**Existing-user mode (`--existing-user`).** This runs at the first login of
the new user, full screen over the desktop.

| # | page id | Title |
|---|---------|-------|
| 9 | `privacy` | Choose privacy settings for your device. Toggles for Location, Automatic time zone, Diagnostic data and Tailored experiences. |
| 10a | `icons` (+ `icons-pack`, `icons-browser`) | Personalize your icons. Selectable options: **Fenestra default**; **Import from my Windows partition** (only when one with `Windows/Fonts/segoeui.ttf` is found; runs `fenestra-import-windows-assets --windows <mount>`); **Import an icon pack (.zip)** (a file chooser filtered to `*.zip`); **Download an icon pack from a link** (mini browser). A pack is validated and previewed before **Apply** runs `fenestra-import-windows-assets --pack FILE.zip`. |
| 10b | `customize` | Let's customize your experience. Grid of interests, saved to `~/.config/fenestra/oobe.json`. |
| 12 | `finale-1..4` | Full-screen sequence: "Hi" → "We're getting everything ready for you" → "This might take a few minutes / Don't turn off your PC" → "Let's start" (about 10 s), then it writes `~/.config/gnome-initial-setup-done` and exits. |

Keyboard: **Enter** triggers the primary button and **Esc** goes back where
that's allowed. In demo mode, Ctrl+Q quits. Page changes slide and fade over
about 260 ms with ease-out, and illustrations crossfade.

## How system mode creates the user and logs in

1. **System settings.** These are set over D-Bus. The polkit rule
   `20-gnome-initial-setup.rules` allows them without a password prompt.
   - `hostname1.SetStaticHostname` gets the name in lower case;
     `SetPrettyHostname` keeps the name as typed.
   - `locale1.SetLocale` sets `LANG` plus `LC_*` formats for the chosen
     region.
   - `locale1.SetX11Keyboard` sets the layouts; with two layouts it also sets
     `grp:win_space_toggle`.
   - `timedate1.SetTimezone` and `SetNTP(true)` set the clock.
   - The keyboard choice is also applied immediately to the setup session's
     `org.gnome.desktop.input-sources`, so the password is typed with the
     right layout.
2. **Account.** The account is created through AccountsService:
   - `CreateUser(name, full name, 1 = administrator)`.
   - `SetPassword(crypt, hint)`. The crypt value is a SHA-512 `$6$` hash
     made through ctypes calls to libxcrypt's `crypt_gensalt` and `crypt`.
     If that fails, it falls back to `openssl passwd -6 -stdin`.
   - `SetLanguage`, plus `SetFormatsLocale` where accountsservice supports it.
   - If "Try again" is used after a partial failure, the account that was
     already created is reused.
3. **Hand-off files.** These go into the setup user's home
   (`/run/gdm/gnome-initial-setup`):
   - `.config/fenestra/oobe-system.json` holds the region, formats and
     layouts for the first-login step.
   - `gnome-initial-setup-uid` holds the new uid. As with g-i-s, GDM uses it
     to chown that home to the new user.
   - The done file is **not** written here. That keeps the first-login
     service enabled for the new user.
4. **Automatic login.** This uses `Gdm.Client`, mirroring g-i-s's summary
   page:
   - `get_greeter_sync` and `get_user_verifier_sync` connect at startup.
   - `begin_verification_for_user("gdm-password", user)` starts the login.
   - The `secret-info-query` signal is answered with the password.
   - On the greeter's `session-opened`, `start_session_when_ready` is called.
   - On failure, or after a 25 s timeout, the app exits and GDM shows its
     normal login screen.

## Icon packs

- **Format.** The format is `docs/ICON-PACK-FORMAT.md` (v1): zips made by *Fenestra Icon Extractor*,
  with `fenestra-pack.json`. A third-party zip that contains an `index.theme` is installed as a plain icon
  theme.
- **Validation.** It is done in one place, `tools/fenestra-import-windows-assets` (`inspect_pack`,
  `safe_extract`). The OOBE loads that file as a module, so the OOBE, Settings and the command line agree.
  It refuses:
  - a missing or invalid manifest;
  - any `format` other than `fenestra-icon-pack`, or any `version` other than `1`;
  - a bad `id` or theme name;
  - `..`, absolute paths and drive letters;
  - symlinks;
  - more than 1 GB uncompressed, counted again while extracting.
- **What gets installed.** Everything goes into the user's own data directory:
  - fonts → `~/.local/share/fonts/fenestra-pack/<id>`
  - `.cur`/`.ani` cursors → an Xcursor theme
  - `raw/Sysbatt.ttf` → battery SVGs
  - `assets/*` → `~/.local/share/fenestra/assets`, then the Start logo goes to ArcMenu and the search
    icon to a user copy of `fenestra-search.desktop`
  - `icons/<theme>` → `~/.local/share/icons`, with `Inherits=Fenestra` added, and `icon-theme` is set
- **Optional extras.** These go beyond the spec: an `accent` (`#rrggbb`) in the manifest sets
  `org.fenestra.desktop accent-color-custom` when that key exists, and `assets/branding/settings.png`
  becomes the Settings icon.
- **Mini browser.** It uses WebKitGTK 6 (`webkitgtk6.0`) with an ephemeral session. The home page is a
  local help page (`data/help/icon-packs.<lang>.html`) that links to the Fenestra releases page; no
  remote URL is preloaded.
  - Downloads are saved to `~/Downloads` (a temporary folder in `--demo`) and checked automatically.
  - Direct `.zip` links are downloaded with libsoup without the web view.
  - Without WebKit, the page shows a plain text explanation and the address bar, which then only
    downloads.
- **From Settings.** Settings › Personalization › Themes › *Icon pack* runs `fenestra-oobe --icons`,
  which shows the same step in a window.

## Integration

`install.sh` installs:

- `/usr/libexec/fenestra-oobe`: the launcher.
- `/usr/share/fenestra-oobe/`: the Python package, `style.css` and the
  illustrations.
- `/usr/lib/systemd/user/gnome-initial-setup.service.d/fenestra.conf`: sets
  `ExecStart=` then `ExecStart=/usr/libexec/fenestra-oobe`.
- `/usr/lib/systemd/user/gnome-initial-setup-first-login.service.d/fenestra.conf`:
  sets `ExecStart=` then `ExecStart=… --existing-user`. The unit keeps its
  `ConditionPathExists=!%E/gnome-initial-setup-done`.
- `/usr/share/applications/org.fenestra.Oobe.desktop`: `NoDisplay=true`.

GDM only starts the initial-setup session when there are no users, initial
setup isn't disabled in `/etc/gdm/custom.conf`, and (Fedora patch)
`/etc/sysconfig/anaconda` doesn't say `post_install_tools_disabled = 1`.
That's why the kickstart uses `firstboot --enable` and creates no user.

```sh
sudo ./install.sh                            # /usr
DESTDIR=$PWD/stage PREFIX=/usr ./install.sh  # packaging / kickstart %post
DESTDIR=$PWD/stage ./install.sh --uninstall
```

The import page calls `/usr/libexec/fenestra-import-windows-assets <mountpoint>`
(also exported as `FENESTRA_WINDOWS_ROOT`) if that helper is installed.

## Testing

**Never run the app on your real desktop session.** Use a headless compositor
instead, with `WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland` and `DISPLAY`
unset.

```sh
export WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland; unset DISPLAY
bin/fenestra-oobe --demo --windowed                  # whole flow, nothing on the system changes
bin/fenestra-oobe --demo --existing-user --windowed  # first-login part only
bin/fenestra-oobe --list-pages
bin/fenestra-oobe --page network --screenshot out.png [--size 1920x1080] [--lang es]
tools/screenshot-all.sh        # every page -> screenshots/<page>.png (uses fenestra-test)
tools/screenshot-all.sh --es   # Spanish variants -> screenshots/<page>-es.png
tools/compare.py               # side-by-side comparisons with tests/vm/shots/win11/*.png
~/.local/bin/fenestra-test-run python3 -m unittest tests.test_backends tests.test_iconpack tests.test_flow_demo
```

- `--demo` mocks every write: account creation, hostname, localed/timedated,
  Wi‑Fi connection (fake network list), gsettings, the done file and volume.
  Reads are real, such as the country and layout lists.
- `--screenshot` renders the window's widget tree through
  `Gtk.WidgetPaintable` and `GskRenderer.render_texture`, then saves a PNG.
  It forces the GL renderer because Vulkan read-back is corrupt on some Intel
  drivers. The window is not resizable so that mutter doesn't auto-maximize
  it.
- `tests/test_backends.py` covers:
  - hostname rules;
  - username derivation (lower case, accents removed, reserved names,
    collisions such as `alex` → `alex2`, `miguel` → `miguelcaballero` →
    `mcaballero`);
  - that `$6$` hashes verify through libcrypt and match `openssl`;
  - locale defaults and nmcli parsing;
  - Spanish catalog completeness, and that the product name is never
    replaced by another vendor's.
- `tests/test_flow_demo.py` drives the whole demo flow programmatically, from
  region to the finale.

UI language comes from `LANG` / `LC_MESSAGES` (English by default, Spanish
included in `fenestra_oobe/translations/es.py`) or `--lang`.

## Screenshots

See `screenshots/`: one PNG per page id (`region.png` … `finale-4.png`),
Spanish variants (`*-es.png`), `privacy-1366x768.png` for small screens, and
`compare-{region,keyboard,second-keyboard,checking-for-updates}.png`.

## Known limitations

- The whole first boot (system mode, account creation, automatic GDM login,
  first-login pages, finale) is exercised in the `tests/vm` VM on a fresh
  install; `nmcli` Wi‑Fi connections are not (the VM is wired).
- The Wi‑Fi list doesn't handle enterprise (802.1X) or hidden networks.
- "Checking for updates" only checks connectivity.
- Text size and high contrast are applied to the OOBE itself immediately. In
  real mode they are also written to gsettings, and the setup session's dconf
  is copied to the new user by `gnome-initial-setup-copy-worker`.
- Fonts fall back to Selawik/Inter/sans when Segoe UI is not installed. The
  light weight on the finale needs a font with a 300 weight.
- `Gtk.Switch` prints baseline warnings on GTK 4.20, so a custom pill
  `ToggleSwitch` is used instead.

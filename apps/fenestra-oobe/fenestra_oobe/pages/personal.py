"""First-login pages: privacy, customization and asset import."""

from gi.repository import GLib, Gtk

from ..backends import run_async
from ..backends.privacy import abrt_available
from ..i18n import _
from ..widgets.controls import CheckRow, SettingRow
from .base import Page


class PrivacyPage(Page):
    page_id = "privacy"
    illustration = "privacy"
    can_go_back = False

    def __init__(self, ctx):
        super().__init__(ctx, _("Choose privacy settings for your device"),
                         _("Fenestra puts you in control of your privacy. Choose your settings, then "
                           "select “Accept” to save them. You can change these settings at any time "
                           "in Settings."))
        self.primary_label = _("Accept")
        defaults = self.backends.privacy.defaults()
        diag_desc = _("Send crash reports automatically so problems can be found and fixed faster. "
                      "Reports never include your files.")
        if not abrt_available():
            diag_desc = _("Allow apps to report technical problems so they can be found and fixed "
                          "faster. Reports never include your files.")
        specs = [
            ("location", "find-location-symbolic", _("Location"),
             _("Let apps use your location for things like weather, maps and directions. "
               "Location services use nearby Wi‑Fi networks to work out where you are.")),
            ("auto-timezone", "preferences-system-time-symbolic", _("Automatic time zone"),
             _("Keep the clock right when you travel by setting the time zone from your location.")),
            ("diagnostics", "computer-fail-symbolic", _("Diagnostic data"), diag_desc),
            ("tailored", "document-open-recent-symbolic", _("Tailored experiences"),
             _("Remember the files and apps you've used recently so you can get back to them quickly "
               "from the Start menu and file dialogs.")),
        ]
        self.rows = {}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["settings-list"])
        for key, icon, title, desc in specs:
            row = SettingRow(icon, title, desc, defaults.get(key, True))
            self.rows[key] = row
            box.append(row)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, child=box,
                                      css_classes=["plain-scroller"])
        self.body.append(scroller)

    def focus_widget(self):
        return next(iter(self.rows.values())).switch

    def on_primary(self):
        values = {k: r.active for k, r in self.rows.items()}
        self.state.privacy = values
        try:
            self.backends.privacy.apply(values)
        except Exception as exc:  # noqa: BLE001 - settings are best effort
            from ..backends import log
            log.warning("privacy settings: %s", exc)
        self.ctx.next()


INTERESTS = [
    ("gaming", "input-gaming-symbolic", "Gaming", "Play and discover games"),
    ("family", "system-users-symbolic", "Family", "Keep your family connected and safe"),
    ("creativity", "applications-graphics-symbolic", "Creativity", "Bring ideas to life"),
    ("schoolwork", "accessories-dictionary-symbolic", "Schoolwork", "Take notes, write essays, collaborate"),
    ("entertainment", "applications-multimedia-symbolic", "Entertainment", "Stream videos and music"),
    ("business", "x-office-presentation-symbolic", "Business", "Track expenses, manage your business"),
    ("development", "utilities-terminal-symbolic", "Development", "Write code and build apps"),
]


class CustomizePage(Page):
    page_id = "customize"
    illustration = "customize"

    def __init__(self, ctx):
        super().__init__(ctx, _("Let's customize your experience"),
                         _("Select all the ways you plan to use your device to get personalized tips "
                           "and app suggestions. You can change these anytime."))
        self.primary_label = _("Accept")
        self.secondary_label = _("Skip")
        grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=2,
                           min_children_per_line=2, homogeneous=True, column_spacing=8,
                           row_spacing=8, css_classes=["interest-grid"])
        self.rows = {}
        for key, icon, title, desc in INTERESTS:
            row = CheckRow(icon, _(title), _(desc))
            self.rows[key] = row
            grid.append(row)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, child=grid,
                                      css_classes=["plain-scroller"])
        self.body.append(scroller)

    def _save(self, interests):
        self.state.interests = interests
        try:
            self.backends.system.save_user_choices({"interests": interests,
                                                    "privacy": self.state.privacy})
        except OSError as exc:
            from ..backends import log
            log.warning("could not save choices: %s", exc)

    def on_primary(self):
        self._save([k for k, r in self.rows.items() if r.active])
        self.ctx.next()

    def on_secondary(self):
        self._save([])
        self.ctx.next()


class ImportPage(Page):
    """Offered only when another system's partition with its fonts is found."""

    page_id = "import"
    illustration = "import"

    def __init__(self, ctx):
        super().__init__(ctx, _("Bring your fonts and pointers along"),
                         _("We found another operating system on this device. Fenestra can copy the "
                           "fonts and mouse pointers you already own from it into your personal folder, "
                           "so documents and apps look the way you're used to."))
        self.primary_label = _("Import")
        self.secondary_label = _("Not now")
        self.location = Gtk.Label(xalign=0, wrap=True, css_classes=["hint-text"])
        self.body.append(self.location)
        for icon, text in (
            ("font-x-generic-symbolic", _("Fonts are copied to ~/.local/share/fonts")),
            ("input-mouse-symbolic", _("Mouse pointers are copied to ~/.local/share/icons")),
            ("security-high-symbolic", _("The other partition is only read, never changed")),
        ):
            row = Gtk.Box(spacing=14, css_classes=["benefit-row"])
            row.append(Gtk.Image(icon_name=icon, pixel_size=20, css_classes=["benefit-icon"]))
            row.append(Gtk.Label(label=text, xalign=0, wrap=True))
            self.body.append(row)
        prog = Gtk.Box(spacing=12, css_classes=["progress-row"])
        self.spinner = Gtk.Spinner(css_classes=["oobe-spinner"])
        self.status = Gtk.Label(xalign=0, wrap=True, css_classes=["dim"])
        prog.append(self.spinner)
        prog.append(self.status)
        self.body.append(prog)

    def should_skip(self):
        return not self.ctx.other_system_root

    def on_enter(self, direction):
        root = self.ctx.other_system_root or ""
        self.location.set_label(_("Found at {path}").format(path=root))

    def on_primary(self):
        if self.busy:
            return
        self.set_busy(True)
        self.spinner.start()
        self.status.set_label(_("Copying your fonts and pointers…"))
        run_async(self.backends.privacy.run_import, self.ctx.other_system_root, callback=self._done)

    def _done(self, result, error):
        self.spinner.stop()
        self.set_busy(False)
        if error is not None:
            self.status.set_label(_("Some items couldn't be copied. You can try again later from Settings."))
            GLib.timeout_add(1800, lambda: (self.ctx.next(), False)[1])
            return
        if result == "missing-helper":
            self.status.set_label(_("The import tool isn't installed, so nothing was copied."))
            GLib.timeout_add(1800, lambda: (self.ctx.next(), False)[1])
            return
        self.status.set_label(_("Done"))
        self.ctx.next()

    def on_secondary(self):
        self.ctx.next()

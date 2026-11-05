"""First-login pages: privacy, customization and asset import."""

from gi.repository import Gtk

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

"""Device name, account and "Just a moment" pages."""

from gi.repository import GLib, Gtk

from ..backends import accounts as acc
from ..backends import hostname as hn
from ..backends import run_async
from ..i18n import _
from .base import Page

HOSTNAME_ERRORS = {
    "spaces": "Your device name can't contain spaces.",
    "too-long": "Your device name can't be more than 15 characters.",
    "invalid-chars": "Your device name can only contain letters, numbers and hyphens.",
    "only-numbers": "Your device name can't be only numbers.",
    "hyphen-edge": "Your device name can't start or end with a hyphen.",
}


def _entry(placeholder="", password=False):
    if password:
        e = Gtk.PasswordEntry(show_peek_icon=True, css_classes=["oobe-entry"])
        e.set_property("placeholder-text", placeholder)
    else:
        e = Gtk.Entry(placeholder_text=placeholder, css_classes=["oobe-entry"])
    return e


class DeviceNamePage(Page):
    page_id = "device-name"
    illustration = "device"

    def __init__(self, ctx):
        super().__init__(ctx, _("Let's name your device"),
                         _("Give your device a unique name that's easy to recognize when connecting "
                           "to it from other devices."))
        self.primary_label = _("Next")
        self.secondary_label = _("Skip for now")
        self.entry = _entry(_("Device name"))
        self.entry.set_max_length(32)
        self.entry.connect("changed", lambda *_: self._validate())
        self.entry.connect("activate", lambda *_: self.on_primary())
        self.body.append(self.entry)
        self.rules = Gtk.Label(label=_("Can't be more than 15 characters, contain spaces, or the "
                                       "following characters: ` ~ ! @ # $ % ^ & * ( ) = + _ [ ] { } "
                                       "\\ | ; : . ' \" , < > / ?"),
                               xalign=0, wrap=True, css_classes=["hint-text"])
        self.body.append(self.rules)
        self.error = Gtk.Label(xalign=0, wrap=True, css_classes=["error-text"], visible=False)
        self.body.append(self.error)
        self.primary_sensitive = False

    def focus_widget(self):
        return self.entry

    def _validate(self):
        name = self.entry.get_text()
        err = hn.validate_hostname(name)
        if err and err != "empty":
            self.error.set_label(_(HOSTNAME_ERRORS[err]))
            self.error.set_visible(True)
            self.entry.add_css_class("invalid")
        else:
            self.error.set_visible(False)
            self.entry.remove_css_class("invalid")
        self.set_primary_sensitive(err is None)

    def on_primary(self):
        name = self.entry.get_text()
        if hn.validate_hostname(name) is not None:
            return
        self.state.hostname = name
        self.ctx.next()

    def on_secondary(self):
        self.state.hostname = None
        self.ctx.next()


class AccountNamePage(Page):
    page_id = "account-name"
    illustration = "account"

    def __init__(self, ctx):
        super().__init__(ctx, _("Who's going to use this device?"), _("What's your name?"))
        self.primary_label = _("Next")
        self.entry = _entry(_("Name"))
        self.entry.set_max_length(64)
        self.entry.connect("changed", lambda *_: self._update())
        self.entry.connect("activate", lambda *_: self.on_primary())
        self.body.append(self.entry)
        self.info = Gtk.Label(xalign=0, wrap=True, css_classes=["hint-text"], use_markup=True)
        self.body.append(self.info)
        self.primary_sensitive = False
        self._username = None
        self._taken = ctx.username_taken

    def focus_widget(self):
        return self.entry

    def _update(self):
        name = self.entry.get_text().strip()
        self._username = acc.derive_username(name, self._taken) if name else None
        if self._username:
            self.info.set_markup(_("You'll use <b>{user}</b> to sign in.").format(
                user=GLib.markup_escape_text(self._username)))
        elif name:
            self.info.set_markup(_("Use letters or numbers in your name."))
        else:
            self.info.set_markup("")
        self.set_primary_sensitive(bool(self._username))

    def on_primary(self):
        if not self._username:
            return
        self.state.full_name = self.entry.get_text().strip()
        self.state.username = self._username
        self.ctx.next()


class PasswordPage(Page):
    page_id = "account-password"
    illustration = "password"

    def __init__(self, ctx):
        super().__init__(ctx, _("Create a super memorable password"),
                         _("Make sure to pick something you'll absolutely remember."))
        self.primary_label = _("Next")
        self.entry = _entry(_("Password"), password=True)
        self.entry.connect("changed", lambda *_: self.set_primary_sensitive(bool(self.entry.get_text())))
        self.entry.connect("activate", lambda *_: self.on_primary())
        self.body.append(self.entry)
        self.primary_sensitive = False

    def focus_widget(self):
        return self.entry

    def on_primary(self):
        pw = self.entry.get_text()
        if not pw:
            return
        self.state.password = pw
        self.ctx.next()


class ConfirmPasswordPage(Page):
    page_id = "account-confirm"
    illustration = "password"

    def __init__(self, ctx):
        super().__init__(ctx, _("Confirm your password"), _("Please enter your password again."))
        self.primary_label = _("Next")
        self.entry = _entry(_("Confirm password"), password=True)
        self.entry.connect("changed", lambda *_: self._changed())
        self.entry.connect("activate", lambda *_: self.on_primary())
        self.body.append(self.entry)
        self.error = Gtk.Label(xalign=0, wrap=True, css_classes=["error-text"], visible=False)
        self.body.append(self.error)
        self.primary_sensitive = False

    def focus_widget(self):
        return self.entry

    def on_enter(self, direction):
        if direction > 0:
            self.entry.set_text("")
            self.error.set_visible(False)

    def _changed(self):
        self.error.set_visible(False)
        self.set_primary_sensitive(bool(self.entry.get_text()))

    def on_primary(self):
        if self.entry.get_text() != self.state.password:
            self.error.set_label(_("The passwords don't match. Try again."))
            self.error.set_visible(True)
            self.entry.set_text("")
            self.entry.grab_focus()
            return
        self.ctx.next()


class HintPage(Page):
    page_id = "account-hint"
    illustration = "password"

    def __init__(self, ctx):
        super().__init__(ctx, _("Add a password hint"),
                         _("Choose a hint that will help you remember your password. "
                           "It's optional, and it can't contain your password."))
        self.primary_label = _("Next")
        self.entry = _entry(_("Password hint (optional)"))
        self.entry.set_max_length(80)
        self.entry.connect("changed", lambda *_: self.error.set_visible(False))
        self.entry.connect("activate", lambda *_: self.on_primary())
        self.body.append(self.entry)
        self.error = Gtk.Label(xalign=0, wrap=True, css_classes=["error-text"], visible=False)
        self.body.append(self.error)

    def focus_widget(self):
        return self.entry

    def on_primary(self):
        hint = self.entry.get_text().strip()
        if hint and self.state.password and self.state.password.lower() in hint.lower():
            self.error.set_label(_("Your hint can't contain your password."))
            self.error.set_visible(True)
            return
        self.state.hint = hint
        self.ctx.next()


class ApplyingPage(Page):
    """Creates the account and applies every system setting."""

    page_id = "applying"
    illustration = "account"
    can_go_back = False
    transient = True

    def __init__(self, ctx):
        super().__init__(ctx, "")
        box = self.make_spinner_layout(_("Getting things ready for you"))
        self.status = self.spinner_label
        self.error = Gtk.Label(xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER,
                               css_classes=["error-text"], visible=False)
        self.error.set_max_width_chars(46)
        box.append(self.error)
        self._done = False

    def on_enter(self, direction):
        if self._done:
            return
        self.error.set_visible(False)
        self.spinner.set_visible(True)
        self.status.set_label(_("Getting things ready for you"))
        self.primary_label = None
        self.ctx.update_footer(self)
        if self.ctx.screenshot_mode:
            return
        self.spinner.start()
        run_async(self._apply, callback=self._applied)

    def _apply(self):
        st, b = self.state, self.backends
        if st.hostname:
            try:
                b.hostname.set_hostname(st.hostname)
            except GLib.Error as exc:
                # Not fatal: keep going with the default name.
                from ..backends import log
                log.warning("could not set hostname: %s", exc.message)
        b.locale.apply(st.lang_locale, st.formats, st.layouts, st.timezone)
        uid = b.accounts.create_user(st.full_name, st.username, st.password, st.hint,
                                     language=st.lang_locale, formats=st.formats)
        return uid

    def _applied(self, uid, error):
        self.spinner.stop()
        if error is not None:
            msg = getattr(error, "message", None) or str(error)
            self.error.set_label(_("Something went wrong while creating your account.") + "\n" + msg)
            self.error.set_visible(True)
            self.status.set_label(_("Something went wrong"))
            self.spinner.set_visible(False)
            self.primary_label = _("Try again")
            self.ctx.update_footer(self)
            return
        self._done = True
        self.state.uid = uid
        self.status.set_label(_("Thanks for your patience"))
        self.spinner.start()
        self.ctx.account_created()

    def on_primary(self):
        self.on_enter(1)

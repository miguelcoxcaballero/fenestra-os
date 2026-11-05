"""Accounts: your info, sign-in options, other users."""
from __future__ import annotations

from gi.repository import Gio, GLib, Gtk

from .. import util
from ..backends import accounts, hello
from ..i18n import N_, _
from ..widgets import ExpanderRow, SettingRow, ToggleSwitch, button, confirm, label, show_dialog, toast, value_label
from .base import Page, register


@register
class AccountsPage(Page):
    id = "accounts"
    title = "Accounts"
    keywords = "user profile sign in password picture family"
    ROWS = [
        ("yourinfo", N_("Your info"), N_("Accounts used by email, calendar, and contacts"), "fs-person-symbolic"),
        ("signin", N_("Sign-in options"), N_("Fingerprint, password, automatic login"), "fs-key-symbolic"),
    ]

    def build(self, box):
        u = accounts.current_user()
        hero = Gtk.Box(spacing=20)
        hero.add_css_class("hero")
        from ..nav import Avatar  # here, not at import time: nav imports the page registry
        av = Avatar(96)
        av.set_user(u)
        hero.append(av)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        tb.append(label(u.real_name, "hero-name"))
        tb.append(label(_("Local Account"), "hero-model"))
        tb.append(label(_("Administrator") if u.is_admin else _("Standard user"), "hero-model"))
        hero.append(tb)
        box.append(hero)
        g = self.group(_("Account settings"))
        for pid, t, s, ic in self.ROWS:
            self.nav_row(g, pid, _(t), _(s), ic)
        self.ext_row(g, _("Email & accounts"), _("Online accounts used by email, calendar, and contacts"),
                     "fs-mail-symbolic", ["gnome-control-center", "online-accounts"])
        self.nav_row(g, "otherusers", _("Other users"), _("Device access, work or school users"),
                     "fs-people-symbolic")


@register
class YourInfoPage(Page):
    id = "yourinfo"
    parent = "accounts"
    title = "Your info"
    keywords = "profile picture avatar name photo"
    index = [("photo", "Choose a file", "picture avatar photo"), ("name", "Full name", "display name")]

    def build(self, box):
        u = accounts.current_user()
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER)
        hero.add_css_class("hero")
        from ..nav import Avatar
        self.av = Avatar(160)
        self.av.set_user(u)
        hero.append(self.av)
        hero.append(label(u.real_name, "subtitle-text", xalign=0.5))
        hero.append(label(_("Local Account"), "caption", xalign=0.5))
        hero.append(label(_("Administrator") if u.is_admin else _("Standard user"), "caption", xalign=0.5))
        box.append(hero)
        g = self.group(_("Adjust your photo"))
        r = SettingRow(_("Choose a file"), None, "fs-image-symbolic",
                       control=button(_("Browse files"), self._browse), key="photo")
        self.remember("photo", r)
        g.add(r)
        if util.have("snapshot"):
            g.add(SettingRow(_("Take a photo"), None, "fs-camera-symbolic",
                             control=button(_("Open Camera"), lambda: util.launch(["snapshot"]))))
        g2 = self.group(_("Account settings"))
        self.name_entry = Gtk.Entry()
        self.name_entry.add_css_class("fluent-entry")
        self.name_entry.set_text(u.real_name)
        self.name_entry.set_size_request(240, -1)
        self.name_entry.set_valign(Gtk.Align.CENTER)
        self.name_entry.connect("activate", lambda e: self._rename(e.get_text()))
        r = SettingRow(_("Full name"), _("Press Enter to save"), "fs-person-symbolic", control=self.name_entry,
                       key="name")
        self.remember("name", r)
        g2.add(r)
        g2.add(SettingRow(_("User name"), None, "fs-person-key-symbolic", control=value_label(u.username)))

    def _rename(self, name):
        name = name.strip()
        if not name:
            return
        u = accounts.current_user()

        def done(ok, _r):
            toast(self.box, _("Name updated") if ok else _("This action is disabled in read-only mode")
                  if util.READ_ONLY else _("Couldn't update the name"))
            if ok:
                self.window.nav.refresh_user()
        u.set_real_name(name, done)

    def _browse(self):
        dlg = Gtk.FileDialog()
        dlg.set_title(_("Choose a file"))
        flt = Gtk.FileFilter()
        flt.set_name(_("Images"))
        flt.add_pixbuf_formats()
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        dlg.set_filters(store)
        pics = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        if pics:
            dlg.set_initial_folder(Gio.File.new_for_path(pics))

        def done(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            if not f or not f.get_path():
                return
            if util.READ_ONLY:
                toast(self.box, _("This action is disabled in read-only mode"))
                return
            u = accounts.current_user()

            def set_done(ok, _r):
                if ok:
                    u._load()
                    self.av.set_user(u)
                    self.window.nav.refresh_user()
                    toast(self.box, _("Your picture has been updated"))
                else:
                    toast(self.box, _("Couldn't update your picture"))
            u.set_icon_file(f.get_path(), set_done)
        dlg.open(self.box.get_root(), None, done)


@register
class SignInPage(Page):
    id = "signin"
    parent = "accounts"
    title = "Sign-in options"
    keywords = "password fingerprint face facial recognition hello howdy pin automatic login lock"
    index = [("face", "Facial recognition (Fenestra Hello)", "face camera howdy hello"),
             ("fingerprint", "Fingerprint recognition (Fenestra Hello)", "fprint finger hello"),
             ("password", "Password", "change password"),
             ("autologin", "Automatic login", "sign in without password")]

    def build(self, box):
        g = self.group(_("Ways to sign in"))
        # ---- face
        self.face = ExpanderRow(_("Facial recognition (Fenestra Hello)"), _("Checking…"), "fs-person-symbolic",
                                key="face")
        self.remember("face", self.face)
        g.add(self.face)
        # ---- fingerprint
        self.fp = ExpanderRow(_("Fingerprint recognition (Fenestra Hello)"), _("Checking…"),
                              "fs-fingerprint-symbolic", key="fingerprint")
        self.remember("fingerprint", self.fp)
        g.add(self.fp)
        pw = SettingRow(_("Password"), _("Sign in with your account's password"), "fs-key-symbolic",
                        control=button(_("Change"), lambda: self._cc()), key="password")
        self.remember("password", pw)
        g.add(pw)
        g2 = self.group(_("Additional settings"))
        u = accounts.current_user()
        auto = SettingRow(_("Automatic login"), _("Sign in to this account without a password at startup"),
                          "fs-person-key-symbolic", control=ToggleSwitch(u.automatic_login, self._autologin),
                          key="autologin")
        self.remember("autologin", auto)
        g2.add(auto)
        g2.add(SettingRow(_("Lock screen"), _("Require sign-in after the screen turns off"),
                          "fs-lock-closed-symbolic", chevron=True, on_click=lambda: self.go("screenlock")))
        self.refresh()

    def on_show(self):
        if hasattr(self, "face"):
            self.refresh()

    def refresh(self):
        self._face_state()
        hello.fingerprint_device(self._fp_device)

    # ------------------------------------------------------------------ face
    def _face_state(self):
        exp = self.face
        exp.clear()
        if not hello.howdy_available():
            exp.header.set_subtitle(_("This option is currently unavailable"))
            exp.add(SettingRow(_("Facial recognition needs Howdy and an infrared camera."), None, None))
            return
        enrolled = hello.howdy_enrolled()
        if not enrolled:
            exp.header.set_subtitle(_("Sign in with your camera (Recommended)"))
            exp.add(SettingRow(_("Use your face to sign in, unlock your device and confirm it's you"), None, None,
                               control=button(_("Set up"), lambda: self._wizard("face"), accent=False)))
        else:
            exp.header.set_subtitle(_("You're all set up to sign in with your face"))
            exp.add(SettingRow(_("Improve recognition"), _("Add another face model, for example with glasses"),
                               None, control=button(_("Improve recognition"),
                                                    lambda: self._wizard("face", improve=True))))
            exp.add(SettingRow(_("Remove this sign-in option"), None, None,
                               control=button(_("Remove"), self._face_remove)))
        t = ToggleSwitch(hello.howdy_auto_dismiss(), self._auto_dismiss)
        exp.add(SettingRow(_("Automatically dismiss the lock screen if we recognize your face"), None, None,
                           control=t))

    def _auto_dismiss(self, on):
        def done(ok, msg):
            if not ok:
                toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else hello.howdy_error_text(msg) if msg == "auth" else _("The change was not applied"))
            self._face_state()
        hello.howdy_set_auto_dismiss(on, done)

    def _face_remove(self):
        def go():
            hello.howdy_clear(lambda ok, msg: (toast(self.box, _("Facial recognition was removed") if ok else
                                                     _("This action is disabled in read-only mode")
                                                     if util.READ_ONLY else hello.howdy_error_text(msg)),
                                               self._face_state()))
        confirm(self.box, _("Remove facial recognition?"),
                _("You won't be able to use your face to sign in anymore."), _("Remove"), go)

    # ------------------------------------------------------------------ fingerprint
    def _fp_device(self, dev):
        exp = self.fp
        exp.clear()
        if dev is None:
            exp.header.set_subtitle(_("This option is currently unavailable"))
            exp.add(SettingRow(_("No fingerprint reader was found"), None, None))
            return
        self.fp_dev = dev
        dev.list_fingers(self._fp_fingers)

    def _fp_fingers(self, fingers):
        exp = self.fp
        exp.clear()
        if not fingers:
            exp.header.set_subtitle(_("Sign in with your fingerprint scanner (Recommended)"))
            exp.add(SettingRow(_("Use your fingerprint to sign in, unlock your device and confirm it's you"),
                               self.fp_dev.name or None, None,
                               control=button(_("Set up"), lambda: self._wizard("finger"))))
            return
        exp.header.set_subtitle(_("You're all set up to sign in with your fingerprint"))
        for f in fingers:
            exp.add(SettingRow(_(hello.FINGER_LABELS.get(f, f)), None, None))
        exp.add(SettingRow(_("Add another fingerprint"), None, None,
                           control=button(_("Add a finger"), lambda: self._wizard("finger"))))
        exp.add(SettingRow(_("Remove this sign-in option"), None, None,
                           control=button(_("Remove"), self._fp_remove)))

    def _fp_remove(self):
        dev = self.fp_dev

        def go():
            def claimed(ok, _e):
                if not ok:
                    toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                          else _("Couldn't access the fingerprint sensor. It might be in use by another app."))
                    return

                def deleted(ok2, _e2):
                    dev.release()
                    toast(self.box, _("Fingerprints removed") if ok2 else _("The change was not applied"))
                    dev.list_fingers(self._fp_fingers)
                dev.delete_all(deleted)
            dev.claim(claimed)
        confirm(self.box, _("Remove fingerprint recognition?"),
                _("All fingerprints enrolled for your account will be deleted."), _("Remove"), go)

    # ------------------------------------------------------------------ wizard
    def _wizard(self, kind, improve=False):
        from ..hello_wizard import HelloWizard
        wiz = HelloWizard(kind, on_finish=lambda changed: self.refresh(), improve=improve)
        show_dialog(self.box, wiz)

    def _autologin(self, on):
        u = accounts.current_user()

        def done(ok, _r):
            if not ok:
                toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("The change was not applied"))
            u._load()
            self._rows["autologin"].control.set_active(u.automatic_login)
        u.set_automatic_login(on, done)

    def _cc(self):
        if not util.open_control_center("users"):
            toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                  else _("Could not open {0}").format("gnome-control-center"))


@register
class OtherUsersPage(Page):
    id = "otherusers"
    parent = "accounts"
    title = "Other users"
    keywords = "add user family guest accounts"

    def build(self, box):
        g = self.group(_("Other users"))
        me = accounts.current_user().username
        others = [u for u in accounts.list_users() if u[0] != me]
        if not others:
            g.add(SettingRow(_("No other users on this device"), None, "fs-people-symbolic"))
        for name, full, uid in others:
            g.add(SettingRow(full, name, "fs-person-symbolic"))
        self.ext_row(g, _("Add other user"), _("Create an account for another person"), "fs-people-team-symbolic",
                     ["gnome-control-center", "system", "users"])

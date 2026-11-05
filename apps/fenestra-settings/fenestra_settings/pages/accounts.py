"""Accounts: your info, sign-in options, other users."""
from __future__ import annotations

from gi.repository import Gio, GLib, Gtk

from .. import util
from ..backends import accounts
from ..i18n import N_, _
from ..nav import Avatar
from ..widgets import SettingRow, button, label, toast, value_label
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
    keywords = "password fingerprint pin automatic login lock"
    index = [("password", "Password", "change password"), ("fingerprint", "Fingerprint recognition", "fprint"),
             ("autologin", "Automatic login", "sign in without password")]

    def build(self, box):
        g = self.group(_("Ways to sign in"))
        self.fp = SettingRow(_("Fingerprint recognition"), _("Checking…"), "fs-fingerprint-symbolic",
                             key="fingerprint")
        self.remember("fingerprint", self.fp)
        g.add(self.fp)
        accounts.fingerprint_status(self._fp)
        pw = SettingRow(_("Password"), _("Sign in with your account's password"), "fs-key-symbolic",
                        control=button(_("Change"), lambda: self._cc()), key="password")
        self.remember("password", pw)
        g.add(pw)
        g2 = self.group(_("Additional settings"))
        auto = SettingRow(_("Automatic login"), _("Sign in to this account without a password at startup"),
                          "fs-person-key-symbolic", control=button(_("Manage"), lambda: self._cc()), key="autologin")
        self.remember("autologin", auto)
        g2.add(auto)
        g2.add(SettingRow(_("Lock screen"), _("Require sign-in after the screen turns off"),
                          "fs-lock-closed-symbolic", chevron=True, on_click=lambda: self.go("screenlock")))

    def _cc(self):
        if not util.open_control_center("users"):
            toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                  else _("Could not open {0}").format("gnome-control-center"))

    def _fp(self, state):
        if state == "none":
            self.fp.set_subtitle(_("No fingerprint reader was found"))
            self.fp.set_control(label(_("Not available"), "row-value"))
        elif state == "enrolled":
            self.fp.set_subtitle(_("You're all set up to sign in with your fingerprint"))
            self.fp.set_control(button(_("Manage"), lambda: self._enroll()))
        else:
            self.fp.set_subtitle(_("Sign in with your fingerprint scanner"))
            self.fp.set_control(button(_("Set up"), lambda: self._enroll()))

    def _enroll(self):
        if util.READ_ONLY:
            toast(self.box, _("This action is disabled in read-only mode"))
            return
        toast(self.box, _("Touch the fingerprint sensor repeatedly…"), )
        util.run_async(["fprintd-enroll"], lambda ok, o, e: (toast(self.box, _("Fingerprint enrolled") if ok
                                                                        else _("Fingerprint enrollment failed")),
                                                                  accounts.fingerprint_status(self._fp)),
                       mutating=True)


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

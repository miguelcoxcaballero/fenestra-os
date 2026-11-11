"""Enterprise Wi-Fi (WPA2/WPA3-Enterprise, 802.1X): every setting a network such as eduroam or a
university's own needs, and the official settings of an eduroam institution (eduroam CAT)."""
from __future__ import annotations

import threading

from gi.repository import GLib, Gtk

from ..backends import eduroam_cat
from ..i18n import _
from ..widgets import Dropdown, button, label, link, spinner, toast

METHODS = [("peap", "PEAP"), ("ttls", "TTLS"), ("tls", "TLS"), ("pwd", "PWD"), ("fast", "FAST"), ("leap", "LEAP")]
PHASE2 = {
    "peap": [("mschapv2", "MSCHAPv2"), ("gtc", "GTC"), ("md5", "MD5")],
    "ttls": [("pap", "PAP"), ("mschapv2", "MSCHAPv2"), ("mschap", "MSCHAP"), ("chap", "CHAP"),
             ("eap-mschapv2", "EAP-MSCHAPv2"), ("eap-gtc", "EAP-GTC"), ("eap-md5", "EAP-MD5")],
    "fast": [("mschapv2", "MSCHAPv2"), ("gtc", "GTC")],
}
PASSWORDLESS = ("tls",)
DEFAULTS = {"method": "peap", "phase2": "mschapv2", "ca": "none"}


def _entry(placeholder=None, password=False):
    e = Gtk.PasswordEntry() if password else Gtk.Entry()
    if password:
        e.set_show_peek_icon(True)
        if placeholder:
            e.set_property("placeholder-text", placeholder)
    elif placeholder:
        e.set_placeholder_text(placeholder)
    e.add_css_class("fluent-entry")
    e.set_hexpand(True)
    return e


class _FileField(Gtk.Box):
    """A path with a Browse button (Gtk.FileDialog)."""

    def __init__(self, on_changed):
        super().__init__(spacing=8)
        self.entry = _entry(_("No file selected"))
        self.entry.connect("changed", lambda *_: on_changed())
        self.append(self.entry)
        self.append(button(_("Browse"), self._browse))

    def _browse(self):
        dlg = Gtk.FileDialog()

        def done(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            if f is not None and f.get_path():
                self.entry.set_text(f.get_path())
        dlg.open(self.get_root(), None, done)

    def get(self):
        return self.entry.get_text().strip()

    def set(self, path):
        self.entry.set_text(path or "")


class EnterpriseForm(Gtk.Box):
    """User name and password first (what Windows asks); the rest under "Advanced options",
    open when the saved settings are not the usual ones."""

    def __init__(self, values=None, on_changed=None, ssid=None, advanced=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._cb = on_changed or (lambda: None)
        self.ssid = ssid
        self.hint = ""
        self.user = _entry(_("User name"))
        self.password = _entry(_("Password"), password=True)
        self.append(self.user)
        self.append(self.password)
        self.toggle = link(_("Advanced options"), self._toggle)
        self.toggle.set_halign(Gtk.Align.START)
        self.append(self.toggle)
        self.adv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.adv.add_css_class("eap-advanced")
        cat = link(_("Use my institution's settings (eduroam)"), self._open_cat)
        cat.set_halign(Gtk.Align.START)
        self.adv.append(cat)
        self.cat_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.adv.append(self.cat_holder)
        self.method = Dropdown(METHODS, "peap", lambda _v: self._sync())
        self.phase2 = Dropdown(PHASE2["peap"], "mschapv2", lambda _v: self._cb())
        self.peapver = Dropdown([("", _("Automatic")), ("0", "0"), ("1", "1")], "", lambda _v: self._cb())
        self.ca = Dropdown([("none", _("Don't validate")), ("system", _("Use system certificates")),
                            ("file", _("From a file"))], "none", lambda _v: self._sync())
        self.ca_file = _FileField(self._cb)
        self.domain = _entry(_("e.g. radius.example.edu"))
        self.anonymous = _entry(_("e.g. anonymous@example.edu"))
        self.client_cert = _FileField(self._cb)
        self.private_key = _FileField(self._cb)
        self.key_password = _entry(_("Private key password"), password=True)
        self.rows = {}
        for key, title, w in (
                ("method", _("EAP method"), self.method),
                ("phase2", _("Phase 2 authentication"), self.phase2),
                ("peapver", _("PEAP version"), self.peapver),
                ("ca", _("CA certificate"), self.ca),
                ("ca_file", _("CA certificate file"), self.ca_file),
                ("domain", _("Domain"), self.domain),
                ("anonymous", _("Anonymous identity"), self.anonymous),
                ("client_cert", _("User certificate"), self.client_cert),
                ("private_key", _("Private key"), self.private_key),
                ("key_password", _("Private key password"), self.key_password)):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.append(label(title, "caption"))
            if isinstance(w, Dropdown):
                w.set_halign(Gtk.Align.FILL)
            box.append(w)
            self.rows[key] = box
            self.adv.append(box)
        self.note = label("", "caption", wrap=True)
        self.adv.append(self.note)
        self.append(self.adv)
        for e in (self.user, self.password, self.domain, self.anonymous, self.key_password):
            e.connect("changed", lambda *_: self._cb())
        self.set(values or DEFAULTS)
        if advanced is None:
            v = values or {}
            advanced = (v.get("method", "peap"), v.get("phase2", "mschapv2"), v.get("ca", "none")) != \
                ("peap", "mschapv2", "none") or bool(v.get("domain") or v.get("anonymous"))
        self.adv.set_visible(advanced)
        self._sync()

    def _open_cat(self):
        if self.cat_holder.get_first_child() is not None:
            return
        self.cat_holder.append(cat_panel(self, self._from_cat, self._close_cat))

    def _close_cat(self):
        while (c := self.cat_holder.get_first_child()) is not None:
            self.cat_holder.remove(c)

    def _toggle(self):
        self.adv.set_visible(not self.adv.get_visible())

    def _sync(self):
        m = self.method.selected_id()
        if m in PHASE2:
            cur = self.phase2.selected_id()
            self.phase2.set_options(PHASE2[m], cur if cur in dict(PHASE2[m]) else PHASE2[m][0][0])
        self.rows["phase2"].set_visible(m in PHASE2)
        self.rows["peapver"].set_visible(m == "peap")
        tunnelled = m in ("peap", "ttls", "fast", "tls")
        for k in ("ca", "domain"):
            self.rows[k].set_visible(tunnelled)
        self.rows["ca_file"].set_visible(tunnelled and self.ca.selected_id() == "file")
        self.rows["anonymous"].set_visible(m in ("peap", "ttls", "fast"))
        for k in ("client_cert", "private_key", "key_password"):
            self.rows[k].set_visible(m == "tls")
        self.password.set_visible(m not in PASSWORDLESS)
        self.note.set_text(_("Without a CA certificate the server is not checked: your password could reach a "
                             "network that only pretends to be this one.")
                           if tunnelled and self.ca.selected_id() == "none" else "")
        self.note.set_visible(bool(self.note.get_text()))
        self._cb()

    def set(self, v):
        self.method.select(v.get("method") or "peap")
        self._sync_phase2(v)
        self.peapver.select(v.get("peapver") or "")
        self.ca.select(v.get("ca") or "none")
        self.ca_file.set(v.get("ca_path"))
        self.domain.set_text(v.get("domain") or "")
        self.anonymous.set_text(v.get("anonymous") or "")
        self.client_cert.set(v.get("client_cert"))
        self.private_key.set(v.get("private_key"))
        if v.get("identity") is not None:
            self.user.set_text(v.get("identity") or "")

    def _sync_phase2(self, v):
        m = v.get("method") or "peap"
        if m in PHASE2:
            self.phase2.set_options(PHASE2[m], v.get("phase2") if v.get("phase2") in dict(PHASE2[m]) else PHASE2[m][0][0])

    def get(self):
        m = self.method.selected_id()
        return {"method": m, "phase2": self.phase2.selected_id() if m in PHASE2 else "",
                "peapver": self.peapver.selected_id() if m == "peap" else "",
                "ca": self.ca.selected_id(), "ca_path": self.ca_file.get(), "domain": self.domain.get_text().strip(),
                "anonymous": self.anonymous.get_text().strip() if m in ("peap", "ttls", "fast") else "",
                "client_cert": self.client_cert.get(), "private_key": self.private_key.get(),
                "key_password": self.key_password.get_text(),
                "identity": self.user.get_text().strip(), "password": self.password.get_text()}

    def valid(self, need_password=True):
        v = self.get()
        if not v["identity"]:
            return False
        if v["method"] == "tls":
            return bool(v["client_cert"] and v["private_key"])
        if v["ca"] == "file" and not v["ca_path"]:
            return False
        return bool(v["password"]) or not need_password

    def _from_cat(self, values, name):
        self.set(values)
        self.adv.set_visible(True)
        self._sync()
        self.hint = values.get("hint") or ""
        if self.hint and "@" not in self.user.get_text():
            self.user.set_placeholder_text(_("User name") + " (…@" + self.hint.lstrip("@") + ")")
        self._close_cat()
        toast(self, _("Settings of {0} applied").format(name))


def cat_panel(widget, on_done, on_close):
    """Inline (Settings shows one dialog at a time): country, institution, profile, then the
    profile's settings (the CA saved to a file)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.add_css_class("cat-panel")
    box.append(label(_("eduroam publishes the settings of each institution (eduroam CAT). Choose yours: you sign "
                       "in with the user name of your own institution."), "caption", wrap=True))
    status = Gtk.Box(spacing=8)
    spin = spinner()
    status.append(spin)
    msg = label(_("Loading the eduroam institutions…"), "caption", wrap=True)
    status.append(msg)
    box.append(status)
    country = Dropdown([("ES", "España")], "ES")
    country.set_halign(Gtk.Align.FILL)
    search = Gtk.SearchEntry()
    search.set_placeholder_text(_("Search your institution"))
    lst = Gtk.ListBox()
    lst.add_css_class("cat-list")
    sc = Gtk.ScrolledWindow()
    sc.set_min_content_height(220)
    sc.set_child(lst)
    prof = Dropdown([], None)
    prof.set_halign(Gtk.Align.FILL)
    prof_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    prof_box.append(label(_("Profile"), "caption"))
    prof_box.append(prof)
    prof_box.set_visible(False)
    apply_btn = button(_("Apply"), lambda: resp("primary"), accent=True, sensitive=False)
    foot = Gtk.Box(spacing=8, homogeneous=True)
    foot.set_halign(Gtk.Align.END)
    foot.append(apply_btn)
    foot.append(button(_("Close"), on_close))
    for w in (label(_("Country"), "caption"), country, search, sc, prof_box, foot):
        box.append(w)
    state = {"idps": [], "idp": None, "name": ""}

    def busy(text):
        spin.set_visible(bool(text))
        msg.set_text(text or "")
        status.set_visible(bool(text))

    def run(fn, done, fail_text):
        def work():
            try:
                res = fn()
            except Exception as e:  # noqa: BLE001 - network, parsing
                GLib.idle_add(lambda: (busy(None), toast(widget, fail_text), print("CAT:", e), False)[-1])
                return
            GLib.idle_add(lambda: (done(res), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def fill_list(*_a):
        q = search.get_text().lower()
        while (r := lst.get_first_child()) is not None:
            lst.remove(r)
        for idp, name in state["idps"]:
            if q in (name or "").lower():
                row = Gtk.ListBoxRow()
                row.set_child(label(name, None))
                row.idp, row.name = idp, name
                lst.append(row)

    def got_idps(idps):
        busy(None)
        state["idps"] = idps
        fill_list()

    def load_country(code):
        busy(_("Loading the eduroam institutions…"))
        run(lambda: eduroam_cat.institutions(code), got_idps, _("Couldn't reach eduroam CAT"))

    def got_countries(cs):
        country.set_options(cs, "ES")
        load_country(country.selected_id() or "ES")

    def picked(_l, row):
        if row is None:
            return
        state["idp"], state["name"] = row.idp, row.name
        busy(_("Loading profiles…"))

        def got(ps):
            busy(None)
            prof.set_options(ps, ps[0][0] if ps else None)
            prof_box.set_visible(len(ps) > 1)
            apply_btn.set_sensitive(bool(ps))
        run(lambda: eduroam_cat.profiles(row.idp), got, _("Couldn't reach eduroam CAT"))

    def resp(r):
        if r != "primary" or not prof.selected_id():
            return
        pid, name = prof.selected_id(), state["name"]

        def got(v):
            if v.get("ca_pem"):
                v["ca_path"] = eduroam_cat.save_ca(f"eduroam-{pid}", v["ca_pem"])
            on_done(v, name)
        run(lambda: eduroam_cat.settings(pid), got, _("This institution's settings couldn't be read"))

    country.connect("notify::selected", lambda *_: load_country(country.selected_id()))
    search.connect("search-changed", fill_list)
    lst.connect("row-activated", picked)
    lst.connect("row-selected", picked)
    run(lambda: eduroam_cat.countries(), got_countries, _("Couldn't reach eduroam CAT"))
    return box

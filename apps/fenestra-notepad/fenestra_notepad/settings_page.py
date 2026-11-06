"""Settings page (gear button): app theme, font, word wrap, formatting, opening files,
startup behaviour, recent files and About."""
from __future__ import annotations

from gi.repository import GLib, Gtk, Pango

from . import __version__, util
from .i18n import _
from .widgets import Dropdown, icon, label

FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
PREFERRED_FONTS = ["Consolas", "Cascadia Mono", "Cascadia Code", "Adwaita Mono", "DejaVu Sans Mono",
                   "Liberation Mono", "Noto Sans Mono", "Source Code Pro", "Fira Mono", "Ubuntu Mono"]


def _card(css="s-card"):
    b = Gtk.Box()
    b.add_css_class(css)
    return b


def _texts(title, subtitle=None):
    v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
    v.set_hexpand(True)
    v.append(label(title, "s-title"))
    if subtitle:
        v.append(label(subtitle, "s-sub", wrap=True))
    return v


class Toggle(Gtk.Box):
    """Fluent ToggleSwitch followed by its On/Off label."""
    __gtype_name__ = "FenestraNotepadToggle"

    def __init__(self, active, on_change):
        super().__init__(spacing=12, valign=Gtk.Align.CENTER)
        self.sw = Gtk.Switch()
        self.sw.add_css_class("fluent")
        self.sw.set_active(active)
        self.sw.set_valign(Gtk.Align.CENTER)
        self.lbl = label("", "s-onoff")
        self.append(self.sw)
        self.append(self.lbl)
        self._upd()
        self.sw.connect("notify::active", lambda *_: (self._upd(), on_change(self.sw.get_active())))

    def _upd(self):
        self.lbl.set_label(_("On") if self.sw.get_active() else _("Off"))


class Expander(Gtk.Box):
    """Settings expander card: header row (icon, title, subtitle, chevron) + revealed rows."""
    __gtype_name__ = "FenestraNotepadExpander"

    def __init__(self, icon_name, title, subtitle=None, trailing=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("s-expander")
        self.head = Gtk.Button()
        self.head.add_css_class("s-card")
        self.head.add_css_class("s-head")
        row = Gtk.Box()
        row.append(icon(icon_name, 20, "s-icon"))
        row.append(_texts(title, subtitle))
        if trailing is not None:
            trailing.set_valign(Gtk.Align.CENTER)
            row.append(trailing)
        self.chev = icon("np-chevron-down-symbolic", 12, "s-chevron")
        self.chev.set_valign(Gtk.Align.CENTER)
        row.append(self.chev)
        self.head.set_child(row)
        self.head.connect("clicked", lambda *_: self.set_expanded(not self.expanded))
        self.append(self.head)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body.add_css_class("s-body")
        self.rev = Gtk.Revealer()
        self.rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.rev.set_transition_duration(120)
        self.rev.set_child(self.body)
        self.append(self.rev)
        self.expanded = False

    def set_expanded(self, on, animate=True):
        self.expanded = on
        if not animate:
            d = self.rev.get_transition_duration()
            self.rev.set_transition_duration(0)
            self.rev.set_reveal_child(on)
            self.rev.set_transition_duration(d)
        else:
            self.rev.set_reveal_child(on)
        self.chev.set_from_icon_name("np-chevron-up-20-symbolic" if on else "np-chevron-down-symbolic")
        if on:
            self.add_css_class("open")
        else:
            self.remove_css_class("open")

    def add_row(self, w):
        r = Gtk.Box()
        r.add_css_class("s-subrow")
        if isinstance(w, Gtk.CheckButton):
            r.add_css_class("s-radiorow")
        r.append(w)
        self.body.append(r)
        return r


class SettingsPage(Gtk.ScrolledWindow):
    __gtype_name__ = "FenestraNotepadSettings"

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.add_css_class("settings-page")
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        s = util.settings()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.add_css_class("s-outer")
        outer.append(label(_("Settings"), "s-page-title"))
        self.cols = Gtk.Box()
        self.cols.add_css_class("s-cols")
        outer.append(self.cols)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        left.add_css_class("s-left")
        self.cols.append(left)

        # ---------------------------------------------------------------- appearance
        left.append(label(_("Appearance"), "s-section"))
        self.theme_exp = Expander("np-palette-symbolic", _("App theme"), _("Select which app theme to display"))
        self.theme_radios = {}
        group = None
        for val, text in (("light", _("Light")), ("dark", _("Dark")), ("system", _("Use system setting"))):
            rb = Gtk.CheckButton(label=text)
            rb.add_css_class("fluent")
            if group is not None:
                rb.set_group(group)
            group = group or rb
            rb.set_active(s["theme"] == val)
            rb.connect("toggled", lambda b, v=val: b.get_active() and s.set("theme", v))
            self.theme_radios[val] = rb
            self.theme_exp.add_row(rb)
        left.append(self.theme_exp)

        # ---------------------------------------------------------------- text formatting
        left.append(label(_("Text Formatting"), "s-section"))
        self.font_exp = Expander("np-font-symbolic", _("Font"))
        fams = self._font_families()
        self.family = Dropdown([(f, f) for f in fams], s["font_family"],
                               lambda v: s.set("font_family", v))
        self.style = Dropdown([("regular", _("Regular")), ("italic", _("Italic")), ("bold", _("Bold")),
                               ("bold-italic", _("Bold Italic"))], s["font_style"],
                              lambda v: s.set("font_style", v))
        self.size = Dropdown([(n, str(n)) for n in FONT_SIZES], s["font_size"],
                             lambda v: s.set("font_size", v))
        for title, dd in ((_("Family"), self.family), (_("Style"), self.style), (_("Size"), self.size)):
            row = Gtk.Box()
            row.append(_texts(title))
            dd.set_valign(Gtk.Align.CENTER)
            dd.set_hexpand(False)
            dd.set_size_request(200, -1)
            row.append(dd)
            row.set_hexpand(True)
            self.font_exp.add_row(row)
        self.preview = label(_("The quick brown fox jumps over the lazy dog."), "s-preview")
        self.preview.set_hexpand(True)
        self.font_exp.add_row(self.preview)
        self._update_preview()
        left.append(self.font_exp)

        left.append(self._row("np-wrap-symbolic", _("Word wrap"), _("Fit text within window by default"),
                              Toggle(s["word_wrap"], lambda v: s.set("word_wrap", v))))
        left.append(self._row("np-format-symbolic", _("Formatting"), None,
                              Toggle(s["formatting"], lambda v: s.set("formatting", v))))

        # ---------------------------------------------------------------- opening
        left.append(label(_("Opening Notepad"), "s-section"))
        self.open_in = Dropdown([("tab", _("Open in a new tab")), ("window", _("Open in a new window"))],
                                s["open_in"], lambda v: s.set("open_in", v))
        left.append(self._row("np-open-symbolic", _("Opening files"), _("Choose where your files are opened"),
                              self.open_in))
        self.start_exp = Expander("np-window-symbolic", _("When Notepad starts"))
        group = None
        for val, text in (("continue", _("Continue previous session")),
                          ("new", _("Start new session and discard unsaved changes"))):
            rb = Gtk.CheckButton(label=text)
            rb.add_css_class("fluent")
            if group is not None:
                rb.set_group(group)
            group = group or rb
            rb.set_active(s["startup"] == val)
            rb.connect("toggled", lambda b, v=val: b.get_active() and s.set("startup", v))
            self.start_exp.add_row(rb)
        left.append(self.start_exp)
        self.recent_toggle = Toggle(s["recent_enabled"], self._recent)
        left.append(self._row("np-history-symbolic", _("Recent Files"), None, self.recent_toggle))

        # ---------------------------------------------------------------- about
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right.add_css_class("s-about")
        right.append(label(_("About this app"), "s-about-title"))
        right.append(label(_("Fenestra Notepad") + " " + __version__, "s-about-text"))
        right.append(label(_("Part of Fenestra. Free software."), "s-about-text"))
        right.append(self._link(_("Project website"), util.PROJECT_URL))
        right.append(self._link(_("Source code and licence"), util.PROJECT_URL + "/tree/main/apps/fenestra-notepad"))
        b1 = Gtk.Button(label=_("Send feedback"))
        b1.add_css_class("std-button")
        b1.add_css_class("s-about-btn")
        b1.set_halign(Gtk.Align.START)
        b1.connect("clicked", lambda *_: self._open_uri(util.PROJECT_URL + "/issues"))
        b2 = Gtk.Button(label=_("Help"))
        b2.add_css_class("std-button")
        b2.add_css_class("s-about-btn")
        b2.set_halign(Gtk.Align.START)
        b2.connect("clicked", lambda *_: self._open_uri(util.PROJECT_URL + "/tree/main/apps/fenestra-notepad#readme"))
        right.append(b1)
        right.append(b2)
        self.right = right
        self.cols.append(right)
        self.set_child(outer)
        s.listeners.append(self._on_setting)
        self.connect("destroy", lambda *_: s.listeners.remove(self._on_setting)
                     if self._on_setting in s.listeners else None)

    def _font_families(self):
        try:
            fams = sorted({f.get_name() for f in self.get_pango_context().list_families()}, key=str.lower)
        except Exception:  # noqa: BLE001
            fams = []
        cur = util.settings()["font_family"]
        pref = [f for f in PREFERRED_FONTS if f in fams]
        out = pref + [f for f in fams if f not in pref]
        if cur not in out:
            out.insert(0, cur)
        return out

    def _row(self, icon_name, title, subtitle, trailing):
        c = _card()
        c.add_css_class("s-row")
        c.append(icon(icon_name, 20, "s-icon"))
        c.append(_texts(title, subtitle))
        trailing.set_valign(Gtk.Align.CENTER)
        trailing.set_hexpand(False)
        c.append(trailing)
        return c

    def _link(self, text, uri):
        b = Gtk.Button(label=text)
        b.add_css_class("s-link")
        b.set_halign(Gtk.Align.START)
        b.set_tooltip_text(uri)
        b.connect("clicked", lambda *_: self._open_uri(uri))
        return b

    def _open_uri(self, uri):
        if util.DEMO:
            return
        Gtk.UriLauncher.new(uri).launch(self.get_root(), None, None, None)

    def _recent(self, on):
        s = util.settings()
        s.set("recent_enabled", on)
        if not on:
            s.set("recent", [])

    def _update_preview(self):
        s = util.settings()
        fd = Pango.FontDescription.from_string(s["font_family"])
        fd.set_size(int(s["font_size"] * Pango.SCALE))
        if "bold" in s["font_style"]:
            fd.set_weight(Pango.Weight.BOLD)
        if "italic" in s["font_style"]:
            fd.set_style(Pango.Style.ITALIC)
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_font_desc_new(fd))
        self.preview.set_attributes(attrs)

    def _on_setting(self, key):
        s = util.settings()
        if key == "theme":
            rb = self.theme_radios.get(s["theme"])
            if rb is not None and not rb.get_active():
                rb.set_active(True)
        if key.startswith("font_"):
            self.family.set_value(s["font_family"])
            self.style.set_value(s["font_style"])
            self.size.set_value(s["font_size"])
            self._update_preview()

    def show_font(self):
        self.font_exp.set_expanded(True, animate=False)
        GLib.idle_add(lambda: (self.font_exp.head.grab_focus(), False)[1], priority=GLib.PRIORITY_DEFAULT)

    def set_narrow(self, narrow):
        self.cols.set_orientation(Gtk.Orientation.VERTICAL if narrow else Gtk.Orientation.HORIZONTAL)
        if narrow:
            self.right.add_css_class("narrow")
        else:
            self.right.remove_css_class("narrow")

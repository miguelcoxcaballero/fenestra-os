"""Country/region and keyboard layout pages."""

from ..backends import locale as loc
from ..i18n import _
from ..widgets.controls import ListPicker
from .base import Page


class RegionPage(Page):
    page_id = "region"
    illustration = "region"
    can_go_back = False

    def __init__(self, ctx):
        super().__init__(ctx, _("Is this the right country or region?"))
        self.primary_label = _("Yes")
        self.countries = loc.load_countries(self.state.ui_lang)
        items = [(c.code, c.label) for c in self.countries]
        self.picker = ListPicker(items, selected=self.state.country)
        self.picker.connect("activated", lambda *_: self.on_primary())
        self.picker.connect("changed", lambda *_: self.set_primary_sensitive(True))
        self.body.append(self.picker)

    def focus_widget(self):
        return self.picker.listbox.get_selected_row() or self.picker.listbox

    def on_primary(self):
        cc = self.picker.get_selected()
        if not cc:
            return
        st = self.state
        st.country = cc
        st.timezone = loc.timezone_for_country(cc, self.ctx.initial_timezone)
        st.formats = loc.formats_for_country(cc, loc.language_of(st.lang_locale), self.ctx.locales)
        self.ctx.keyboard_suggestion = loc.keyboard_for_country(cc, self.ctx.layouts)
        self.ctx.next()


def _layout_items(layouts):
    return [(l.id, l.label) for l in layouts]


def _parse_id(layout_id: str) -> tuple[str, str]:
    layout, _, variant = layout_id.partition("+")
    return layout, variant


class KeyboardPage(Page):
    page_id = "keyboard"
    illustration = "keyboard"

    def __init__(self, ctx):
        super().__init__(ctx, _("Is this the right keyboard layout or input method?"),
                         _("If you also use another keyboard layout, you can add that next."))
        self.primary_label = _("Yes")
        self.picker = ListPicker(_layout_items(ctx.layouts), selected=self._suggested())
        self.picker.connect("activated", lambda *_: self.on_primary())
        self.body.append(self.picker)
        self._last_suggestion = self._suggested()

    def _suggested(self):
        layout, variant = self.ctx.keyboard_suggestion
        return f"{layout}+{variant}" if variant else layout

    def focus_widget(self):
        return self.picker.listbox.get_selected_row() or self.picker.listbox

    def on_enter(self, direction):
        sugg = self._suggested()
        if sugg != self._last_suggestion:
            # Rebuild so the new suggestion is pinned at the top again.
            self._last_suggestion = sugg
            self.body.remove(self.picker)
            self.picker = ListPicker(_layout_items(self.ctx.layouts), selected=sugg)
            self.picker.connect("activated", lambda *_: self.on_primary())
            self.body.append(self.picker)

    def on_primary(self):
        sel = self.picker.get_selected()
        if not sel:
            return
        self.state.layouts = [_parse_id(sel)]
        self.ctx.set_session_keyboard(self.state.layouts)
        self.ctx.next()


class SecondKeyboardPage(Page):
    page_id = "keyboard-second"
    illustration = "keyboard"

    def __init__(self, ctx):
        super().__init__(ctx, _("Want to add a second keyboard layout?"))
        self.primary_label = _("Add layout")
        self.secondary_label = _("Skip")

    def on_enter(self, direction):
        # Coming back from the picker: forget a previously added layout.
        if len(self.state.layouts) > 1:
            self.state.layouts = self.state.layouts[:1]

    def on_primary(self):
        self.ctx.goto("keyboard-pick")

    def on_secondary(self):
        self.ctx.next()


class PickSecondKeyboardPage(Page):
    page_id = "keyboard-pick"
    illustration = "keyboard"
    branch = True

    def __init__(self, ctx):
        super().__init__(ctx, _("Choose a second keyboard layout"))
        self.primary_label = _("Add layout")
        self.picker = ListPicker(_layout_items(ctx.layouts), selected=None, pin_selected=False)
        self.picker.connect("changed", lambda *_: self.set_primary_sensitive(True))
        self.picker.connect("activated", lambda *_: self.on_primary())
        self.body.append(self.picker)
        self.primary_sensitive = False

    def focus_widget(self):
        return self.picker.listbox

    def on_primary(self):
        sel = self.picker.get_selected()
        if not sel:
            return
        first = self.state.layouts[0]
        second = _parse_id(sel)
        self.state.layouts = [first] if second == first else [first, second]
        self.ctx.set_session_keyboard(self.state.layouts)
        self.ctx.next()

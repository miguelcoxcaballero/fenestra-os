"""Gaming."""
from __future__ import annotations

from .. import util
from ..i18n import _
from ..widgets import SettingRow, ToggleSwitch, label, toast
from .base import Page, register
from .common import infobar


@register
class GamingPage(Page):
    id = "gaming"
    title = "Gaming"
    keywords = "game mode performance steam controller"
    index = [("gamemode", "Game Mode", "feral gamemoded performance")]

    def build(self, box):
        g = self.group()
        if util.have("gamemoded"):
            self.gm = SettingRow(_("Game Mode"),
                                 _("Optimize your PC for play by applying performance tweaks while games run"),
                                 "fs-xbox-controller-symbolic", key="gamemode")
            self.remember("gamemode", self.gm)
            g.add(self.gm)
            util.run_async(["systemctl", "--user", "is-enabled", "gamemoded.service"], self._state)
        else:
            r = SettingRow(_("Game Mode"), _("Install the \"gamemode\" package to enable performance tweaks for games"),
                           "fs-xbox-controller-symbolic", control=label(_("Not installed"), "row-value"),
                           key="gamemode")
            self.remember("gamemode", r)
            g.add(r)
        g2 = self.group(_("Related"))
        for cmd, title, sub in (("steam", _("Steam"), _("Open your game library")),
                                ("lutris", _("Lutris"), _("Manage games from other stores")),
                                ("protonup-qt", _("ProtonUp-Qt"), _("Install compatibility tools"))):
            if util.have(cmd):
                self.ext_row(g2, title, sub, "fs-games-symbolic", [cmd])
        self.ext_row(g2, _("Controllers"), _("Bluetooth and USB game controllers"), "fs-xbox-controller-symbolic",
                     ["gnome-control-center", "bluetooth"])
        g2.add(SettingRow(_("Graphics"), _("GPU and display settings"), "fs-desktop-symbolic", chevron=True,
                          on_click=lambda: self.go("display")))
        box.append(infobar(_("Games run inside Game Mode automatically when they request it (for example with "
                             "\"gamemoderun %command%\" in Steam launch options)."), None))

    def _state(self, ok, out, _e):
        st = out.strip()
        if st in ("enabled", "static", "indirect", "alias"):
            active = True
        else:
            active = False

        def set_(v):
            util.run_async(["systemctl", "--user", "enable" if v else "disable", "--now", "gamemoded.service"],
                           lambda o, *_: o or toast(self.box, _("This action is disabled in read-only mode")
                                                    if util.READ_ONLY else _("The change was not applied")),
                           mutating=True)
        self.gm.set_control(ToggleSwitch(active, set_))

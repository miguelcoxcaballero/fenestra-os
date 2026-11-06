"""System › Storage."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..backends import storage
from ..i18n import _
from ..widgets import (ContentDialog, SettingRow, label, progress, show_dialog, spinner,
                       toast, value_label)
from .base import Page, register
from .common import gsetting_toggle

PRIVACY = "org.gnome.desktop.privacy"


@register
class StoragePage(Page):
    id = "storage"
    parent = "system"
    title = "Storage"
    keywords = "disk space drive free cleanup temporary files trash cache"
    index = [
        ("temp", "Temporary files", "trash cache thumbnails cleanup delete"),
        ("sense", "Storage Sense", "automatic cleanup trash"),
        ("drives", "Disks & volumes", "partition mount drive"),
    ]

    CATS = [
        ("temp", "Temporary files", "fs-delete-symbolic"),
        ("documents", "Documents", "fs-document-symbolic"),
        ("pictures", "Pictures", "fs-image-symbolic"),
        ("videos", "Videos", "fs-video-symbolic"),
        ("music", "Music", "fs-music-note-2-symbolic"),
        ("downloads", "Downloads", "fs-arrow-download-symbolic"),
        ("apps_system", "Installed apps (Flatpak)", "fs-apps-symbolic"),
    ]

    def build(self, box):
        vols = storage.volumes()
        main = vols[0] if vols else None
        g = self.group(_("Local disk") + (f" ({main.mount})" if main else ""))
        if main:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.add_css_class("card")
            card.add_css_class("padded")
            top = Gtk.Box()
            top.append(label(_("{0} used").format(util.human_size(main.used)), "body-strong"))
            sp = Gtk.Box(hexpand=True)
            top.append(sp)
            top.append(label(_("{0} free").format(util.human_size(main.free)), "caption"))
            card.append(top)
            card.append(progress(main.fraction, "usage" + (" warn" if main.fraction > 0.9 else "")))
            g.add(card)
        self.cat_rows = {}
        for key, t, ic in self.CATS:
            r = SettingRow(_(t), _("Calculating…"), ic, control=None, key=key,
                           chevron=key == "temp",
                           on_click=(self._temp_dialog if key == "temp" else None))
            pb = progress(0.0, "usage")
            pb.set_size_request(160, -1)
            r.set_control(pb)
            self.cat_rows[key] = (r, pb)
            if key == "temp":
                self.remember("temp", r)
            g.add(r)
        self.total_for_bars = main.used if main else 1

        g2 = self.group(_("Storage management"))
        sense = gsetting_toggle(PRIVACY, "remove-old-trash-files")
        if sense:
            r = SettingRow(_("Storage Sense"),
                           _("Automatically free up space, delete temporary files, and manage locally "
                             "available cloud content"), "fs-hard-drive-symbolic", control=sense, key="sense")
            self.remember("sense", r)
            g2.add(r)
        if util.has_key(PRIVACY, "old-files-age"):
            g2.add(SettingRow(_("Delete files in my trash if they have been there for over"), None,
                              "fs-delete-symbolic",
                              control=value_label(_("{0} days").format(util.gget(PRIVACY, "old-files-age", 30))),
                              key="old-files-age"))
        dr = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for v in vols:
            r = SettingRow(v.label, f"{util.human_size(v.free)} " + _("free of") + f" {util.human_size(v.total)}"
                           + f" · {v.fstype}", "fs-hard-drive-symbolic")
            pb = progress(v.fraction, "usage" + (" warn" if v.fraction > 0.9 else ""))
            pb.set_size_request(160, -1)
            r.set_control(pb)
            dr.append(r)
        g3 = self.group(_("Disks & volumes"))
        g3.key = "drives"
        self._rows["drives"] = g3
        g3.add(dr)
        self.ext_row(g3, _("Disks"), _("Partitions, formatting and SMART data"), "fs-hard-drive-symbolic",
                     ["gnome-disks"])
        self.ext_row(g3, _("Disk usage analyzer"), _("See which folders use the most space"),
                     "fs-data-usage-symbolic", ["baobab"])
        storage.categories(self._got_cats)

    def _got_cats(self, sizes):
        total = max(self.total_for_bars, 1)
        for key, (row, pb) in self.cat_rows.items():
            n = sizes.get(key, 0)
            if key == "apps_system":
                n += sizes.get("apps_user", 0)
            row.set_subtitle(util.human_size(n))
            pb.set_fraction(min(1.0, n / total))

    def _temp_dialog(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        cb_trash = Gtk.CheckButton(label=_("Trash"))
        cb_trash.set_active(True)
        cb_thumbs = Gtk.CheckButton(label=_("Thumbnail cache"))
        cb_thumbs.set_active(True)
        box.append(cb_trash)
        box.append(cb_thumbs)
        sizes = label(_("Calculating…"), "caption")
        box.append(sizes)
        storage.dir_size(storage.trash_dir(), lambda n: cb_trash.set_label(
            _("Trash") + f" ({util.human_size(n)})"))
        storage.dir_size(storage.thumbnails_dir(), lambda n: cb_thumbs.set_label(
            _("Thumbnail cache") + f" ({util.human_size(n)})"))
        sizes.set_label(_("Files in the trash are deleted permanently."))

        def resp(r):
            if r != "primary":
                return
            if util.READ_ONLY:
                toast(self.box, _("This action is disabled in read-only mode"))
                return
            row, _pb = self.cat_rows["temp"]
            sp = spinner()
            row.set_control(sp)

            def done(ok):
                toast(self.box, _("Temporary files removed") if ok else _("Some files could not be removed"))
                storage.categories(self._got_cats)
                pb = progress(0.0, "usage")
                pb.set_size_request(160, -1)
                row.set_control(pb)
                self.cat_rows["temp"] = (row, pb)
            storage.clean_temp(cb_trash.get_active(), cb_thumbs.get_active(), done)
        dlg = ContentDialog(_("Remove temporary files?"), None, primary=_("Remove files"),
                            close=_("Cancel"), on_response=resp, extra=box)
        show_dialog(self.box, dlg)


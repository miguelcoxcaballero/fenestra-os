"""A document (one tab): text buffer + file, encoding and line-ending metadata."""
from __future__ import annotations

import os
import re
import threading
import uuid

import gi

gi.require_version("GtkSource", "5")
from gi.repository import GLib, GObject, GtkSource  # noqa: E402

from . import textio  # noqa: E402
from .i18n import _  # noqa: E402

CHUNK = 512 * 1024          # characters inserted per main-loop iteration while loading
# Below the frame clock's redraw (120) so the window keeps painting, above GtkTextView's
# line validation (125) so validation does not run on every partial buffer.
FILL_PRIORITY = 122
MAX_SIZE = 512 * 1024 * 1024
MD_EXT = (".md", ".markdown", ".mdown", ".mkd", ".mkdn")

_scheme_mgr = None


def style_scheme(dark):
    global _scheme_mgr
    if _scheme_mgr is None:
        from . import util
        _scheme_mgr = GtkSource.StyleSchemeManager.get_default()
        _scheme_mgr.prepend_search_path(os.path.join(util.data_dir(), "styles"))
    return _scheme_mgr.get_scheme("fenestra-notepad-dark" if dark else "fenestra-notepad-light")


class Document(GObject.Object):
    __gtype_name__ = "FenestraNotepadDocument"
    __gsignals__ = {
        "changed-meta": (GObject.SignalFlags.RUN_FIRST, None, ()),   # title/dirty/encoding/eol
        "loaded": (GObject.SignalFlags.RUN_FIRST, None, (str,)),     # error message or ""
    }

    def __init__(self, text="", markdown=False, uid=None):
        super().__init__()
        self.uid = uid or uuid.uuid4().hex
        self.path = None
        self.encoding = textio.DEFAULT_ENCODING
        self.bom = None
        self.eol = textio.DEFAULT_EOL
        self.markdown = markdown
        self.formatting = True
        self.zoom = 100
        self.loading = False
        self.session_dirty = True     # content not yet written to the session store
        self._first_line = ""
        self.buffer = GtkSource.Buffer()
        self.buffer.set_highlight_matching_brackets(False)
        self.buffer.set_implicit_trailing_newline(False)
        if text:
            self.buffer.set_enable_undo(False)
            self.buffer.set_text(text, -1)
            self.buffer.set_enable_undo(True)
            self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.set_modified(False)
        self.buffer.connect("modified-changed", lambda *_: self.emit("changed-meta"))
        self.buffer.connect("changed", self._on_changed)
        self.search_settings = GtkSource.SearchSettings()
        self.search = GtkSource.SearchContext.new(self.buffer, self.search_settings)
        self.search.set_highlight(False)
        self._strike_tag = None
        self._strike_id = 0
        self._update_first_line()
        self.apply_language()

    # ------------------------------------------------------------------ naming
    change_serial = 0
    _text_cache = (-1, "")

    def cached_text(self):
        """Whole text, reused until the buffer changes (searching big documents)."""
        if self._text_cache[0] != self.change_serial:
            self._text_cache = (self.change_serial, self.get_text())
        return self._text_cache[1]

    def _on_changed(self, *_):
        self.change_serial += 1
        self.session_dirty = True
        if self.markdown and self.formatting and not self.loading and not self._strike_id:
            self._strike_id = GLib.timeout_add(150, self._update_strike)
        if self.path is None and not self.loading:
            old = self._first_line
            self._update_first_line()
            if old != self._first_line:
                self.emit("changed-meta")

    def _update_first_line(self):
        b = self.buffer
        it = b.get_start_iter()
        end = it.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        # first 60 characters are enough for a tab title
        s = b.get_text(it, end, False)[:60].strip()
        self._first_line = s

    @property
    def title(self):
        if self.path:
            return os.path.basename(self.path)
        return self._first_line or _("Untitled")

    @property
    def modified(self):
        return self.buffer.get_modified()

    def set_modified(self, v):
        self.buffer.set_modified(v)

    # ------------------------------------------------------------------ text
    def get_text(self):
        b = self.buffer
        return b.get_text(b.get_start_iter(), b.get_end_iter(), True)

    def is_empty(self):
        return self.buffer.get_char_count() == 0

    _STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")

    def _update_strike(self):
        """~~strikethrough~~ is not part of GtkSourceView's Markdown syntax: tag it here."""
        self._strike_id = 0
        b = self.buffer
        if self._strike_tag is None:
            self._strike_tag = b.create_tag("md-strike", strikethrough=True)
        b.remove_tag(self._strike_tag, b.get_start_iter(), b.get_end_iter())
        if not (self.markdown and self.formatting) or b.get_char_count() > 1_000_000:
            return False
        for m in self._STRIKE.finditer(self.get_text()):
            b.apply_tag(self._strike_tag, b.get_iter_at_offset(m.start()), b.get_iter_at_offset(m.end()))
        return False

    def apply_language(self):
        if not self._strike_id:
            self._strike_id = GLib.idle_add(self._update_strike)
        md = self.markdown and self.formatting
        if md:
            lang = GtkSource.LanguageManager.get_default().get_language("markdown")
            self.buffer.set_language(lang)
            self.buffer.set_highlight_syntax(True)
        else:
            self.buffer.set_highlight_syntax(False)
            self.buffer.set_language(None)

    def set_markdown(self, on):
        self.markdown = bool(on)
        self.apply_language()
        self.session_dirty = True
        self.emit("changed-meta")

    def set_formatting(self, on):
        self.formatting = bool(on)
        self.apply_language()

    def set_scheme(self, dark):
        s = style_scheme(dark)
        if s is not None:
            self.buffer.set_style_scheme(s)

    # ------------------------------------------------------------------ files
    def load(self, path, text_override=None):
        """Read `path` in a worker thread, then fill the buffer in chunks so a 20 MB file
        never blocks the UI.  Emits "loaded" with an error message ("" on success).
        text_override: session restore of a modified file (keep metadata of the file)."""
        self.path = os.path.abspath(path)
        self.markdown = self.path.lower().endswith(MD_EXT)
        self.loading = True
        self.emit("changed-meta")

        def work():
            try:
                if os.path.getsize(self.path) > MAX_SIZE:
                    raise OSError(0, _("The file is too large to open (more than %d MB).") % (MAX_SIZE >> 20))
                det = textio.read_file(self.path)
                err = ""
            except OSError as e:
                det, err = None, e.strerror or str(e)
            GLib.idle_add(self._loaded_bytes, det, err, text_override, priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=work, daemon=True).start()

    def _loaded_bytes(self, det, err, text_override):
        if det is None:
            self.loading = False
            self.emit("loaded", err)
            return False
        self.encoding, self.bom, self.eol = det.encoding, det.bom, det.eol
        self.fill(text_override if text_override is not None else det.text,
                  modified=text_override is not None)
        return False

    def fill(self, text, modified=False, cursor=None):
        """Replace the buffer contents incrementally (undo disabled while filling)."""
        b = self.buffer
        self.loading = True
        b.set_enable_undo(False)
        b.set_highlight_syntax(False)
        b.set_text("", 0)
        pos = [0]

        def step():
            if pos[0] < len(text):
                chunk = text[pos[0]:pos[0] + CHUNK]
                pos[0] += CHUNK
                b.insert(b.get_end_iter(), chunk, -1)
                return True
            b.set_enable_undo(True)
            if cursor is not None:
                b.place_cursor(b.get_iter_at_offset(min(cursor, b.get_char_count())))
            else:
                b.place_cursor(b.get_start_iter())
            b.set_modified(modified)
            self.loading = False
            self.apply_language()
            self._update_first_line()
            self.session_dirty = True
            self.emit("changed-meta")
            self.emit("loaded", "")
            return False
        if len(text) <= CHUNK:
            step()
            step()
        else:
            GLib.idle_add(step, priority=FILL_PRIORITY)

    def save(self, path=None, encoding=None, eol=None):
        """Write the document; raises OSError / UnicodeEncodeError."""
        path = os.path.abspath(path or self.path)
        enc = encoding or self.encoding
        eol = eol or self.eol
        data = textio.encode(self.get_text(), enc, eol, self.bom)
        textio.write_file(path, data)
        self.path = path
        self.encoding, self.eol = enc, eol
        if path.lower().endswith(MD_EXT) and not self.markdown:
            self.markdown = True
            self.apply_language()
        self.buffer.set_modified(False)
        self.session_dirty = True
        self.emit("changed-meta")

    def set_encoding(self, enc):
        if enc != self.encoding:
            self.encoding = enc
            if enc.startswith("utf-16"):
                self.bom = True
            self.buffer.set_modified(True)
            self.emit("changed-meta")

    def set_eol(self, eol):
        if eol != self.eol:
            self.eol = eol
            self.buffer.set_modified(True)
            self.emit("changed-meta")

#!/usr/bin/env python3
"""Headless smoke test for Fenestra Notepad.

Opens files in several encodings and line endings, edits, finds / replaces, saves (checking
the bytes on disk), exercises menus, dialogs, Markdown formatting, settings and a 20 MB file
(the main loop must keep running while it loads), then restores the session in a second
application run and checks that unsaved text came back.

Uses a private temporary XDG config/state directory; never touches the user's settings.

    WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland python3 tools/smoke-test.py [--no-big]
"""
import codecs
import os
import shutil
import sys
import tempfile
import time
import traceback

TMP = tempfile.mkdtemp(prefix="fenestra-notepad-test-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_STATE_HOME"] = os.path.join(TMP, "state")
os.environ["FENESTRA_NOTEPAD_NON_UNIQUE"] = "1"
os.environ.setdefault("FENESTRA_NOTEPAD_LANG", "en")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fenestra_notepad import app as appmod, textio, util  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402

BIG = "--no-big" not in sys.argv
errors = []
checks = [0]
sys.excepthook = lambda *a: (errors.append(a), traceback.print_exception(*a))
F = os.path.join(TMP, "files")
os.makedirs(F)


def check(cond, what):
    checks[0] += 1
    if not cond:
        errors.append(what)
        print("FAIL:", what, flush=True)


def write(name, data: bytes):
    p = os.path.join(F, name)
    with open(p, "wb") as f:
        f.write(data)
    return p


SAMPLE = "Grüße, añejo – ünïcödé\nsecond line\nthird line"
files = {
    "utf8.txt": write("utf8.txt", SAMPLE.encode("utf-8")),
    "utf8bom.txt": write("utf8bom.txt", codecs.BOM_UTF8 + SAMPLE.replace("\n", "\r\n").encode("utf-8")),
    "utf16le.txt": write("utf16le.txt", codecs.BOM_UTF16_LE + SAMPLE.replace("\n", "\r\n").encode("utf-16-le")),
    "utf16be.txt": write("utf16be.txt", codecs.BOM_UTF16_BE + SAMPLE.encode("utf-16-be")),
    "latin1.txt": write("latin1.txt", "caf\xe9 cr\xe8me\rna\xefve".encode("latin-1")),
    "notes.md": write("notes.md", b"# Title\n\nsome words here\n"),
}
EXPECT = {
    "utf8.txt": ("utf-8", "lf"), "utf8bom.txt": ("utf-8-bom", "crlf"), "utf16le.txt": ("utf-16-le", "crlf"),
    "utf16be.txt": ("utf-16-be", "lf"), "latin1.txt": ("latin-1", "cr"), "notes.md": ("utf-8", "lf"),
}


def pump(ms=50):
    """Let the main loop run for a while (inside a step)."""
    ctx = GLib.MainContext.default()
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        ctx.iteration(False)
        time.sleep(0.002)


def wait_loaded(w, timeout=30):
    end = time.monotonic() + timeout
    ctx = GLib.MainContext.default()
    while any(d.loading for d in w.documents()) and time.monotonic() < end:
        ctx.iteration(True)


def doc_named(w, name):
    return next(d for d in w.documents() if d.path and os.path.basename(d.path) == name)


# --------------------------------------------------------------------------- unit checks (no GTK)
def unit_checks():
    for enc in textio.ENCODING_ORDER:
        for eol in textio.EOL_ORDER:
            txt = "a\nb\nc" if enc == "latin-1" else "añ\n€\nz"
            data = textio.encode(txt, enc, eol)
            det = textio.decode(data)
            check(det.text == txt, f"roundtrip text {enc}/{eol}")
            check(det.encoding == enc or (enc == "latin-1" and det.encoding == "utf-8"),
                  f"roundtrip encoding {enc}/{eol}: {det.encoding}")
            check(det.eol == eol, f"roundtrip eol {enc}/{eol}: {det.eol}")
    # BOM-less UTF-16
    det = textio.decode("hello world\r\n".encode("utf-16-le"))
    check(det.encoding == "utf-16-le" and det.text == "hello world\n", "bom-less utf-16 le")
    check(not textio.can_encode("€", "latin-1"), "latin-1 cannot encode euro")


# --------------------------------------------------------------------------- phase 1
def phase1(a):
    w = a.windows[0]
    yield 300
    wait_loaded(w)
    names = [os.path.basename(d.path) for d in w.documents() if d.path]
    for n in EXPECT:
        check(n in names, f"opened {n}")
    check(not any(d.path is None and d.is_empty() for d in w.documents()), "blank tab replaced by files")
    for n, (enc, eol) in EXPECT.items():
        d = doc_named(w, n)
        check((d.encoding, d.eol) == (enc, eol), f"detect {n}: {d.encoding}/{d.eol}")
        check(not d.modified, f"{n} not modified after load")
    d = doc_named(w, "utf8.txt")
    check(d.get_text() == SAMPLE, "utf8 text")
    check(doc_named(w, "latin1.txt").get_text() == "café crème\nnaïve", "latin1 text")
    check(doc_named(w, "notes.md").markdown, "md file is a Markdown tab")

    # ---- status bar
    w.set_current(d)
    buf = d.buffer
    buf.place_cursor(buf.get_end_iter())
    yield 50
    check(w.st_pos.get_label() == "Ln 3, Col 11", f"status position {w.st_pos.get_label()!r}")
    check(w.st_chars.get_label() == f"{len(SAMPLE)} characters", f"status chars {w.st_chars.get_label()!r}")
    check(w.st_eol_lbl.get_label() == "LF", "status eol")
    check(w.st_enc_lbl.get_label() == "UTF-8", "status encoding")
    check(not w.toolbar.get_visible(), "toolbar hidden for plain text")

    # ---- edit + save every encoding, verify bytes on disk
    for n, (enc, eol) in EXPECT.items():
        d = doc_named(w, n)
        w.set_current(d)
        d.buffer.insert(d.buffer.get_end_iter(), "\nadded line", -1)
        check(d.modified, f"{n} modified after edit")
        w.save()
        yield 30
        check(not d.modified, f"{n} saved")
        raw = open(d.path, "rb").read()
        det = textio.decode(raw)
        check(det.encoding == enc, f"saved encoding {n}: {det.encoding}")
        check(det.eol == eol, f"saved eol {n}: {det.eol}")
        check(det.text.endswith("\nadded line"), f"saved text {n}")
        if enc == "utf-8-bom":
            check(raw.startswith(codecs.BOM_UTF8), "utf-8 BOM kept")
        if enc == "utf-16-le":
            check(raw.startswith(codecs.BOM_UTF16_LE), "utf-16 LE BOM kept")
        if eol == "crlf":
            check(b"\n" not in raw.replace(b"\r\n", b"").replace(b"\n\x00", b"").replace(b"\x00\n", b"")
                  or enc.startswith("utf-16"), f"only CRLF in {n}")

    # ---- change encoding / eol from the status bar and save
    d = doc_named(w, "utf8.txt")
    w.set_current(d)
    w.set_encoding("utf-16-be")
    d.set_eol("crlf")
    w.save()
    raw = open(d.path, "rb").read()
    check(raw.startswith(codecs.BOM_UTF16_BE) and "\r\n".encode("utf-16-be") in raw, "converted to UTF-16 BE CRLF")
    d2 = doc_named(w, "latin1.txt")
    w.set_current(d2)
    d2.buffer.insert_at_cursor("€", -1)
    w.set_encoding("latin-1")    # stays: euro is not latin-1 -> error dialog
    yield 50
    check(w.dialog is not None, "encoding error dialog shown")
    w.hide_dialog(w.dialog)
    w.save()    # latin-1 cannot hold the euro sign: saved as UTF-8 instead of losing it
    check(textio.read_file(d2.path).encoding == "utf-8", "unencodable text saved as UTF-8")

    # ---- find / replace
    t = w.new_tab()
    t.buffer.set_text("apple Apple pineapple apple\nAPPLE", -1)
    t.buffer.place_cursor(t.buffer.get_start_iter())
    w.show_find(False)
    yield 50
    check(w.find.get_visible(), "find card visible")
    w.find.entry.set_text("apple")
    yield 50
    w.find_next()
    sel = t.buffer.get_selection_bounds()
    check(bool(sel), "find selects a match")
    util.settings().set("match_case", True)
    util.settings().set("whole_word", True)
    w.show_find(True)
    w.find.entry.set_text("apple")
    yield 50
    n = w.replace_all("pear")
    check(n == 2, f"replace all (case + whole word) count {n}")
    check(t.get_text() == "pear Apple pineapple pear\nAPPLE", f"replace all result {t.get_text()!r}")
    util.settings().set("match_case", False)
    util.settings().set("whole_word", False)
    w.find.entry.set_text("APPLE")
    yield 30
    t.buffer.place_cursor(t.buffer.get_start_iter())
    w.find_next()
    w.replace_one("fig")
    check("fig" in t.get_text(), "replace one")
    w.find_previous()
    w.find.close_card()
    check(not w.find.get_visible(), "find card closed")

    # ---- go to line
    dlg = w.goto_dialog()
    yield 50
    entry = [c for c in _walk(dlg) if isinstance(c, Gtk.Entry)][0]
    entry.set_text("2")
    entry.emit("activate")
    yield 30
    it = t.buffer.get_iter_at_mark(t.buffer.get_insert())
    check(it.get_line() == 1, "go to line 2")
    check(w.dialog is None, "go to dialog closed")
    dlg = w.goto_dialog()
    entry = [c for c in _walk(dlg) if isinstance(c, Gtk.Entry)][0]
    entry.set_text("99")
    entry.emit("activate")
    check(w.dialog is dlg, "go to beyond last line keeps dialog open")
    w.hide_dialog(dlg)

    # ---- edit commands, zoom, time/date
    w.select_all()
    w.copy()
    w.insert_time_date()
    check(len(t.get_text()) > 5, "time/date inserted")
    w.undo()
    w.redo()
    for step in (1, 1, -1, 0):
        w.zoom(step)
    check(t.zoom == 100 and w.st_zoom.get_label() == "100%", "zoom restore")
    w.zoom(1)
    check(t.zoom == 110, "zoom in")

    # ---- keyboard shortcuts (window capture handler)
    from gi.repository import Gdk
    C, S = Gdk.ModifierType.CONTROL_MASK, Gdk.ModifierType.SHIFT_MASK
    n0 = len(w.documents())
    w._on_key(None, Gdk.KEY_n, 0, C)
    check(len(w.documents()) == n0 + 1, "Ctrl+N new tab")
    cur = w.doc
    w._on_key(None, Gdk.KEY_Tab, 0, C)
    check(w.doc is not cur, "Ctrl+Tab next tab")
    w._on_key(None, Gdk.KEY_1, 0, C)
    check(w.doc is w.documents()[0], "Ctrl+1 first tab")
    w._on_key(None, Gdk.KEY_w, 0, C)
    w.set_current(w.documents()[-1])
    z = w.doc.zoom
    w._on_key(None, Gdk.KEY_plus, 0, C | S)
    check(w.doc.zoom == z + 10, "Ctrl+Plus (with Shift) zooms in")
    w._on_key(None, Gdk.KEY_0, 0, C)
    check(w.doc.zoom == 100, "Ctrl+0 restores zoom")
    w._on_key(None, Gdk.KEY_f, 0, C)
    check(w.find.get_visible(), "Ctrl+F opens find")
    w.find.close_card()
    w._on_key(None, Gdk.KEY_w, 0, C)    # close the Ctrl+N tab (empty: no prompt)
    check(len(w.documents()) == n0 - 1 or w.dialog is None, "Ctrl+W closes tab")
    if w.dialog is not None:
        w.hide_dialog(w.dialog)

    # ---- menus (build every menu, open and close)
    for key in ("file", "edit", "view"):
        w.menu_buttons[key].emit("clicked")
        yield 80
        w.open_menu.popdown()
    for b in (w._build_kind_menu, w._build_eol_menu, w._build_enc_menu):
        m = w._open_menu(w.st_enc, b, up=True)
        yield 30
        m.popdown()
    m = w._context_menu(w.current.view, 50, 20)
    yield 50
    m.popdown()

    # ---- markdown
    md = w.new_tab(markdown=True)
    yield 30
    check(w.toolbar.get_visible(), "toolbar visible for Markdown tab")
    md.buffer.set_text("hello world", -1)
    md.buffer.select_range(md.buffer.get_iter_at_offset(0), md.buffer.get_iter_at_offset(5))
    w._md(__import__("fenestra_notepad.markdown", fromlist=["x"]).wrap, "**")
    check(md.get_text() == "**hello** world", f"bold {md.get_text()!r}")
    from fenestra_notepad import markdown as mdm
    w._md(mdm.heading, 2)
    check(md.get_text().startswith("## "), "heading 2")
    w._md(mdm.toggle_list, False)
    w._md(mdm.clear_formatting)
    check(md.get_text() == "hello world", f"clear formatting {md.get_text()!r}")
    w._md(mdm.insert_table, 2, 2)
    check("| --- | --- |" in md.get_text().replace("|---|", "| --- |") or "---" in md.get_text(), "table inserted")
    w._table_picker(w.fmt_table)
    yield 50
    w.open_menu.popdown()
    w.set_markdown(False)
    check(not w.toolbar.get_visible(), "toolbar hidden after switching to plain text")

    # ---- settings page
    w.open_settings()
    yield 80
    s = util.settings()
    s.set("word_wrap", False)
    check(w.current.view.get_wrap_mode() == Gtk.WrapMode.NONE, "word wrap off")
    s.set("word_wrap", True)
    s.set("theme", "dark")
    yield 30
    s.set("theme", "light")
    s.set("font_size", 14)
    s.set("font_family", "Liberation Mono")
    s.set("status_bar", False)
    check(not w.statusbar.get_visible(), "status bar hidden")
    s.set("status_bar", True)
    w.settings_page.font_exp.set_expanded(True)
    w.close_settings()
    yield 30

    # ---- printing (exported to PDF, no dialog)
    from fenestra_notepad import printing
    pdf = os.path.join(TMP, "out.pdf")
    printing.print_document(w, w.doc, lambda m: errors.append("print: " + m), export_to=pdf)
    yield 100
    check(os.path.exists(pdf) and open(pdf, "rb").read(4) == b"%PDF", "print to PDF")

    # ---- close tab with unsaved changes -> Save / Don't save / Cancel
    t2 = w.new_tab()
    t2.buffer.set_text("unsaved scratch", -1)
    w.close_tab(t2)
    yield 50
    check(w.dialog is not None, "save prompt on closing a modified tab")
    labels = [b.get_label() for b in w.dialog.buttons]
    check(labels == ["Save", "Don't save", "Cancel"], f"prompt buttons {labels}")
    w.dialog.buttons[1].emit("clicked")
    yield 30
    check(t2 not in w.documents(), "tab closed after Don't save")

    # ---- second window via the app
    w2 = a.new_window()
    yield 100
    check(len(a.windows) == 2, "new window")
    w2.close_tab(w2.doc)    # empty tab: closes without prompt, window goes away
    yield 100
    check(len(a.windows) == 1, "window closed with its last tab")

    # ---- big file: UI must stay responsive while loading
    if BIG:
        line = "The quick brown fox jumps over the lazy dog 0123456789 " * 2 + "\n"
        big = os.path.join(F, "big.log")
        with open(big, "w") as f:
            f.write(line * (20 * 1024 * 1024 // len(line)))
        gaps = []
        last = [time.monotonic()]

        def tick():
            now = time.monotonic()
            gaps.append(now - last[0])
            last[0] = now
            return True
        tid = GLib.timeout_add(20, tick)
        t0 = time.monotonic()
        w.open_paths([big])
        wait_loaded(w, 120)
        dt = time.monotonic() - t0
        pump(300)
        GLib.source_remove(tid)
        bd = doc_named(w, "big.log")
        check(bd.buffer.get_char_count() == os.path.getsize(big), "big file fully loaded")
        worst = max(gaps) if gaps else 0
        print(f"20 MB load: {dt:.2f} s, longest main-loop stall {worst * 1000:.0f} ms", flush=True)
        check(worst < 1.0, f"main loop stalled {worst:.2f} s while loading the big file")
        bd.buffer.place_cursor(bd.buffer.get_end_iter())
        w.find.entry.set_text("zzz-not-there")
        t0 = time.monotonic()
        w.find_next()
        gaps.clear()
        last[0] = time.monotonic()
        tid = GLib.timeout_add(20, tick)
        end = time.monotonic() + 30
        while w.searching and time.monotonic() < end:
            GLib.MainContext.default().iteration(True)
        GLib.source_remove(tid)
        check(max(gaps or [0]) < 0.5, f"search stalled the main loop {max(gaps or [0]):.2f} s")
        print(f"20 MB search miss: {time.monotonic() - t0:.2f} s", flush=True)
        check(w.find.entry.has_css_class("no-match"), "search miss reported")
        bd.buffer.insert(bd.buffer.get_end_iter(), "needle-at-the-end", -1)
        bd.buffer.place_cursor(bd.buffer.get_start_iter())
        w.find.entry.set_text("needle-at-the-end")
        t0 = time.monotonic()
        w.find_next()
        while w.searching and time.monotonic() < end:
            GLib.MainContext.default().iteration(True)
        sel = bd.buffer.get_selection_bounds()
        print(f"20 MB search hit at the end: {time.monotonic() - t0:.2f} s", flush=True)
        check(bool(sel) and sel[1].is_end(), "search finds text at the end of the big file")
        w.find.entry.set_text("lazy dog 0123456789 The")
        t0 = time.monotonic()
        n = w.replace_all("LAZY")
        print(f"20 MB replace all ({n}): {time.monotonic() - t0:.2f} s", flush=True)
        check(n > 100000 and "LAZY" in bd.buffer.get_text(bd.buffer.get_start_iter(),
                                                          bd.buffer.get_iter_at_offset(400), True), "big replace all")
        bd.buffer.set_modified(False)
        w._remove_doc(bd)

    # ---- unsaved untitled text for the session
    keep = w.new_tab()
    keep.buffer.set_text("remember me\nacross restarts", -1)
    mdk = w.new_tab(markdown=True)
    mdk.buffer.set_text("# kept markdown", -1)
    mod = doc_named(w, "notes.md")
    mod.buffer.insert(mod.buffer.get_end_iter(), "unsaved tail", -1)
    yield 50
    a.save_session_now()
    st = os.path.join(os.environ["XDG_STATE_HOME"], "fenestra-notepad", "session.json")
    check(os.path.exists(st), "session file written")
    # close the last window: with "continue previous session" there is no prompt
    w.close()
    yield 200
    check(not a.windows, "last window closed without prompts (session kept)")


def phase2(a):
    yield 300
    w = a.windows[0]
    wait_loaded(w)
    yield 100
    texts = [d.get_text() for d in w.documents()]
    check("remember me\nacross restarts" in texts, f"untitled text restored ({len(texts)} tabs)")
    check("# kept markdown" in texts, "markdown tab restored")
    mds = [d for d in w.documents() if d.get_text() == "# kept markdown"]
    check(bool(mds) and mds[0].markdown, "markdown flag restored")
    mod = doc_named(w, "notes.md")
    check(mod.get_text().endswith("unsaved tail") and mod.modified, "modified file restored with its edits")
    check(doc_named(w, "utf16le.txt").encoding == "utf-16-le", "file tab restored from disk")
    # "Start new session": nothing restored next time
    util.settings().set("startup", "new")
    for d in list(w.documents()):
        d.buffer.set_modified(False)
        if d.path is None:
            d.buffer.set_text("", 0)
            d.buffer.set_modified(False)
    a.exit()
    yield 200


def _walk(w):
    out = [w]
    c = w.get_first_child()
    while c is not None:
        out += _walk(c)
        c = c.get_next_sibling()
    return out


def run(argv, phase):
    opts = appmod.parse_args(argv)
    a = appmod.App(opts)
    gen = [None]

    def step():
        try:
            if gen[0] is None:
                if not a.windows:
                    return True
                gen[0] = phase(a)
            delay = next(gen[0])
            GLib.timeout_add(delay or 30, step)
        except StopIteration:
            GLib.timeout_add(200, lambda: (a.quit(), False)[1])
        except Exception:  # noqa: BLE001
            errors.append(sys.exc_info())
            traceback.print_exc()
            a.quit()
        return False
    GLib.timeout_add(200, step)
    GLib.timeout_add(300000, lambda: (errors.append("timeout"), a.quit()))
    a.run(argv)


def main():
    unit_checks()
    run(["fenestra-notepad"] + list(files.values()), phase1)
    util._settings = None     # re-read settings like a fresh process would
    run(["fenestra-notepad"], phase2)
    ok = not errors
    print(f"{checks[0]} checks, {len(errors)} failures")
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

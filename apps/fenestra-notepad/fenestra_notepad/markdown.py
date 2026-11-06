"""Markdown formatting commands used by the formatting toolbar (Markdown tabs).

Everything is a plain-text edit of the buffer, grouped as a single undo step."""
from __future__ import annotations

import re

_HEADING = re.compile(r"^(#{1,6})\s+")
_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def _line_range(buf):
    """Iters spanning whole lines touched by the selection (or the cursor line)."""
    sel = buf.get_selection_bounds()
    if sel:
        s, e = sel
        if e.starts_line() and e.compare(s) > 0:
            e.backward_char()
    else:
        s = buf.get_iter_at_mark(buf.get_insert())
        e = s.copy()
    s.set_line_offset(0)
    if not e.ends_line():
        e.forward_to_line_end()
    return s, e


def _replace_lines(buf, fn):
    s, e = _line_range(buf)
    start_off = s.get_offset()
    text = buf.get_text(s, e, True)
    new = "\n".join(fn(i, ln) for i, ln in enumerate(text.split("\n")))
    if new == text:
        return
    buf.begin_user_action()
    buf.delete(s, e)
    buf.insert(buf.get_iter_at_offset(start_off), new, -1)
    buf.end_user_action()
    end = buf.get_iter_at_offset(start_off + len(new))
    buf.place_cursor(end)


def current_heading(buf):
    it = buf.get_iter_at_mark(buf.get_insert())
    it.set_line_offset(0)
    e = it.copy()
    if not e.ends_line():
        e.forward_to_line_end()
    m = _HEADING.match(buf.get_text(it, e, False))
    return len(m.group(1)) if m else 0


def heading(buf, level):
    """level 1..6, 0 = body text."""
    def fn(_i, ln):
        ln = _HEADING.sub("", ln)
        return ("#" * level + " " + ln) if level else ln
    _replace_lines(buf, fn)


def toggle_list(buf, numbered=False):
    s, e = _line_range(buf)
    lines = buf.get_text(s, e, True).split("\n")
    pat = re.compile(r"^\s*\d+[.)]\s+") if numbered else re.compile(r"^\s*[-*+]\s+")
    all_on = all(pat.match(ln) for ln in lines if ln.strip()) and any(ln.strip() for ln in lines)

    def fn(i, ln):
        body = _LIST.sub(r"\1", ln)
        if all_on:
            return body
        if not ln.strip() and len(lines) > 1:
            return ln
        return (f"{i + 1}. " if numbered else "- ") + body
    _replace_lines(buf, fn)


def wrap(buf, marker):
    """Toggle an inline marker (** bold, * italic, ~~ strikethrough) around the selection."""
    n = len(marker)
    sel = buf.get_selection_bounds()
    buf.begin_user_action()
    if not sel:
        it = buf.get_iter_at_mark(buf.get_insert())
        off = it.get_offset()
        buf.insert(it, marker + marker, -1)
        buf.place_cursor(buf.get_iter_at_offset(off + n))
        buf.end_user_action()
        return
    s, e = sel
    so, eo = s.get_offset(), e.get_offset()
    text = buf.get_text(s, e, True)
    if len(text) >= 2 * n and text.startswith(marker) and text.endswith(marker) \
            and not (marker == "*" and text.startswith("**") and not text.startswith("***")):
        inner = text[n:-n]
        buf.delete(s, e)
        buf.insert(buf.get_iter_at_offset(so), inner, -1)
        buf.select_range(buf.get_iter_at_offset(so), buf.get_iter_at_offset(so + len(inner)))
        buf.end_user_action()
        return
    # markers just outside the selection -> remove them
    bs = buf.get_iter_at_offset(max(0, so - n))
    ae = buf.get_iter_at_offset(eo + n)
    if so >= n and buf.get_text(bs, s, True) == marker and buf.get_text(e, ae, True) == marker:
        buf.delete(e, buf.get_iter_at_offset(eo + n))
        buf.delete(buf.get_iter_at_offset(so - n), buf.get_iter_at_offset(so))
        buf.select_range(buf.get_iter_at_offset(so - n), buf.get_iter_at_offset(eo - n))
        buf.end_user_action()
        return
    buf.insert(buf.get_iter_at_offset(eo), marker, -1)
    buf.insert(buf.get_iter_at_offset(so), marker, -1)
    buf.select_range(buf.get_iter_at_offset(so + n), buf.get_iter_at_offset(eo + n))
    buf.end_user_action()


def selected_text(buf):
    sel = buf.get_selection_bounds()
    return buf.get_text(sel[0], sel[1], True) if sel else ""


def insert_link(buf, text, url):
    text = text or url
    md = f"[{text}]({url})"
    buf.begin_user_action()
    sel = buf.get_selection_bounds()
    if sel:
        buf.delete(*sel)
    buf.insert_at_cursor(md, -1)
    buf.end_user_action()


def insert_table(buf, rows, cols):
    head = "| " + " | ".join(f"Column {c + 1}" for c in range(cols)) + " |"
    sep = "|" + "|".join(" --- " for _c in range(cols)) + "|"
    body = ["| " + " | ".join("   " for _c in range(cols)) + " |" for _r in range(max(0, rows - 1))]
    table = "\n".join([head, sep] + body)
    it = buf.get_iter_at_mark(buf.get_insert())
    prefix = "" if it.starts_line() else "\n"
    buf.begin_user_action()
    buf.insert_at_cursor(prefix + table + "\n", -1)
    buf.end_user_action()


def clear_formatting(buf):
    """Remove Markdown markers from the selected lines (or the current line)."""
    def fn(_i, ln):
        for _r in range(3):     # markers can be nested: "- ## > text"
            ln = _HEADING.sub("", ln)
            ln = _LIST.sub(r"\1", ln)
            ln = re.sub(r"^\s*>\s?", "", ln)
        ln = _LINK.sub(r"\1", ln)
        ln = re.sub(r"(\*\*|__|~~|`)", "", ln)
        ln = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"\1", ln)
        ln = re.sub(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])", r"\1", ln)
        return ln
    _replace_lines(buf, fn)

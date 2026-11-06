"""Session store (~/.local/state/fenestra-notepad): open windows and tabs, including the
text of unsaved tabs, so Notepad continues where it was closed (Windows Notepad style)."""
from __future__ import annotations

import json
import os

from . import util

VERSION = 1


def _dir():
    return util.state_dir()


def _tabs_dir():
    return os.path.join(_dir(), "tabs")


def _content_path(uid):
    return os.path.join(_tabs_dir(), uid + ".txt")


def _atomic_write(path, data: bytes):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def save(windows):
    """windows: list of NotepadWindow (in stacking order, most recent first)."""
    if util.DEMO:
        return
    try:
        os.makedirs(_tabs_dir(), exist_ok=True)
    except OSError:
        return
    out = {"version": VERSION, "windows": []}
    keep = set()
    for win in windows:
        tabs = []
        for doc in win.documents():
            if doc.loading:
                # still filling the buffer: remember just the file
                if doc.path:
                    tabs.append({"uid": doc.uid, "path": doc.path, "markdown": doc.markdown,
                                 "modified": False, "content": False, "zoom": doc.zoom})
                continue
            needs_content = (doc.path is None and not doc.is_empty()) or (doc.path is not None and doc.modified)
            if doc.path is None and doc.is_empty() and len(win.documents()) > 1:
                continue    # empty untitled tabs are not worth restoring (unless alone)
            ins = doc.buffer.get_iter_at_mark(doc.buffer.get_insert())
            t = {"uid": doc.uid, "path": doc.path, "markdown": doc.markdown, "encoding": doc.encoding,
                 "bom": doc.bom, "eol": doc.eol, "modified": bool(doc.modified), "content": needs_content,
                 "cursor": ins.get_offset(), "zoom": doc.zoom}
            if needs_content:
                keep.add(doc.uid)
                p = _content_path(doc.uid)
                if doc.session_dirty or not os.path.exists(p):
                    try:
                        _atomic_write(p, doc.get_text().encode("utf-8", "surrogatepass"))
                    except OSError:
                        continue
            doc.session_dirty = False
            tabs.append(t)
        if not tabs:
            continue
        active = win.active_index()
        out["windows"].append({"tabs": tabs, "active": max(0, min(active, len(tabs) - 1)),
                               "width": win.get_width() or win.get_default_size()[0],
                               "height": win.get_height() or win.get_default_size()[1],
                               "maximized": bool(win.is_maximized())})
    try:
        _atomic_write(os.path.join(_dir(), "session.json"), json.dumps(out, indent=1).encode())
    except OSError:
        return
    # drop content of tabs that are gone
    try:
        for f in os.listdir(_tabs_dir()):
            if f.endswith(".txt") and f[:-4] not in keep:
                os.unlink(os.path.join(_tabs_dir(), f))
    except OSError:
        pass


def clear():
    if util.DEMO:
        return
    try:
        os.unlink(os.path.join(_dir(), "session.json"))
    except OSError:
        pass
    try:
        for f in os.listdir(_tabs_dir()):
            os.unlink(os.path.join(_tabs_dir(), f))
    except OSError:
        pass


def load():
    """-> list of window dicts; tab dicts get "text" when they had stored content."""
    if util.DEMO:
        return []
    try:
        with open(os.path.join(_dir(), "session.json")) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return []
    wins = []
    for w in data.get("windows", []):
        tabs = []
        for t in w.get("tabs", []):
            if not isinstance(t, dict) or "uid" not in t:
                continue
            if t.get("content"):
                try:
                    with open(_content_path(t["uid"]), "rb") as f:
                        t["text"] = f.read().decode("utf-8", "replace")
                except OSError:
                    if not t.get("path"):
                        continue
            elif t.get("path") and not os.path.exists(t["path"]):
                continue
            tabs.append(t)
        if tabs:
            w["tabs"] = tabs
            wins.append(w)
    return wins

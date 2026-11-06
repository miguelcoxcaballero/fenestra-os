# SPDX-License-Identifier: GPL-3.0-or-later
"""~/.config/fenestra/shell.conf: Fenestra Shell options shared with Settings.

The shell reads the file with Qt's QSettings (IniFormat) and reloads it when it changes
(it watches the directory, shell/src/core/shellsettings.cpp), so Settings only has to write
it. This module reads and writes the same format:

* ``[Group]`` sections, ``Key=value`` lines; keys outside a group live in ``[General]``;
* strings are written like QSettings does (quoted when they contain ``,;=`` or leading /
  trailing spaces, ``\\`` and ``"`` escaped, a leading ``@`` doubled);
* string lists are comma + space separated (``a, b``); an empty list is ``@Invalid()``;
* booleans are ``true`` / ``false``.

Keys and lines this module does not change are kept exactly as they were. Writes are atomic
(a temporary file in the same directory, then rename), so the shell never reads a half
written file.
"""
from __future__ import annotations

import builtins
import os
import tempfile

from .. import util

_watchers = []


def config_dir() -> str:
    """$XDG_CONFIG_HOME or ~/.config (QStandardPaths::GenericConfigLocation)."""
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def path() -> str:
    return os.path.join(config_dir(), "fenestra", "shell.conf")


# --------------------------------------------------------------------------- value codec

def _escape(s: str) -> str:
    out = []
    quote = False
    for ch in s:
        o = ord(ch)
        if ch in ";,=":
            quote = True
        if ch in '"\\':
            out.append("\\" + ch)
        elif ch == "\0":
            out.append("\\0")
        elif ch in "\a\b\f\n\r\t\v":
            out.append("\\" + "abfnrtv"["\a\b\f\n\r\t\v".index(ch)])
        elif o <= 0x1F or o == 0x7F:
            out.append("\\x%x" % o)
        else:
            out.append(ch)
    text = "".join(out)
    if quote or (text and (text[0] == " " or text[-1] == " ")):
        text = f'"{text}"'
    return text


def encode(value) -> str:
    """Python value -> QSettings INI text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        items = [str(v) for v in value]
        if not items:
            return "@Invalid()"
        return ", ".join(_escape("@" + v if v.startswith("@") else v) for v in items)
    s = str(value)
    if s.startswith("@"):
        s = "@" + s
    return _escape(s)


_ESC = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "0": "\0",
        '"': '"', "\\": "\\", "'": "'", "?": "?"}


def decode(raw: str):
    """QSettings INI text -> str, or list[str] when it holds several comma separated items
    (like QSettings), or None for @Invalid()."""
    raw = raw.strip()
    if raw == "@Invalid()":
        return None
    items, cur, quoted, i, any_quote = [], [], False, 0, False
    while i < len(raw):
        ch = raw[i]
        if ch == '"':
            quoted = not quoted
            any_quote = True
        elif ch == "\\" and i + 1 < len(raw):
            i += 1
            nx = raw[i]
            if nx == "x":
                j = i + 1
                while j < len(raw) and raw[j] in "0123456789abcdefABCDEF":
                    j += 1
                cur.append(chr(int(raw[i + 1:j] or "0", 16)))
                i = j - 1
            else:
                cur.append(_ESC.get(nx, nx))
        elif ch == "," and not quoted:
            items.append("".join(cur).strip() if not any_quote else "".join(cur))
            cur, any_quote = [], False
            # skip the space after the separator
            while i + 1 < len(raw) and raw[i + 1] == " ":
                i += 1
        else:
            cur.append(ch)
        i += 1
    items.append("".join(cur) if any_quote else "".join(cur).strip())
    items = [s[1:] if s.startswith("@@") else s for s in items]
    return items if len(items) > 1 else items[0]


# --------------------------------------------------------------------------- file

def _split(key: str):
    group, _sep, name = key.rpartition("/")
    return group or "General", name


def _read_lines(file=None):
    try:
        with open(file or path(), encoding="utf-8") as f:
            return f.read().splitlines()
    except OSError:
        return []


def _parse(lines):
    """-> {group: {key: raw value}} (case-sensitive, like QSettings on Linux)."""
    data, group = {}, "General"
    for line in lines:
        t = line.strip()
        if not t or t[0] in ";#":
            continue
        if t.startswith("[") and t.endswith("]"):
            group = t[1:-1]
            data.setdefault(group, {})
            continue
        if "=" in t:
            k, v = t.split("=", 1)
            data.setdefault(group, {})[k.strip()] = v.strip()
    return data


def raw(key: str, file=None):
    group, name = _split(key)
    return _parse(_read_lines(file)).get(group, {}).get(name)


def get(key: str, default=None, file=None):
    """Value of ``Group/Key`` (str, list or None), or ``default`` when it is not set.
    ``file`` reads another INI file of the same format (e.g. a KDE config file)."""
    r = raw(key, file)
    return default if r is None else decode(r)


def get_bool(key: str, default=False) -> bool:
    v = get(key)
    if v is None or isinstance(v, list):
        return default
    v = v.strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off", ""):
        return False
    return default


def get_list(key: str, default=None) -> list[str] | None:
    r = raw(key)
    if r is None:
        return default
    v = decode(r)
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def has(key: str) -> bool:
    return raw(key) is not None


def set_many(values: dict, file=None) -> bool:
    """Set several ``Group/Key`` values at once (None removes the key) and write the file
    atomically. Refused in read-only mode; recorded in the test sandbox."""
    if util.SANDBOX:
        for k, v in values.items():
            util.record("shellconf" if file is None else "config", k if file is None
                        else f"{os.path.basename(file)} {k}", v)
    elif util.READ_ONLY:
        util.log("read-only: shell.conf", values)
        return False
    lines = _read_lines(file)
    pending = {}
    for k, v in values.items():
        g, n = _split(k)
        pending.setdefault(g, {})[n] = v
    out, group, done = [], "General", builtins.set()

    def flush(g):
        # keys of group g that were not in the file yet go at the end of that group
        for n, v in pending.get(g, {}).items():
            if (g, n) not in done and v is not None:
                out.append(f"{n}={encode(v)}")
                done.add((g, n))

    for line in lines:
        t = line.strip()
        if t.startswith("[") and t.endswith("]"):
            while out and not out[-1].strip():
                out.pop()
            flush(group)
            if out:
                out.append("")
            group = t[1:-1]
            out.append(line)
            continue
        if t and t[0] not in ";#" and "=" in t:
            n = t.split("=", 1)[0].strip()
            if n in pending.get(group, {}):
                v = pending[group][n]
                done.add((group, n))
                if v is not None:
                    out.append(f"{n}={encode(v)}")
                continue
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    flush(group)
    seen = {g for g in _parse(lines)} | {group}
    for g in pending:
        if g in seen:
            continue
        rows = [(n, v) for n, v in pending[g].items() if v is not None]
        if not rows:
            continue
        if out:
            out.append("")
        out.append(f"[{g}]")
        out.extend(f"{n}={encode(v)}" for n, v in rows)
    text = "\n".join(out) + "\n"
    return write_atomic(file or path(), text)


def set(key: str, value) -> bool:  # noqa: A001 - mirrors QSettings::setValue
    return set_many({key: value})


def remove(key: str) -> bool:
    return set_many({key: None})


def write_atomic(p: str, text: str) -> bool:
    """Write ``text`` to ``p`` through a temporary file in the same directory + rename."""
    d = os.path.dirname(p)
    try:
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(p) + ".", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.chmod(tmp, os.stat(p).st_mode & 0o777 if os.path.exists(p) else 0o644)
            except OSError:
                pass
            os.replace(tmp, p)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except OSError as e:
        util.log("write failed", p, e)
        return False


def watch(cb):
    """Call cb() (from the GLib main loop) whenever shell.conf changes on disk."""
    from gi.repository import Gio, GLib
    if not _watchers:
        d = Gio.File.new_for_path(os.path.dirname(path()))
        try:
            os.makedirs(d.get_path(), exist_ok=True)
        except OSError:
            pass
        try:
            mon = d.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        except GLib.Error:
            return
        name = os.path.basename(path())
        callbacks = []

        def changed(_m, f, other, _ev):
            names = {x.get_basename() for x in (f, other) if x is not None}
            if name in names:
                for c in list(callbacks):
                    c()
        mon.connect("changed", changed)
        _watchers.append((mon, callbacks))
    _watchers[0][1].append(cb)

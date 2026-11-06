"""Encoding and line-ending detection / conversion (no GTK, unit-testable).

Documents are kept with "\n" line endings in the editor; the original line ending
and encoding are remembered and used again when saving."""
from __future__ import annotations

import codecs
import os

# encoding keys -> status bar label
ENCODINGS = {
    "utf-8": "UTF-8",
    "utf-8-bom": "UTF-8 with BOM",
    "utf-16-le": "UTF-16 LE",
    "utf-16-be": "UTF-16 BE",
    "latin-1": "ISO-8859-1",
}
ENCODING_ORDER = ["utf-8", "utf-8-bom", "utf-16-le", "utf-16-be", "latin-1"]

EOLS = {"crlf": "\r\n", "lf": "\n", "cr": "\r"}
# Plain names (no operating-system names in the interface).
EOL_LABELS = {"crlf": "CRLF", "lf": "LF", "cr": "CR"}
EOL_ORDER = ["crlf", "lf", "cr"]

DEFAULT_ENCODING = "utf-8"
DEFAULT_EOL = "lf"


class Detected:
    __slots__ = ("text", "encoding", "bom", "eol")

    def __init__(self, text, encoding, bom, eol):
        self.text, self.encoding, self.bom, self.eol = text, encoding, bom, eol


def _looks_utf16(data: bytes):
    """BOM-less UTF-16 heuristic: lots of NUL bytes on one parity."""
    n = min(len(data), 4096) & ~1
    if n < 4:
        return None
    sample = data[:n]
    even = sample[0::2].count(0)
    odd = sample[1::2].count(0)
    half = n // 2
    if odd > half * 0.4 and even < half * 0.05:
        return "utf-16-le"
    if even > half * 0.4 and odd < half * 0.05:
        return "utf-16-be"
    return None


def detect_encoding(data: bytes):
    """-> (encoding key, bom present, number of BOM bytes)."""
    if data.startswith(codecs.BOM_UTF8):
        return "utf-8-bom", True, 3
    if data.startswith(codecs.BOM_UTF16_LE):
        return "utf-16-le", True, 2
    if data.startswith(codecs.BOM_UTF16_BE):
        return "utf-16-be", True, 2
    u16 = _looks_utf16(data)
    if u16:
        return u16, False, 0
    try:
        data.decode("utf-8")
        return "utf-8", False, 0
    except UnicodeDecodeError:
        return "latin-1", False, 0


def _codec(enc):
    return {"utf-8": "utf-8", "utf-8-bom": "utf-8", "utf-16-le": "utf-16-le",
            "utf-16-be": "utf-16-be", "latin-1": "latin-1"}[enc]


def detect_eol(text: str) -> str:
    """Line ending of the first line break (Windows Notepad behaviour); LF if none."""
    i = text.find("\n")
    j = text.find("\r")
    if i < 0 and j < 0:
        return DEFAULT_EOL
    if j >= 0 and (i < 0 or j < i):
        return "crlf" if text.startswith("\r\n", j) else "cr"
    return "lf"


def normalize(text: str) -> str:
    if "\r" not in text:
        return text
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode(data: bytes) -> Detected:
    enc, bom, skip = detect_encoding(data)
    try:
        text = data[skip:].decode(_codec(enc))
    except UnicodeDecodeError:
        enc, bom = "latin-1", False
        text = data.decode("latin-1")
    eol = detect_eol(text)
    text = normalize(text)
    # NUL characters would cut GtkTextBuffer text: show them as U+2400-like replacement
    if "\x00" in text:
        text = text.replace("\x00", "␀")
    return Detected(text, enc, bom, eol)


def encode(text: str, encoding: str, eol: str, bom: bool | None = None) -> bytes:
    """Editor text (\\n line endings) -> bytes in the given encoding and line ending.
    Raises UnicodeEncodeError if a character cannot be represented (latin-1)."""
    if eol != "lf":
        text = text.replace("\n", EOLS[eol])
    body = text.encode(_codec(encoding))
    if encoding == "utf-8-bom":
        return codecs.BOM_UTF8 + body
    if encoding in ("utf-16-le", "utf-16-be"):
        if bom is None or bom:
            return (codecs.BOM_UTF16_LE if encoding == "utf-16-le" else codecs.BOM_UTF16_BE) + body
    return body


def can_encode(text: str, encoding: str) -> bool:
    if encoding != "latin-1":
        return True
    try:
        text.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


def read_file(path: str) -> Detected:
    with open(path, "rb") as f:
        data = f.read()
    return decode(data)


def write_file(path: str, data: bytes):
    """Atomic-ish write that keeps the file mode (and follows symlinks)."""
    real = os.path.realpath(path)
    d = os.path.dirname(real) or "."
    mode = None
    try:
        mode = os.stat(real).st_mode & 0o7777
    except OSError:
        pass
    tmp = os.path.join(d, f".{os.path.basename(real)}.fenestra-notepad-{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, real)
    except PermissionError:
        # directory not writable but the file may be: write in place
        try:
            os.unlink(tmp)
        except OSError:
            pass
        with open(real, "wb") as f:
            f.write(data)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

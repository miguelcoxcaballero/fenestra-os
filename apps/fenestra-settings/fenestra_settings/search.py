"""Search index over every page and indexed row."""
from __future__ import annotations

import unicodedata

from .i18n import _
from .pages.base import PAGES


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


class Entry:
    __slots__ = ("page_id", "key", "title", "where", "icon", "hay", "title_n")

    def __init__(self, page_id, key, title, where, icon, hay):
        self.page_id, self.key, self.title, self.where, self.icon = page_id, key, title, where, icon
        self.hay = hay
        self.title_n = norm(title)


def _root_icon(cls):
    while cls.parent:
        cls = PAGES[cls.parent]
    return f"fs-nav-{cls.id}"


def _crumb(cls):
    parts = []
    c = cls
    while c is not None:
        parts.append(_(c.title))
        c = PAGES.get(c.parent) if c.parent else None
    return "  ›  ".join(reversed(parts))


def build_index() -> list[Entry]:
    out = []
    for pid, cls in PAGES.items():
        icon = _root_icon(cls)
        crumb = _crumb(cls)
        hay = norm(" ".join([cls.title, _(cls.title), cls.keywords, _(cls.keywords) if cls.keywords else ""]))
        out.append(Entry(pid, None, _(cls.title), crumb, icon, hay))
        for key, title, kw in cls.index:
            hay = norm(" ".join([title, _(title), kw, _(kw) if kw else ""]))
            out.append(Entry(pid, key, _(title), crumb, icon, hay))
    return out


def query(index: list[Entry], text: str, limit=8) -> list[Entry]:
    q = norm(text.strip())
    if not q:
        return []
    words = q.split()
    scored = []
    for e in index:
        if not all(w in e.hay for w in words):
            continue
        score = 0
        if e.title_n.startswith(q):
            score += 100
        elif q in e.title_n:
            score += 60
        elif all(w in e.title_n for w in words):
            score += 40
        if e.key is None:
            score += 5
        score -= len(e.title_n) * 0.1
        scored.append((score, e))
    scored.sort(key=lambda t: -t[0])
    seen = set()
    res = []
    for _s, e in scored:
        k = (e.page_id, e.key, e.title)
        if k in seen:
            continue
        seen.add(k)
        res.append(e)
        if len(res) >= limit:
            break
    return res

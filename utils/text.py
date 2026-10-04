"""Text utilities: sentences, tokens, snippets and output sanitising."""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has",
    "have", "having", "he", "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "just", "me", "more", "most", "my", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "them", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "will", "with", "would", "you", "your", "yours",
}

_ABBREV = ["Inc.", "Ltd.", "Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "vs.", "e.g.", "i.e.", "etc.", "Co.", "Corp.", "St.", "No.", "approx."]
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def split_sentences(text: str) -> list[str]:
    """Rule-based sentence splitter that respects common abbreviations and decimals."""
    t = normalize_ws(text)
    if not t:
        return []
    for ab in _ABBREV:
        t = t.replace(ab, ab.replace(".", "\u2024"))
    t = re.sub(r"(\d)\.(\d)", "\\1\u2024\\2", t)
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9#$])", t)
    return [p.replace("\u2024", ".").strip() for p in parts if p.strip()]


def tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def word_count(text: str) -> int:
    return len(tokens(text))


def content_terms(text: str) -> list[str]:
    return [w.lower() for w in tokens(text) if w.lower() not in STOPWORDS and len(w) > 2]


def light_stem(w: str) -> str:
    w = w.lower()
    for suf in ("ing", "ers", "er", "ies", "es", "s", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def stem_set(text: str) -> set[str]:
    return {light_stem(w) for w in content_terms(text)}


def truncate(s: str, n: int = 160) -> str:
    s = normalize_ws(s)
    return s if len(s) <= n else s[: n - 3].rstrip() + "..."


def snippet_around(text: str, start: int, end: int, radius: int = 140) -> str:
    a, b = max(0, start - radius), min(len(text), end + radius)
    out = normalize_ws(text[a:b])
    return ("..." if a > 0 else "") + out + ("..." if b < len(text) else "")


_DASHES = {"\u2014": ", ", "\u2013": "-", "\u2015": "-", "\u2012": "-"}
_ARROWS = {"\u2192": "to", "\u2190": "from", "\u21d2": "to", "\u2794": "to", "\u279c": "to", "\u2192\u2192": "to", "\u2b95": "to", "\u21d4": "and", "\u2194": "and"}
_QUOTES = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00a0": " ", "\u2022": "-", "\u00b7": "-"}


def ui_clean(s: str) -> str:
    """Remove em dashes and arrow symbols from user-facing text."""
    if not s:
        return s
    for k, v in {**_DASHES, **_ARROWS}.items():
        s = s.replace(k, v)
    return s


def pdf_safe(s: str) -> str:
    """Make text safe for ReportLab's built-in Helvetica (Latin-1 only) and house style."""
    s = ui_clean(s or "")
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("latin-1", "ignore").decode("latin-1")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)


def slugify(s: str, default: str = "entity") -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_")
    return s[:50] or default


def sanitize_input(s: str, max_len: int = 200_000) -> str:
    """Strip control characters and cap length for user-supplied text."""
    s = (s or "")[:max_len]
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)

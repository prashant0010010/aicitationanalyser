"""Query helpers: intent detection and key-term extraction."""
from __future__ import annotations

import re

from config.lexicons import CITIES
from utils.text import STOPWORDS, content_terms, light_stem

INTENT_WORDS = {
    "best", "top", "vs", "versus", "compare", "comparison", "review", "reviews", "alternatives", "alternative",
    "recommended", "how", "what", "why", "when", "who", "which", "guide", "buy", "price", "pricing", "cost",
    "cheap", "near", "me", "free", "online", "list", "ranking", "worth",
}


def detect_intent(query: str, entity: str = "") -> str:
    q = (query or "").lower().strip()
    if not q:
        return "informational"
    if entity and q.replace(entity.lower(), "").strip(" -:?") == "":
        return "navigational"
    if re.match(r"^(how (to|do|can|should)|steps to|guide to)\b", q):
        return "howto"
    if re.search(r"\b(near me|nearby)\b", q) or any(re.search(rf"\bin {c}\b", q) for c in CITIES):
        return "local"
    if re.search(r"\b(buy|pricing|price|cost|cheap|discount|coupon|order|subscribe|hire|quote|book)\b", q):
        return "transactional"
    if re.search(r"\b(best|top|vs|versus|compare|comparison|reviews?|alternatives?|recommended|worth it|ranking)\b", q):
        return "commercial"
    return "informational"


def query_phrases(query: str, limit: int = 3) -> list[str]:
    """Noun-phrase-like chunks: runs of content words between stopwords and intent words."""
    from utils.text import tokens

    phrases, cur = [], []
    for w in tokens(query):
        lw = w.lower()
        if lw in STOPWORDS or lw in INTENT_WORDS:
            if cur:
                phrases.append(cur)
                cur = []
        else:
            cur.append(lw)
    if cur:
        phrases.append(cur)
    out = []
    for ph in phrases:
        if len(ph) > 3:
            ph = ph[-3:]
        out.append(" ".join(ph))
    return out[:limit]


def query_terms(query: str) -> list[str]:
    """Content terms of the query excluding generic intent words."""
    out, seen = [], set()
    for t in content_terms(query):
        if t in INTENT_WORDS or t in STOPWORDS:
            continue
        s = light_stem(t)
        if s not in seen:
            seen.add(s)
            out.append(t)
    return out

"""Optional AI enhancement: subtopic suggestions and strategic commentary.

AI output is validated and never changes a score. If the provider fails or
returns malformed output the caller receives None and a status message, and
the local analysis stands on its own.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from providers.base import AIProvider, ProviderError
from utils.cache import TTLCache, stable_hash
from utils.text import ui_clean

log = logging.getLogger("citation_analyser.enhance")
_CACHE = TTLCache(ttl_seconds=3600, max_items=64)
SYSTEM = ("You are a precise GEO (generative engine optimisation) analyst. Respond with a single JSON object only. "
          "Do not invent facts, statistics or sources. Do not use em dashes.")


def _cached(provider: AIProvider, prompt: str) -> dict:
    key = stable_hash(provider.name, provider.model, prompt)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    data = provider.generate_json(SYSTEM, prompt)
    _CACHE.set(key, data)
    return data


def suggest_subtopics(provider: AIProvider, query: str, entity: str, industry: str, market: str) -> list[str]:
    prompt = (
        f"Query: {query}\nEntity: {entity}\nIndustry: {industry or 'unspecified'}\nMarket: {market or 'unspecified'}\n\n"
        "List 4 to 8 subtopics that a complete, citable answer page for this query should cover, beyond generic ones like pricing and features "
        "unless they are specific to the query. Return JSON: {\"subtopics\": [\"short noun phrase\", ...]}. Each item at most 8 words."
    )
    data = _cached(provider, prompt)
    items = data.get("subtopics")
    if not isinstance(items, list):
        raise ProviderError("The AI response did not contain a subtopics list.")
    out = []
    for i in items:
        if isinstance(i, str):
            t = ui_clean(i.strip().strip("."))
            if 2 <= len(t) <= 80 and t.lower() not in {o.lower() for o in out}:
                out.append(t)
    if not out:
        raise ProviderError("The AI response contained no usable subtopics.")
    return out[:8]


def strategic_commentary(provider: AIProvider, payload: dict) -> dict:
    prompt = (
        "Below is a measured GEO analysis. Scores were computed locally and must not be changed.\n"
        f"{json.dumps(payload, ensure_ascii=True)[:6000]}\n\n"
        "Write a short strategic commentary grounded only in this data. Return JSON: "
        "{\"summary\": \"3 to 5 sentences\", \"priorities\": [\"3 to 5 concrete actions that cite a metric number\"]}."
    )
    data = _cached(provider, prompt)
    summary, pri = data.get("summary"), data.get("priorities")
    if not isinstance(summary, str) or not isinstance(pri, list):
        raise ProviderError("The AI commentary did not match the expected format.")
    pri = [ui_clean(p.strip()) for p in pri if isinstance(p, str) and p.strip()][:5]
    if not summary.strip() or not pri:
        raise ProviderError("The AI commentary was empty.")
    return {"summary": ui_clean(summary.strip())[:1500], "priorities": pri}

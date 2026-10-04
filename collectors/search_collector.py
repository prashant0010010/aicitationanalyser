"""Optional web search layer used only to suggest candidate external sources.

Results are real search API responses and are never treated as AI answers.
Providers: Brave Search API and Google Programmable Search (Custom Search JSON API).
Check each provider's current free-tier terms before relying on them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from config.settings import Settings

log = logging.getLogger("citation_analyser.search")


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""


class SearchError(Exception):
    pass


def search_web(query: str, settings: Settings, count: int = 10) -> list[SearchHit]:
    if not settings.search_configured():
        raise SearchError("No search provider is configured. Set SEARCH_PROVIDER and SEARCH_API_KEY.")
    try:
        if settings.search_provider == "brave":
            r = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": settings.search_api_key, "Accept": "application/json"},
                params={"q": query, "count": min(count, 20)},
                timeout=settings.request_timeout,
            )
            _check(r)
            return [SearchHit(x.get("title", ""), x.get("url", ""), x.get("description", ""))
                    for x in r.json().get("web", {}).get("results", [])][:count]
        if settings.search_provider == "google_cse":
            r = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": settings.search_api_key, "cx": settings.search_engine_id, "q": query, "num": min(count, 10)},
                timeout=settings.request_timeout,
            )
            _check(r)
            return [SearchHit(x.get("title", ""), x.get("link", ""), x.get("snippet", "")) for x in r.json().get("items", [])][:count]
    except requests.exceptions.RequestException as exc:
        raise SearchError(f"Search request failed: {type(exc).__name__}.") from exc
    except ValueError as exc:
        raise SearchError("The search provider returned an unreadable response.") from exc
    raise SearchError(f"Unknown search provider: {settings.search_provider}")


def _check(r: requests.Response) -> None:
    if r.status_code in (401, 403):
        raise SearchError("The search API rejected the key or the quota is exhausted.")
    if r.status_code == 429:
        raise SearchError("The search API rate limit was reached. Try again later.")
    if r.status_code >= 400:
        raise SearchError(f"The search API returned HTTP {r.status_code}.")

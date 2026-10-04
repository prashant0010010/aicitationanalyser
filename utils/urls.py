"""URL helpers: normalisation, hostnames and registrable domains."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

# Common two-part public suffixes so "bbc.co.uk" resolves to "bbc.co.uk" rather than "co.uk".
_TWO_PART_SUFFIXES = {
    "co.nz", "org.nz", "net.nz", "govt.nz", "ac.nz", "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "co.in", "co.jp", "com.sg", "co.za", "com.br",
}
_URL_RE = re.compile(r"https?://[^\s<>\")\]]+", re.I)


def normalize_url(url: str) -> str:
    """Add a scheme when missing and strip fragments and whitespace."""
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path or "/", p.params, p.query, ""))


def hostname(url: str) -> str:
    try:
        host = urlparse(url if "://" in url else "https://" + url).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def registrable_domain(url_or_host: str) -> str:
    host = hostname(url_or_host)
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if ".".join(parts[-2:]) in _TWO_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def same_site(a: str, b: str) -> bool:
    da, db = registrable_domain(a), registrable_domain(b)
    return bool(da) and da == db


def domain_stem(url_or_host: str) -> str:
    """'https://www.example.co.nz' becomes 'example'."""
    dom = registrable_domain(url_or_host)
    return dom.split(".")[0] if dom else ""


def extract_urls(text: str) -> list[str]:
    seen, out = set(), []
    for m in _URL_RE.findall(text or ""):
        u = m.rstrip(".,;:")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_url_lines(text: str) -> list[str]:
    """One URL per line or whitespace separated. Invalid lines are dropped later by validation."""
    out, seen = [], set()
    for raw in re.split(r"[\s,]+", text or ""):
        raw = raw.strip()
        if not raw:
            continue
        u = normalize_url(raw)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def first_or_none(items: list[str]) -> Optional[str]:
    return items[0] if items else None

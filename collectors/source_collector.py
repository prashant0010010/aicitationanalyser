"""Collect the target page and external sources into Document objects."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from collectors.url_collector import collect_pasted, collect_url
from config.lexicons import SOURCE_TYPE_RULES
from config.settings import Settings, get_settings
from models.schemas import AnalysisSession, Document
from utils.urls import hostname, registrable_domain, same_site

log = logging.getLogger("citation_analyser.sources")
ProgressFn = Callable[[float, str], None]


def classify_source(doc_url: str, target_site: str = "", competitor_domains: Optional[list[str]] = None) -> str:
    host = hostname(doc_url)
    if not host:
        return "other_web"
    if target_site and same_site(doc_url, target_site):
        return "own_site"
    for cd in competitor_domains or []:
        if cd and same_site(doc_url, cd):
            return "competitor_site"
    for label, needles in SOURCE_TYPE_RULES:
        for n in needles:
            if n.startswith(".") or n.endswith("."):
                if n in "." + host + "." or host.endswith(n.strip(".")) or n in host:
                    return label
            elif n in host:
                return label
    return "other_web"


def collect_all(session: AnalysisSession, settings: Optional[Settings] = None,
                progress: Optional[ProgressFn] = None) -> AnalysisSession:
    """Fetch the target and external sources. Failures are recorded, never raised."""
    s = settings or get_settings()
    p = session.project
    session.errors = []
    steps = 1 + len(p.external_urls[: s.max_external_sources]) + len(p.external_pasted)
    done = 0

    def tick(msg: str) -> None:
        nonlocal done
        done += 1
        if progress:
            progress(min(1.0, done / max(1, steps)), msg)

    # target
    if progress:
        progress(0.0, "Collecting the target page")
    if p.target_pasted.strip():
        doc = collect_pasted(p.target_pasted, label="Pasted target content", kind="target", url=p.target_url or p.website, settings=s)
    elif p.target_url.strip():
        doc = collect_url(p.target_url, kind="target", settings=s)
    else:
        doc = Document(kind="target", ok=False, error="No target URL or pasted content was provided.")
    doc.source_type = "own_site"
    session.target_doc = doc
    if not doc.ok:
        session.errors.append(f"Target: {doc.error}")
    tick("Target page collected" if doc.ok else "Target page failed")

    # external
    comp_domains = [c.domain for c in p.competitors if c.domain]
    docs: list[Document] = []
    for url in p.external_urls[: s.max_external_sources]:
        d = collect_url(url, kind="external", settings=s)
        d.source_type = classify_source(d.url or url, p.website or p.target_url, comp_domains)
        docs.append(d)
        if not d.ok:
            session.errors.append(f"{url}: {d.error}")
        tick(f"Collected {hostname(url) or url}")
    for item in p.external_pasted:
        label = item.get("label") or "Pasted external source"
        d = collect_pasted(item.get("text", ""), label=label, kind="external", url=item.get("url", ""), settings=s)
        d.source_type = classify_source(item.get("url", ""), p.website or p.target_url, comp_domains) if item.get("url") else "other_web"
        docs.append(d)
        if not d.ok:
            session.errors.append(f"{label}: {d.error}")
        tick(f"Collected {label}")
    session.external_docs = docs
    from models.schemas import utcnow

    session.collected_at = utcnow()
    session.touch()
    return session


def registrable(url: str) -> str:
    return registrable_domain(url)

"""Analysis of AI-generated answers supplied by the user.

The module only works from supplied text and citation lists. It never queries
an AI search engine and never invents answers or citations.
"""
from __future__ import annotations

import re
from typing import Optional

from analyzers.entity_analyzer import build_matcher
from collectors.source_collector import classify_source
from config.lexicons import RECOMMEND_CUES, SOURCE_TYPE_LABELS
from models.schemas import AIAnswer, Competitor, Document
from utils.text import snippet_around, split_sentences, truncate
from utils.urls import extract_urls, hostname, normalize_url, registrable_domain, same_site

_MARKER_RE = re.compile(r"\[\d+(?:[,\s]\d+)*\]|\(\s*(?:source|sources|via|per)\b[^)]*\)|\baccording to\b|\(\s*[a-z0-9.-]+\.[a-z]{2,}\s*\)", re.I)
_LIST_LINE_RE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)]|\*\*)\s*")
_REC_RE = [re.compile(p, re.I) for p in RECOMMEND_CUES]


def parse_citations(lines: list[str]) -> list[dict]:
    """Parse citation lines into {rank, url, title, domain}. Lines without a URL are kept as title-only."""
    out: list[dict] = []
    for raw in lines:
        raw = (raw or "").strip()
        if not raw:
            continue
        urls = extract_urls(raw)
        if urls:
            url = urls[0]
            title = re.sub(r"[\s\-:|,]+$", "", raw.replace(url, "")).strip(" -:|,[]()")
            out.append({"url": url, "title": title, "domain": registrable_domain(url)})
        else:
            out.append({"url": "", "title": raw, "domain": ""})
    for i, c in enumerate(out, 1):
        c["rank"] = i
    return out


def analyze_answer(
    answer: AIAnswer, entity: str, website: str, competitors: list[Competitor],
    external_docs: Optional[list[Document]] = None,
) -> dict:
    text = answer.text or ""
    matcher = build_matcher(entity, website)
    matches = matcher.find(text) if entity.strip() else []
    sents = split_sentences(text)
    mention_sents = [s for s in sents if entity.strip() and matcher.present(s)]
    lines = text.splitlines()
    in_list = any(entity.strip() and matcher.present(l) and _LIST_LINE_RE.match(l) for l in lines)
    recommended = [s for s in mention_sents if any(r.search(s) for r in _REC_RE)]
    if not matches:
        mtype = "absent"
    elif recommended:
        mtype = "recommended"
    elif in_list:
        mtype = "listed"
    else:
        mtype = "mentioned"
    cites = parse_citations(answer.citations)
    comp_domains = [c.domain for c in competitors if c.domain]
    ext_urls = {normalize_url(d.url).rstrip("/"): d for d in (external_docs or []) if d.url}
    cited = []
    for c in cites:
        is_target = bool(c["url"]) and same_site(c["url"], website) if website else False
        if not is_target and entity.strip() and c["title"] and matcher.present(c["title"]) and not c["url"]:
            is_target = True
        is_comp = bool(c["url"]) and any(same_site(c["url"], d) for d in comp_domains)
        stype = classify_source(c["url"], website, comp_domains) if c["url"] else "other_web"
        doc = ext_urls.get(normalize_url(c["url"]).rstrip("/")) if c["url"] else None
        cited.append({
            "rank": c["rank"], "url": c["url"], "title": c["title"], "domain": c["domain"],
            "source_type": stype, "is_target": is_target, "is_competitor": is_comp,
            "mentions_target": (matcher.present(doc.text) if doc and doc.ok and entity.strip() else None),
        })
    target_ranks = [c["rank"] for c in cited if c["is_target"]]
    marked = [s for s in mention_sents if _MARKER_RE.search(s)]
    comp_mentions = {}
    for c in competitors:
        n = build_matcher(c.name, c.domain).count(text) if c.name else 0
        if n:
            comp_mentions[c.name] = n
    ext_domains = {registrable_domain(d.url) for d in (external_docs or []) if d.url}
    cited_domains = {c["domain"] for c in cited if c["domain"]}
    return {
        "label": answer.label or "AI answer", "query": answer.query,
        "entity_mentioned": bool(matches), "mention_count": len(matches),
        "first_position_pct": round(matches[0].start() / max(1, len(text)) * 100, 1) if matches else None,
        "mention_type": mtype,
        "contexts": [snippet_around(text, m.start(), m.end()) for m in matches[:3]],
        "cited": bool(target_ranks), "citation_ranks": target_ranks,
        "citation_prominence": round(1.0 / min(target_ranks), 3) if target_ranks else 0.0,
        "citation_count": len(cited), "cited_sources": cited,
        "competitor_mentions": comp_mentions,
        "competitors_cited": [c["domain"] for c in cited if c["is_competitor"]],
        "attributable_ratio": (round(len(marked) / len(mention_sents), 2) if mention_sents else None),
        "unattributed_mentions": [truncate(s, 180) for s in mention_sents if not _MARKER_RE.search(s)][:3],
        "source_overlap_with_supplied": sorted(cited_domains & ext_domains),
        "cited_domains_not_mentioning_target": sorted({c["domain"] for c in cited if c["domain"] and c["mentions_target"] is False}),
        "cited_domains_unchecked": sorted({c["domain"] for c in cited if c["domain"] and c["mentions_target"] is None and not c["is_target"]}),
        "type_counts": {SOURCE_TYPE_LABELS.get(t, t): sum(1 for c in cited if c["source_type"] == t) for t in {c["source_type"] for c in cited}},
    }


def analyze_answers(answers: list[AIAnswer], entity: str, website: str, competitors: list[Competitor],
                    external_docs: Optional[list[Document]] = None) -> list[dict]:
    return [analyze_answer(a, entity, website, competitors, external_docs) for a in answers if (a.text or "").strip()]

"""Pillar 2: Fact and Information Density (metrics 5 to 8).

Fact extraction is deterministic (regular expressions). An LLM may add
suggested subtopics for coverage, but no score depends on an LLM being present.
"""
from __future__ import annotations

import re
from collections import Counter

from analyzers.base import AnalysisContext, clamp, make_metric, scale, unavailable, verdict
from config.lexicons import (ATTRIBUTION_PATTERNS, FACET_SETS, FILLER_PHRASES, ORG_SUFFIXES,
                             SUPERLATIVE_CUES)
from config.scoring import CALIBRATION
from utils.query import query_phrases, query_terms
from utils.text import content_terms, light_stem, split_sentences, stem_set, truncate, word_count

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
FACT_PATTERNS: dict[str, re.Pattern] = {
    "percentage": re.compile(r"\b\d+(?:\.\d+)?\s?%"),
    "currency": re.compile(r"(?:NZ\$|A\$|US\$|[$€£])\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|bn|million|billion))?|\b\d[\d,]*(?:\.\d+)?\s?(?:dollars|euros|pounds|NZD|USD|AUD)\b", re.I),
    "date": re.compile(rf"\b{_MONTH}\.?\s+(?:\d{{1,2}},?\s+)?(?:19|20)\d{{2}}\b|\b(?:19|20)\d{{2}}\b|\b\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}\b"),
    "measurement": re.compile(r"\b\d[\d,]*(?:\.\d+)?\s?(?:GB|MB|TB|KB|GHz|MHz|kg|km|cm|mm|lbs?|oz|hrs?|hours|minutes|mins|days|weeks|months|years|users|customers|employees|countries|locations|integrations|seats|licen[cs]es|reviews|ratings|stars|x)\b", re.I),
    "quantity": re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\s?(?:million|billion|thousand)\b", re.I),
    "definition": re.compile(r"\b[A-Z][\w&'’\- ]{1,40}?\s(?:is|are|refers to|means|stands for)\s(?:a|an|the)\b"),
    "comparison": re.compile(r"\b(?:better than|faster than|cheaper than|more\s+\w+\s+than|less\s+\w+\s+than|compared (?:to|with)|versus|vs\.?)\b", re.I),
    "named_organisation": re.compile(r"\b[A-Z][\w&'’\-]+(?:\s+[A-Z][\w&'’\-]+)*\s+(?:" + "|".join(sorted(s.capitalize() for s in ORG_SUFFIXES)) + r")\b"),
}
_ATTR_RE = [re.compile(p, re.I) for p in ATTRIBUTION_PATTERNS]
_SUPER_RE = [re.compile(p, re.I) for p in SUPERLATIVE_CUES]
_CLAIM_NUM = ("percentage", "currency", "quantity", "measurement")
_REF_HEAD = re.compile(r"\b(references|sources|citations|further reading|bibliography|footnotes)\b", re.I)


def _fact_hits(sentence: str) -> dict[str, int]:
    return {k: len(p.findall(sentence)) for k, p in FACT_PATTERNS.items() if p.search(sentence)}


def information_density(ctx: AnalysisContext):
    doc, eng = ctx.doc, ctx.engine
    if doc.word_count < 30:
        return unavailable(5, "Fewer than 30 words of content were found.")
    sents = split_sentences(doc.text)
    sents = [s for s in sents if word_count(s) >= 4]
    if not sents:
        return unavailable(5, "No full sentences were found.")
    informative, weak = 0, []
    for s in sents:
        mid_caps = re.search(r"(?<=[a-z,;] )[A-Z][a-zA-Z]{2,}", s)
        if re.search(r"\d", s) or mid_caps:
            informative += 1
        elif word_count(s) >= 12:
            weak.append(s)
    inf_ratio = informative / len(sents)
    sem_share = None
    sem_score = 50.0
    if ctx.query.strip():
        sims = eng.similarity([ctx.query], sents)[0]
        sem_share = float((sims >= eng.relevance_threshold).mean())
        sem_score = scale(sem_share, 0.1, 0.6)
        weak.sort(key=lambda s: float(sims[sents.index(s)]))
    low = doc.text.lower()
    fills = {p: low.count(p) for p in FILLER_PHRASES if p in low}
    per_1000 = sum(fills.values()) / max(1, doc.word_count) * 1000
    filler_score = 100 - min(100.0, per_1000 * 25)
    terms = content_terms(doc.text)[:1000]
    ttr = len(set(terms)) / len(terms) if terms else 0
    comp = {"informative_sentences": 0.40 * scale(inf_ratio, 0.15, 0.6), "semantic_density": 0.25 * sem_score,
            "absence_of_filler": 0.20 * filler_score, "lexical_diversity": 0.15 * scale(ttr, 0.35, 0.7)}
    score = sum(comp.values())
    ev = [f"{informative} of {len(sents)} sentences ({inf_ratio*100:.0f}%) carry a figure or a named entity.",
          (f"Semantic density: {sem_share*100:.0f}% of sentences are relevant to the query ({eng.backend} similarity)." if sem_share is not None else "No query was set, so semantic density was not measured."),
          f"Filler phrases: {sum(fills.values())} found ({per_1000:.1f} per 1,000 words)" + (": " + ", ".join(f"'{k}' x{v}" for k, v in list(fills.items())[:4]) if fills else "."),
          f"Lexical diversity (type-token ratio over the first 1,000 content terms): {ttr:.2f}."]
    for s in weak[:2]:
        ev.append("Low-information sentence: " + truncate(s, 150))
    recs = []
    if fills:
        recs.append("Remove generic phrasing (" + ", ".join(f"'{k}'" for k in list(fills)[:3]) + ") and replace it with the specific claim, number or example it stands in for.")
    if inf_ratio < 0.4:
        recs.append(f"Only {inf_ratio*100:.0f}% of sentences contain a figure or named entity. Add concrete specifics (numbers, names, dates, versions) to the paragraphs that currently speak in general terms.")
    if sem_share is not None and sem_share < 0.3:
        recs.append("Under a third of sentences relate to the query. Cut or relocate material that does not help answer it.")
    interp = f"Information density is {verdict(score)}. " + ("Most sentences add specific information." if score >= 70 else "A large share of the text is general or off-query, which dilutes the citable material.")
    return make_metric(5, score, raw={"informative_ratio": round(inf_ratio, 3), "filler_per_1000": round(per_1000, 2), "ttr": round(ttr, 3), "semantic_share": sem_share},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def fact_density(ctx: AnalysisContext):
    doc = ctx.doc
    if doc.word_count < 30:
        return unavailable(6, "Fewer than 30 words of content were found.")
    sents = split_sentences(doc.text)
    cat_counter: Counter = Counter()
    fact_sents: list[tuple[int, str, list[str]]] = []
    items = 0
    for s in sents:
        hits = _fact_hits(s)
        if hits:
            cats = list(hits)
            items += len(cats)
            cat_counter.update(cats)
            fact_sents.append((len(cats), s, cats))
    per100 = items / max(1, doc.word_count) * 100
    target = CALIBRATION["fact_density_target_per_100_words"]
    variety = min(1.0, len(cat_counter) / 5)
    comp = {"fact_items_per_100_words": 0.80 * min(100.0, per100 / target * 100), "fact_type_variety": 0.20 * variety * 100}
    score = sum(comp.values())
    top = sorted(fact_sents, key=lambda x: -x[0])[:4]
    ev = [f"{items} fact items in {len(fact_sents)} of {len(sents)} sentences: {per100:.2f} per 100 words (full score at {target:g}).",
          "By type: " + (", ".join(f"{k} {v}" for k, v in cat_counter.most_common()) or "none detected") + "."]
    for _, s, cats in top:
        ev.append(f"Fact ({', '.join(cats)}): " + truncate(s, 170))
    recs = []
    missing = [k for k in ("percentage", "currency", "date", "measurement", "comparison") if k not in cat_counter]
    if per100 < target * 0.6:
        recs.append(f"Fact density is {per100:.2f} per 100 words against a target of {target:g}. Replace qualitative statements with checkable specifics such as figures, dates, prices and named comparisons.")
    if missing:
        recs.append("No " + ", ".join(missing[:3]) + " statements were detected. Add them where they are true and relevant to the query, for example pricing, dates and quantified outcomes.")
    interp = f"Fact density is {verdict(score)}. " + ("The page carries many concrete, checkable statements." if score >= 70 else "The page is mostly descriptive, so answer engines have few concrete statements to attribute to it.")
    return make_metric(6, score, raw={"fact_items": items, "per_100_words": round(per100, 2), "by_type": dict(cat_counter)},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def evidence_attribution(ctx: AnalysisContext):
    doc = ctx.doc
    claims, attributed, unattributed = 0, 0, []
    attributed_ex = []
    for para, ext in zip(doc.paragraphs, doc.para_links or [0] * len(doc.paragraphs)):
        for s in split_sentences(para):
            hits = _fact_hits(s)
            is_claim = any(k in hits for k in _CLAIM_NUM) or any(r.search(s) for r in _SUPER_RE)
            if not is_claim:
                continue
            claims += 1
            if ext > 0 or any(r.search(s) for r in _ATTR_RE):
                attributed += 1
                if len(attributed_ex) < 2:
                    attributed_ex.append(s)
            else:
                unattributed.append(s)
    if claims == 0:
        return unavailable(7, "No quantitative or superlative claims were detected, so attribution cannot be assessed.")
    ext_domains = {l["href"].split("/")[2].lower().removeprefix("www.") for l in doc.links if l.get("external") and l["href"].startswith("http") and len(l["href"].split("/")) > 2}
    ref = any(_REF_HEAD.search(h["text"]) for h in doc.headings)
    ratio = attributed / claims
    comp = {"attributed_claims": 0.60 * ratio * 100, "source_domains": 0.25 * min(1.0, len(ext_domains) / 5) * 100, "references_section": 0.15 * (100 if ref else 0)}
    score = sum(comp.values())
    ev = [f"{attributed} of {claims} claim sentences ({ratio*100:.0f}%) carry an attribution cue or an outbound link in the same paragraph.",
          f"{len(ext_domains)} distinct external domain(s) linked from the content" + (": " + ", ".join(sorted(ext_domains)[:5]) if ext_domains else ".") + f" References section: {'yes' if ref else 'no'}."]
    for s in unattributed[:3]:
        ev.append("Unattributed claim: " + truncate(s, 160))
    for s in attributed_ex[:1]:
        ev.append("Attributed claim: " + truncate(s, 160))
    recs = []
    if unattributed:
        recs.append(f"{len(unattributed)} claim(s) have no visible source. Name the source and year beside each (for example 'According to [publisher], 2025') and link to it. Start with: '{truncate(unattributed[0], 90)}'")
    if len(ext_domains) < 3:
        recs.append("Link to primary sources (studies, standards bodies, regulators or original data) rather than relying on unlinked assertions.")
    if not ref:
        recs.append("Add a short Sources or References section listing the evidence behind the page's main claims.")
    interp = f"Evidence attribution is {verdict(score)}. " + ("Most claims can be traced to a source." if score >= 70 else "Many claims would be treated as unsupported assertions.")
    return make_metric(7, score, raw={"claims": claims, "attributed": attributed, "external_domains": len(ext_domains)},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


# ------------------------------------------------------------------ coverage
def build_facets(query: str, intent: str, extra: list[str] | None = None) -> list[dict]:
    """Build a query-adaptive facet list: intent facets, query concepts and optional extras."""
    base = FACET_SETS.get(intent) or FACET_SETS["informational"]
    facets = [{"name": n, "keywords": list(k), "origin": f"{intent} intent"} for n, k in base]
    for ph in query_phrases(query):
        words = ph.split()
        words[-1] = light_stem(words[-1])
        facets.append({"name": f"Query concept: {ph}", "keywords": [" ".join(words)], "origin": "query phrase"})
    existing = {f["name"].lower() for f in facets}
    for e in extra or []:
        e = e.strip()
        if e and e.lower() not in existing:
            kws = [light_stem(w) for w in content_terms(e)][:5] or [e.lower()]
            facets.append({"name": e, "keywords": kws, "origin": "AI suggestion"})
            existing.add(e.lower())
    return facets


def _kw_regex(kw: str) -> re.Pattern:
    """Word-start match so 'vs' does not match 'canvas' and 'feature' matches 'features'."""
    k = re.escape(kw.lower())
    return re.compile((r"\b" if kw[:1].isalnum() else "") + k, re.I)


def information_coverage(ctx: AnalysisContext):
    doc, eng = ctx.doc, ctx.engine
    if not ctx.query.strip():
        return unavailable(8, "No target query was defined.")
    passages = doc.passages(min_words=8)
    if not passages:
        return unavailable(8, "No passages of sufficient length were found.")
    facets = build_facets(ctx.query, ctx.intent, ctx.extra_subtopics)
    texts = [(p["heading"] + ". " + p["text"]).strip() for p in passages]
    probes = [f"{ctx.query} {f['name'].split(':')[-1].strip()} " + " ".join(f["keywords"][:4]) for f in facets]
    sims = eng.similarity(probes, texts)
    heads = [h["text"].lower() for h in doc.headings]
    results, covered_total = [], 0.0
    for fi, f in enumerate(facets):
        pats = [_kw_regex(k) for k in f["keywords"]]
        hits_idx = [i for i, t in enumerate(texts) if any(p.search(t) for p in pats)]
        head_hit = any(any(p.search(h) for p in pats) for h in heads)
        row = sims[fi]
        best = int(row.argmax())
        best_sim = float(row[best])
        kw_sim = max((float(row[i]) for i in hits_idx), default=0.0)
        if (hits_idx and head_hit) or len(hits_idx) >= 2 and kw_sim >= eng.coverage_low or best_sim >= eng.coverage_high:
            level = "full"
        elif hits_idx or head_hit or best_sim >= eng.coverage_low:
            level = "partial"
        else:
            level = "none"
        f.update({"level": level, "best_similarity": round(best_sim, 3), "keyword_passages": len(hits_idx),
                  "heading_match": head_hit, "evidence": truncate(passages[best]["text"], 150) if level != "none" else ""})
        results.append(f)
    covered_total = sum({"full": 1.0, "partial": 0.5, "none": 0.0}[f["level"]] for f in results)
    score = covered_total / len(facets) * 100
    ctx.shared["facets"] = results
    full = [f["name"] for f in results if f["level"] == "full"]
    part = [f["name"] for f in results if f["level"] == "partial"]
    none = [f["name"] for f in results if f["level"] == "none"]
    ev = [f"{len(facets)} subtopics assessed for intent '{ctx.intent}' ({eng.backend} similarity plus keyword evidence): {len(full)} covered, {len(part)} partial, {len(none)} missing.",
          "Covered: " + ("; ".join(full) or "none"), "Partial: " + ("; ".join(part) or "none"), "Missing: " + ("; ".join(none) or "none")]
    recs = []
    if none:
        recs.append("Add sections for the missing subtopics: " + "; ".join(none[:5]) + ". Give each its own heading and a self-contained paragraph with specifics.")
    if part:
        recs.append("Strengthen the partially covered subtopics (" + "; ".join(part[:4]) + ") with a dedicated heading and at least one concrete fact each.")
    interp = f"Information coverage is {verdict(score)}: {len(full)} of {len(facets)} expected subtopics are fully addressed." + (" The list was extended with AI-suggested subtopics." if ctx.extra_subtopics else "")
    return make_metric(8, score, raw={"facets": len(facets), "full": len(full), "partial": len(part), "missing": len(none)},
                       evidence=ev, interpretation=interp, recommendations=recs, components={"coverage_pct": score})


METRICS = {5: information_density, 6: fact_density, 7: evidence_attribution, 8: information_coverage}

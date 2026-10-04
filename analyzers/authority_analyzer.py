"""Pillar 4: Cross-Platform Authority (metrics 13 to 16).

Only supplied sources and AI answers are used. No domain authority, backlink
counts or traffic figures are invented. Where evidence is missing the metric
is reported as unavailable.
"""
from __future__ import annotations

from analyzers.base import AnalysisContext, make_metric, unavailable, verdict
from analyzers.citation_analyzer import analyze_answers
from analyzers.entity_analyzer import prepare
from config.lexicons import SOURCE_TYPE_LABELS
from config.scoring import CALIBRATION, INTENT_VALUE
from utils.text import snippet_around, truncate
from utils.urls import registrable_domain, same_site


def _ok_external(ctx: AnalysisContext):
    return [d for d in ctx.external if d.ok]


def external_summary(ctx: AnalysisContext) -> list[dict]:
    """Per-source mention analysis, computed once and cached in ctx.shared."""
    if "external_summary" in ctx.shared:
        return ctx.shared["external_summary"]
    prepare(ctx)
    rows = []
    for d in ctx.external:
        row = {"label": d.label, "url": d.url, "source_type": d.source_type or "other_web", "ok": d.ok, "error": d.error,
               "words": d.word_count, "mentions": 0, "context": "", "links_to_target": False, "prominent": False,
               "relevance": None, "date": d.published or d.modified or ""}
        if d.ok:
            ms = ctx.matcher.find(d.text) if ctx.entity.strip() else []
            row["mentions"] = len(ms)
            if ms:
                row["context"] = snippet_around(d.text, ms[0].start(), ms[0].end())
            row["links_to_target"] = any(l.get("href", "").startswith("http") and ctx.website and same_site(l["href"], ctx.website) for l in d.links)
            first100 = " ".join(d.text.split()[:100])
            row["prominent"] = bool(ms) and (ctx.matcher.present(d.title) or any(ctx.matcher.present(h["text"]) for h in d.headings) or ctx.matcher.present(first100))
            ps = d.passages(min_words=8)
            if ps and ctx.query.strip():
                sims = ctx.engine.similarity([ctx.query], [p["text"] for p in ps])[0]
                top = sorted((float(x) for x in sims), reverse=True)[:3]
                row["relevance"] = round(sum(top) / len(top), 3)
        rows.append(row)
    ctx.shared["external_summary"] = rows
    return rows


def third_party_mentions(ctx: AnalysisContext):
    if not ctx.entity.strip():
        return unavailable(13, "No target entity was defined.")
    docs = _ok_external(ctx)
    if not docs:
        return unavailable(13, "Requires external sources. No external URLs or pasted sources were collected.",
                           "Supply external pages (reviews, news, directories, community threads) that discuss the entity so third-party corroboration can be measured.")
    rows = [r for r in external_summary(ctx) if r["ok"]]
    mentioning = [r for r in rows if r["mentions"] > 0]
    full_at = CALIBRATION["external_sources_for_full_mentions"]
    n = len(mentioning)
    link_share = (sum(1 for r in mentioning if r["links_to_target"]) / n) if n else 0.0
    prom_share = (sum(1 for r in mentioning if r["prominent"]) / n) if n else 0.0
    comp = {"sources_mentioning": 0.60 * min(1.0, n / full_at) * 100, "links_to_entity_site": 0.20 * link_share * 100,
            "prominent_mentions": 0.20 * prom_share * 100}
    score = sum(comp.values())
    ev = [f"{n} of {len(rows)} readable external source(s) mention '{ctx.entity}' (full score at {full_at} mentioning sources)."]
    for r in mentioning[:4]:
        ev.append(f"{r['label'] or r['url']} ({SOURCE_TYPE_LABELS.get(r['source_type'], r['source_type'])}, {r['mentions']} mention(s)): " + truncate(r["context"], 170))
    silent = [r for r in rows if r["mentions"] == 0]
    if silent:
        ev.append("No mention found in: " + "; ".join(truncate(r["label"] or r["url"], 50) for r in silent[:4]))
    recs = []
    if silent:
        recs.append(f"{len(silent)} supplied source(s) discuss the topic without naming '{ctx.entity}'. Treat them as outreach and inclusion targets: " + "; ".join(truncate(r["label"] or r["url"], 45) for r in silent[:3]) + ".")
    if n and link_share < 0.5:
        recs.append("Mentions mostly do not link to the entity's website. Where mentions are earned, ask for a link to the specific page that supports the claim.")
    if n < full_at:
        recs.append(f"Only {n} mentioning source(s) were supplied. Broaden the source set to at least {full_at} independent pages before drawing conclusions.")
    interp = f"Third-party corroboration is {verdict(score)} within the supplied source set ({len(rows)} readable source(s)). This is not a measure of the entity's total web footprint."
    return make_metric(13, score, raw={"mentioning": n, "supplied": len(rows)}, evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def source_diversity(ctx: AnalysisContext):
    if not ctx.entity.strip():
        return unavailable(14, "No target entity was defined.")
    docs = _ok_external(ctx)
    if not docs:
        return unavailable(14, "Requires external sources. No external URLs or pasted sources were collected.",
                           "Supply external pages of different kinds (news, review sites, community threads, directories) to measure diversity.")
    rows = [r for r in external_summary(ctx) if r["ok"] and r["mentions"] > 0 and r["source_type"] not in ("own_site", "competitor_site")]
    types = {r["source_type"] for r in rows}
    domains = {registrable_domain(r["url"]) for r in rows if r["url"]}
    comp = {"source_types": 0.5 * min(1.0, len(types) / CALIBRATION["source_types_for_full_diversity"]) * 100,
            "domains": 0.5 * min(1.0, len(domains) / CALIBRATION["domains_for_full_diversity"]) * 100}
    score = sum(comp.values())
    ev = [f"{len(types)} source type(s) and {len(domains)} registrable domain(s) among {len(rows)} independent mentioning source(s).",
          "Types present: " + (", ".join(SOURCE_TYPE_LABELS.get(t, t) for t in sorted(types)) or "none")]
    missing = [SOURCE_TYPE_LABELS[t] for t in ("news_media", "review_directory", "community_forum", "encyclopaedia", "academic_government") if t not in types]
    ev.append("Types not represented: " + ", ".join(missing))
    recs = []
    if missing:
        recs.append("The entity is not represented in these source types in the supplied set: " + ", ".join(missing[:3]) + ". Prioritise the types most relevant to the query (review or comparison sites for commercial queries, community threads for experiential ones).")
    if len(domains) < 3:
        recs.append("Mentions are concentrated on very few domains. Aim for mentions on at least three independent domains.")
    interp = f"Source diversity is {verdict(score)} within the supplied set. Source types are classified by domain rules, so unusual domains may be labelled 'Other web source'."
    return make_metric(14, score, raw={"types": sorted(types), "domains": sorted(domains)}, evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def citation_share(ctx: AnalysisContext):
    ans = ctx.answer_analyses
    if not ans:
        return unavailable(15, "Requires AI answers. No AI answer text was supplied.",
                           "Paste real AI answers for the target query, with their citation lists, to measure citation share.")
    total_cites = sum(a["citation_count"] for a in ans)
    target_cites = sum(1 for a in ans for c in a["cited_sources"] if c["is_target"])
    cite_share = (target_cites / total_cites) if total_cites else None
    m_t = sum(a["mention_count"] for a in ans)
    m_c = sum(sum(a["competitor_mentions"].values()) for a in ans)
    mention_share = (m_t / (m_t + m_c)) if (ctx.competitors and (m_t + m_c) > 0) else None
    full = CALIBRATION["citation_share_full_score_at"]
    parts, weights = [], []
    if cite_share is not None:
        parts.append(min(100.0, cite_share / full * 100)); weights.append(0.6)
    if mention_share is not None:
        parts.append(min(100.0, mention_share / full * 100)); weights.append(0.4)
    if not parts:
        return unavailable(15, "The supplied answers have no citation lists and no competitors were defined, so no share can be computed.",
                           "Add the citation list shown with each AI answer and name competitors to enable share calculations.")
    score = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
    ev = [f"{len(ans)} AI answer(s) supplied with {total_cites} citation(s) in total."]
    if cite_share is not None:
        ev.append(f"Citation share: {target_cites} of {total_cites} citations point to the target site ({cite_share*100:.0f}%).")
    if mention_share is not None:
        ev.append(f"Mention share: {m_t} target mention(s) against {m_c} competitor mention(s) ({mention_share*100:.0f}%).")
    cited_answers = sum(1 for a in ans if a["cited"])
    ev.append(f"The entity's site is cited in {cited_answers} of {len(ans)} answer(s) and named in {sum(1 for a in ans if a['entity_mentioned'])}.")
    recs = []
    if cite_share is not None and cite_share < full:
        top_other = {}
        for a in ans:
            for c in a["cited_sources"]:
                if c["domain"] and not c["is_target"]:
                    top_other[c["domain"]] = top_other.get(c["domain"], 0) + 1
        leaders = sorted(top_other.items(), key=lambda kv: -kv[1])[:3]
        recs.append("Study the pages that are cited instead: " + ", ".join(f"{d} ({n}x)" for d, n in leaders) + ". Compare their structure, facts and evidence with the target page and close the gaps that metrics 1 to 8 expose.")
    if m_t == 0 and ans:
        recs.append("The entity is not named in any supplied answer. Strengthen entity clarity and third-party corroboration so it becomes a candidate for inclusion.")
    interp = (f"Within the {len(ans)} supplied answer(s), the entity holds a {verdict(score)} share position. "
              "This reflects only the answers supplied, not the whole answer space.")
    status = "measured" if cite_share is not None else "proxy"
    return make_metric(15, score, raw={"citation_share": cite_share, "mention_share": mention_share, "answers": len(ans)},
                       evidence=ev, interpretation=interp, recommendations=recs, status=status,
                       components={"citation_share_score": parts[0] if cite_share is not None else None})


def citation_value(ctx: AnalysisContext):
    iv = INTENT_VALUE.get(ctx.intent, 0.6)
    s = ctx.shared.get("scores", {})
    rel_parts = [s[i] for i in (9, 12) if s.get(i) is not None]
    components, weights, ev = {}, {}, []
    components["intent_value"], weights["intent_value"] = iv * 100, 0.40
    ev.append(f"Query intent classified as '{ctx.intent}' (intent value {iv:.2f}). Industry: {ctx.industry or 'not stated'}; market: {ctx.market or 'not stated'}.")
    if rel_parts:
        components["entity_relevance"], weights["entity_relevance"] = sum(rel_parts) / len(rel_parts), 0.30
        ev.append(f"Entity relevance from metrics 9 and 12: {components['entity_relevance']:.0f}/100.")
    rows = [r for r in external_summary(ctx) if r["ok"] and r["relevance"] is not None] if ctx.external else []
    if rows:
        rel = sum(ctx.engine.sim_to_score(r["relevance"]) for r in rows) / len(rows)
        components["source_relevance"], weights["source_relevance"] = rel, 0.15
        ev.append(f"Mean relevance of {len(rows)} supplied external source(s) to the query: {rel:.0f}/100.")
    if ctx.answer_analyses:
        prom = max((a["citation_prominence"] for a in ctx.answer_analyses), default=0.0)
        components["citation_prominence"], weights["citation_prominence"] = prom * 100, 0.15
        ev.append(f"Best citation prominence in supplied answers: {prom:.2f} (1.00 means first citation).")
    score = sum(components[k] * weights[k] for k in components) / sum(weights.values())
    ev.append("Search volume, traffic and conversion data are not used. This is an estimate of strategic value, not a forecast.")
    recs = []
    if iv >= 0.85 and (components.get("entity_relevance", 0) < 60):
        recs.append(f"This is a high-value '{ctx.intent}' query but entity relevance is only {components.get('entity_relevance', 0):.0f}/100. Prioritise the recommendations on metrics 9, 10 and 12 for this query first.")
    if iv < 0.6:
        recs.append("The query has lower commercial value. Weigh effort against value, and consider testing commercial-intent variants of the query.")
    interp = f"Estimated citation value is {verdict(score)}. It combines query intent with how relevant the entity currently is, and is an estimate only."
    return make_metric(16, score, raw={"intent": ctx.intent, "intent_value": iv}, evidence=ev, interpretation=interp,
                       recommendations=recs, status="estimate", components=components)


METRICS = {13: third_party_mentions, 14: source_diversity, 15: citation_share, 16: citation_value}

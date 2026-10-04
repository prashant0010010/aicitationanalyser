"""Evidence-linked recommendations, priority scoring and opportunity grouping."""
from __future__ import annotations

from typing import Optional

from config.scoring import (EVIDENCE_STRENGTH, INTENT_VALUE, METRICS, PRIORITY_THRESHOLDS, PRIORITY_WEIGHTS,
                            RECOMMENDATION_SCORE_THRESHOLD)
from models.schemas import MetricResult, Recommendation


def _priority_label(score: float) -> str:
    if score >= PRIORITY_THRESHOLDS["High"]:
        return "High"
    if score >= PRIORITY_THRESHOLDS["Medium"]:
        return "Medium"
    return "Low"


def build_recommendations(metrics: list[MetricResult], intent: str, entity_relevance: Optional[float]) -> list[Recommendation]:
    """One recommendation per weak metric. The priority formula is in config/scoring.py."""
    max_w = max(m["weight"] for m in METRICS.values())
    qi = INTENT_VALUE.get(intent, 0.6)
    er = (entity_relevance if entity_relevance is not None else 50.0) / 100.0
    recs: list[Recommendation] = []
    for m in metrics:
        if not m.available or m.score >= RECOMMENDATION_SCORE_THRESHOLD or not m.recommendations:
            continue
        meta = METRICS[m.id]
        factors = {
            "weakness": (100 - m.score) / 100,
            "impact": meta["weight"] / max_w,
            "query_importance": qi,
            "entity_relevance": er,
            "effort": {1: 1.0, 2: 0.6, 3: 0.3}[meta["effort"]],
            "evidence_strength": EVIDENCE_STRENGTH.get(m.status, 0.5),
        }
        ps = sum(factors[k] * PRIORITY_WEIGHTS[k] for k in PRIORITY_WEIGHTS)
        label = _priority_label(ps)
        horizon = "Immediate" if (meta["effort"] == 1 and label != "Low") else ("Strategic" if meta["effort"] == 3 else "Near-term")
        recs.append(Recommendation(
            metric_id=m.id, metric_name=m.name, category=meta["category"], score=m.score, status=m.status,
            evidence=m.evidence[:2], why=meta["why"], action=m.recommendations[:3], effect=meta["effect"],
            priority=label, priority_score=round(ps, 3), factors={k: round(v, 2) for k, v in factors.items()},
            effort=meta["effort"], horizon=horizon,
        ))
    recs.sort(key=lambda r: -r.priority_score)
    return recs


def evidence_gaps(metrics: list[MetricResult]) -> list[str]:
    gaps = []
    for m in metrics:
        if not m.available:
            need = METRICS[m.id]["needs"]
            gaps.append(f"Metric {m.id} ({m.name}) is not scored. {m.evidence[0] if m.evidence else ''} Needs: {need}.".strip())
    return gaps


def build_opportunities(recs: list[Recommendation], answer_analyses: list[dict], external_summary: list[dict],
                        entity: str) -> dict[str, list[dict]]:
    """Group recommendations by category and add citation opportunities derived from real supplied data."""
    out: dict[str, list[dict]] = {k: [] for k in ("citation", "content", "entity", "authority", "technical")}
    for r in recs:
        out.setdefault(r.category, []).append({
            "title": f"{r.metric_name} (score {r.score:.0f})", "evidence": r.evidence, "why": r.why,
            "action": r.action, "priority": r.priority, "source": "metric",
        })
    # citation opportunities from supplied AI answers
    if answer_analyses:
        absent = [a for a in answer_analyses if not a["entity_mentioned"]]
        not_cited = [a for a in answer_analyses if not a["cited"]]
        if absent:
            out["citation"].append({
                "title": f"{entity} is absent from {len(absent)} of {len(answer_analyses)} supplied answer(s)",
                "evidence": [f"Answers without the entity: " + "; ".join((a['label'] or 'answer') for a in absent[:4])],
                "why": "An entity that is not named cannot be recommended. Absence usually reflects weak entity clarity or weak corroboration.",
                "action": ["Compare the pages those answers cite with the target page, and close the gaps in structure, facts and evidence."],
                "priority": "High", "source": "ai_answers"})
        domain_counts: dict[str, int] = {}
        for a in not_cited:
            for c in a["cited_sources"]:
                if c["domain"] and not c["is_target"] and c["mentions_target"] is not True:
                    domain_counts[c["domain"]] = domain_counts.get(c["domain"], 0) + 1
        for d, n in sorted(domain_counts.items(), key=lambda kv: -kv[1])[:5]:
            checked = any(c["domain"] == d and c["mentions_target"] is False for a in answer_analyses for c in a["cited_sources"])
            out["citation"].append({
                "title": f"Cited source without the entity: {d}",
                "evidence": [f"{d} is cited {n} time(s) in answers where the target site is not cited." + (" The supplied copy of the page does not mention the entity." if checked else " The page was not supplied, so mention status is unverified.")],
                "why": "Sources that answers already rely on are the most direct route to being included.",
                "action": [f"Seek inclusion or a factual mention of {entity} on {d} where it is relevant, with a link to a supporting page."],
                "priority": "Medium", "source": "ai_answers"})
        unattrib = [a for a in answer_analyses if a["entity_mentioned"] and a["attributable_ratio"] == 0.0]
        if unattrib:
            out["citation"].append({
                "title": "Mentions without a visible source",
                "evidence": [f"{len(unattrib)} answer(s) name {entity} with no inline citation marker next to the mention."],
                "why": "Unsourced mentions are the weakest form of visibility and may not carry referral value.",
                "action": ["Publish a concise, fact-rich page that directly supports the claims made about the entity so that answers have something to cite."],
                "priority": "Medium", "source": "ai_answers"})
    # authority opportunities from supplied external sources
    silent = [r for r in external_summary if r.get("ok") and r.get("mentions") == 0]
    if silent:
        out["authority"].append({
            "title": f"{len(silent)} relevant source(s) discuss the topic without naming {entity}",
            "evidence": ["; ".join((r["label"] or r["url"])[:60] for r in silent[:4])],
            "why": "These pages already cover the topic. They are plausible places for a corroborating mention.",
            "action": ["Prepare factual, citable material (data, specifications, case evidence) and approach the publishers where inclusion is editorially justified."],
            "priority": "Medium", "source": "external_sources"})
    return out

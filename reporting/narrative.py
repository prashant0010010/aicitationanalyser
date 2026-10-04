"""Deterministic narrative built only from measured results (no generated claims)."""
from __future__ import annotations

from config.scoring import METRICS, PILLARS
from models.schemas import AnalysisSession
from utils.text import ui_clean


def _fmt(score) -> str:
    return "n/a" if score is None else f"{score:.0f}"


def strengths_and_weaknesses(session: AnalysisSession):
    r = session.results
    avail = [m for m in r.metrics if m.available]
    strong = sorted([m for m in avail if m.score >= 75], key=lambda m: -m.score)
    weak = sorted([m for m in avail if m.score < 60], key=lambda m: m.score)
    return strong, weak


def executive_summary(session: AnalysisSession) -> list[str]:
    r, p = session.results, session.project
    sc = r.scoring
    doc = session.target_doc
    n_ext = sum(1 for d in session.external_docs if d.ok)
    out = []
    src = doc.url or doc.label if doc else "supplied content"
    out.append(
        f"This report analyses how clearly and attributably {p.entity} is represented for the query '{p.query}' "
        f"(intent: {r.intent}). The evidence base is one target page ({src}, {doc.word_count if doc else 0} words), "
        f"{n_ext} readable external source(s) and {len(r.answer_analyses)} supplied AI answer(s)."
    )
    if sc["overall"] is not None:
        prov = " The score is provisional because not every pillar could be scored." if sc["provisional"] else ""
        pillar_txt = "; ".join(f"{v['name']} {_fmt(v['score'])}" for v in sc["pillars"].values())
        out.append(f"The Citation Quality Score is {sc['overall']:.0f} out of 100 ({sc['band'].lower()}). Pillar scores: {pillar_txt}.{prov}")
    strong, weak = strengths_and_weaknesses(session)
    if strong:
        out.append("Strongest signals: " + "; ".join(f"{m.name} ({m.score:.0f})" for m in strong[:3]) + ".")
    if weak:
        out.append("Weakest signals: " + "; ".join(f"{m.name} ({m.score:.0f})" for m in weak[:3]) + ".")
    if r.recommendations:
        top = r.recommendations[:3]
        out.append("Largest opportunities, ranked by the priority formula: " + "; ".join(
            f"{x.metric_name} ({x.priority} priority, {x.horizon.lower()})" for x in top) + ".")
        first = top[0]
        out.append(f"Recommended next step: {first.action[0]}")
    if r.evidence_gaps:
        out.append(f"{len(r.evidence_gaps)} metric(s) could not be scored for lack of evidence and are marked as not available rather than estimated.")
    return [ui_clean(x) for x in out]


def action_plan(session: AnalysisSession) -> dict[str, list]:
    plan = {"Immediate": [], "Near-term": [], "Strategic": []}
    for rec in session.results.recommendations:
        plan[rec.horizon].append(rec)
    return plan

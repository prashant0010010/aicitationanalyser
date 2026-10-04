"""End-to-end analysis pipeline: collection output in, scored results out."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from analyzers import authority_analyzer, entity_analyzer, information_analyzer, structural_analyzer
from analyzers.base import AnalysisContext, safe_run
from analyzers.citation_analyzer import analyze_answers
from analyzers.semantic_analyzer import get_engine
from config.scoring import CALIBRATION, METRICS
from config.settings import Settings, get_settings
from core import enhance
from core.recommendations import build_opportunities, build_recommendations, evidence_gaps
from core.scoring import compute_scores
from models.schemas import AnalysisResults, AnalysisSession, QueryResult, utcnow
from providers import ProviderError, get_provider
from utils.query import detect_intent

log = logging.getLogger("citation_analyser.pipeline")
ProgressFn = Callable[[float, str], None]

REGISTRY: dict[int, Callable] = {}
for _mod in (structural_analyzer, information_analyzer, entity_analyzer, authority_analyzer):
    REGISTRY.update(_mod.METRICS)

AI_UNAVAILABLE = "AI enhancement unavailable. Local analysis has been used."


class AnalysisError(Exception):
    """A user-facing analysis problem (for example no readable target content)."""


def build_context(session: AnalysisSession, query: str, settings: Settings, answers, extra_subtopics: Optional[list[str]] = None) -> AnalysisContext:
    p = session.project
    engine = get_engine(settings)
    ctx = AnalysisContext(
        query=query, entity=p.entity, website=p.website or p.target_url, industry=p.industry, market=p.market,
        competitors=p.competitors, doc=session.target_doc, external=session.external_docs, answers=answers,
        engine=engine, settings=settings, intent=detect_intent(query, p.entity), extra_subtopics=extra_subtopics or [],
    )
    ctx.answer_analyses = analyze_answers(answers, p.entity, ctx.website, p.competitors, session.external_docs)
    return ctx


def run_metrics(ctx: AnalysisContext) -> list:
    """Run all 16 metrics in order. A failing metric becomes 'unavailable' and never stops the run."""
    ctx.shared["scores"] = {}
    out = []
    for mid in sorted(METRICS):
        res = safe_run(mid, REGISTRY[mid], ctx)
        ctx.shared["scores"][mid] = res.score
        out.append(res)
    return out


def _answers_for(session: AnalysisSession, query: str, primary: bool):
    q = query.strip().lower()
    return [a for a in session.answers if (a.query.strip().lower() == q) or (primary and not a.query.strip())]


def analyse(session: AnalysisSession, settings: Optional[Settings] = None, progress: Optional[ProgressFn] = None) -> AnalysisResults:
    s = settings or get_settings()
    p = session.project
    doc = session.target_doc

    def tick(f: float, msg: str) -> None:
        if progress:
            progress(f, msg)

    if not doc or not doc.ok:
        raise AnalysisError("The target content has not been collected or could not be read. Return to Source Collection.")
    if doc.word_count < CALIBRATION["min_words_for_analysis"]:
        raise AnalysisError(f"The target content has only {doc.word_count} words. At least {CALIBRATION['min_words_for_analysis']} are needed.")
    if not p.query.strip() or not p.entity.strip():
        raise AnalysisError("A target query and a target entity are required.")

    res = AnalysisResults(generated_at=utcnow(), query=p.query)
    tick(0.05, "Preparing the semantic engine")
    engine = get_engine(s)
    res.semantic_backend, res.semantic_note = engine.backend, engine.note

    # optional AI layer (never required)
    provider = get_provider(s) if session.use_ai else None
    extra: list[str] = []
    if provider is None:
        res.ai_status = AI_UNAVAILABLE if session.use_ai else "AI enhancement was switched off. Local analysis has been used."
    else:
        res.ai_provider = f"{provider.name} ({provider.model})"
        tick(0.12, "Asking the AI provider for query-specific subtopics")
        try:
            extra = enhance.suggest_subtopics(provider, p.query, p.entity, p.industry, p.market)
            res.ai_subtopics = extra
            res.ai_status = f"AI enhancement active ({provider.name}). Used for subtopic suggestions and commentary only. Scores are computed locally."
        except ProviderError as exc:
            res.ai_status = f"AI enhancement failed: {exc} Local analysis has been used."
            provider = None
            log.warning("AI subtopics failed: %s", exc)

    queries = p.all_queries()
    primary_ctx = None
    tick(0.2, "Analysing the primary query")
    for qi, q in enumerate(queries):
        is_primary = qi == 0
        ctx = build_context(session, q, s, _answers_for(session, q, is_primary), extra if is_primary else [])
        metrics = run_metrics(ctx)
        scoring = compute_scores(metrics, session.pillar_weights or None)
        if is_primary:
            primary_ctx = ctx
            res.metrics, res.scoring, res.intent = metrics, scoring, ctx.intent
        by = {m.id: m for m in metrics}
        res.query_set.append(QueryResult(
            query=q, overall=scoring["overall"], is_primary=is_primary,
            pillars={k: v["score"] for k, v in scoring["pillars"].items()},
            key_metrics={"Direct answer": by[1].score, "Coverage": by[8].score, "Contextual relevance": by[12].score},
        ))
        tick(0.2 + 0.5 * (qi + 1) / len(queries), f"Analysed query {qi + 1} of {len(queries)}")

    ctx = primary_ctx
    info = entity_analyzer.prepare(ctx)
    res.entities = [{k: v for k, v in e.items() if k != "sentences"} for e in info["entities"][:40]]
    res.relationships = info["relationships"]
    res.topics = info["topics"]
    res.facets = ctx.shared.get("facets", [])
    res.answer_analyses = ctx.answer_analyses
    res.external_summary = authority_analyzer.external_summary(ctx) if session.external_docs else []

    tick(0.75, "Building recommendations")
    scores = ctx.shared["scores"]
    rel = [scores[i] for i in (9, 12) if scores.get(i) is not None]
    er = sum(rel) / len(rel) if rel else None
    res.recommendations = build_recommendations(res.metrics, ctx.intent, er)
    res.evidence_gaps = evidence_gaps(res.metrics)
    res.opportunities = build_opportunities(res.recommendations, res.answer_analyses, res.external_summary, p.entity)

    if provider is not None:
        tick(0.85, "Requesting AI commentary")
        try:
            payload = {
                "entity": p.entity, "query": p.query, "intent": ctx.intent, "overall": res.scoring["overall"],
                "pillars": {v["name"]: v["score"] for v in res.scoring["pillars"].values()},
                "metrics": [{"id": m.id, "name": m.name, "score": m.score, "evidence": m.evidence[:2]} for m in res.metrics],
            }
            res.ai_commentary = enhance.strategic_commentary(provider, payload)
        except ProviderError as exc:
            res.warnings.append(f"AI commentary was not produced: {exc}")

    failed = [d for d in [session.target_doc, *session.external_docs] if d and not d.ok]
    for d in failed:
        res.warnings.append(f"Source not analysed: {d.label or d.url} ({d.error})")
    if res.scoring["provisional"]:
        res.warnings.extend(res.scoring["notes"])
    session.results = res
    session.analysed_at = utcnow()
    session.touch()
    tick(1.0, "Analysis complete")
    return res

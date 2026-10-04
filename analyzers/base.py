"""Shared analysis context and helpers for all analyzers."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from config.scoring import METRICS
from config.settings import Settings
from models.schemas import AIAnswer, Competitor, Document, MetricResult
from analyzers.semantic_analyzer import SemanticEngine

log = logging.getLogger("citation_analyser.analyzers")


@dataclass
class AnalysisContext:
    query: str
    entity: str
    website: str
    industry: str
    market: str
    competitors: list[Competitor]
    doc: Document
    external: list[Document]
    answers: list[AIAnswer]
    engine: SemanticEngine
    settings: Settings
    intent: str = "informational"
    extra_subtopics: list[str] = field(default_factory=list)
    # filled lazily by entity_analyzer.prepare()
    entity_info: Optional[dict] = None
    matcher: Any = None
    answer_analyses: list[dict] = field(default_factory=list)
    shared: dict[str, Any] = field(default_factory=dict)  # scratch space for cross-metric values


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def scale(x: float, lo: float, hi: float) -> float:
    """Linear map of x from [lo, hi] to [0, 100], clamped."""
    if hi == lo:
        return 0.0
    return clamp((x - lo) / (hi - lo) * 100.0)


def make_metric(
    metric_id: int, score: Optional[float], raw: Any = None, evidence: Optional[list[str]] = None,
    interpretation: str = "", recommendations: Optional[list[str]] = None,
    status: Optional[str] = None, components: Optional[dict] = None,
) -> MetricResult:
    meta = METRICS[metric_id]
    if score is None:
        st = "unavailable"
    else:
        st = status or meta["status_type"]
        score = round(clamp(score), 1)
    return MetricResult(
        id=metric_id, key=meta["key"], name=meta["name"], pillar=meta["pillar"], score=score, status=st,
        raw_value=raw, evidence=evidence or [], method=meta["method"], interpretation=interpretation,
        recommendations=recommendations or [], components={k: (round(v, 1) if isinstance(v, float) else v) for k, v in (components or {}).items()},
    )


def unavailable(metric_id: int, reason: str, recommendation: str = "") -> MetricResult:
    return make_metric(
        metric_id, None, raw=None, evidence=[reason],
        interpretation=f"Not available. {reason}",
        recommendations=[recommendation] if recommendation else [],
    )


def safe_run(metric_id: int, fn: Callable[[AnalysisContext], MetricResult], ctx: AnalysisContext) -> MetricResult:
    """Run one metric function; a failure becomes an unavailable metric rather than a crash."""
    try:
        return fn(ctx)
    except Exception as exc:
        log.exception("Metric %s failed", metric_id)
        return unavailable(metric_id, f"The metric could not be calculated ({type(exc).__name__}).")


def verdict(score: float) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "good"
    if score >= 50:
        return "developing"
    if score >= 30:
        return "weak"
    return "very weak"

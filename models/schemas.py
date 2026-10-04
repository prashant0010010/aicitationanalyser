"""Typed data models shared by collectors, analyzers, scoring and reporting."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class Competitor:
    name: str
    domain: str = ""


@dataclass
class ProjectInput:
    query: str = ""
    extra_queries: list[str] = field(default_factory=list)
    entity: str = ""
    website: str = ""
    industry: str = ""
    market: str = ""
    competitors: list[Competitor] = field(default_factory=list)
    target_url: str = ""
    target_pasted: str = ""
    external_urls: list[str] = field(default_factory=list)
    external_pasted: list[dict] = field(default_factory=list)  # {"label": str, "text": str}

    def all_queries(self) -> list[str]:
        seen, out = set(), []
        for q in [self.query, *self.extra_queries]:
            q = (q or "").strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                out.append(q)
        return out


@dataclass
class Document:
    url: str = ""
    label: str = ""
    kind: str = "target"  # target | external
    origin: str = "url"  # url | pasted_html | pasted_text | demo
    source_type: str = ""
    ok: bool = False
    error: str = ""
    title: str = ""
    text: str = ""
    word_count: int = 0
    blocks: list[dict] = field(default_factory=list)  # {type, text, level, ext_links}
    headings: list[dict] = field(default_factory=list)  # {level, text, block}
    paragraphs: list[str] = field(default_factory=list)
    para_links: list[int] = field(default_factory=list)
    lists: list[list[str]] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)  # {rows: [[...]]}
    links: list[dict] = field(default_factory=list)  # {href, text, external}
    meta: dict[str, Any] = field(default_factory=dict)
    jsonld: list[dict] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    published: str = ""
    modified: str = ""
    has_html: bool = False
    notes: list[str] = field(default_factory=list)
    fetched_at: str = ""

    @property
    def host(self) -> str:
        from utils.urls import hostname

        return hostname(self.url)

    def sections(self) -> list[dict]:
        """Split blocks into sections: {heading, level, paragraphs, lists}."""
        out: list[dict] = [{"heading": "", "level": 0, "paragraphs": [], "lists": []}]
        for b in self.blocks:
            if b["type"] == "heading":
                out.append({"heading": b["text"], "level": b.get("level", 2), "paragraphs": [], "lists": []})
            elif b["type"] == "p":
                out[-1]["paragraphs"].append(b["text"])
            elif b["type"] == "list":
                out[-1]["lists"].append(b["text"])
        return [s for s in out if s["heading"] or s["paragraphs"] or s["lists"]]

    def passages(self, min_words: int = 8) -> list[dict]:
        """Retrievable passages with their section heading: {text, heading}."""
        out, heading = [], ""
        for b in self.blocks:
            if b["type"] == "heading":
                heading = b["text"]
            elif b["type"] in ("p", "list", "table"):
                if len(b["text"].split()) >= min_words:
                    out.append({"text": b["text"], "heading": heading, "type": b["type"]})
        return out

    def summary(self) -> dict:
        return {
            "url": self.url, "label": self.label, "kind": self.kind, "origin": self.origin,
            "ok": self.ok, "error": self.error, "title": self.title, "words": self.word_count,
            "headings": len(self.headings), "source_type": self.source_type,
        }


@dataclass
class AIAnswer:
    label: str = ""
    query: str = ""
    text: str = ""
    citations: list[str] = field(default_factory=list)  # raw lines, URL or "Title - URL"


@dataclass
class MetricResult:
    id: int
    key: str
    name: str
    pillar: str
    score: Optional[float]
    status: str  # measured | proxy | estimate | unavailable
    scale: str = "0-100"
    raw_value: Any = None
    evidence: list[str] = field(default_factory=list)
    method: str = ""
    interpretation: str = ""
    recommendations: list[str] = field(default_factory=list)
    components: dict[str, Any] = field(default_factory=dict)  # sub-scores that make up the score

    @property
    def available(self) -> bool:
        return self.score is not None and self.status != "unavailable"


@dataclass
class Recommendation:
    metric_id: int
    metric_name: str
    category: str
    score: float
    status: str
    evidence: list[str]
    why: str
    action: list[str]
    effect: str
    priority: str
    priority_score: float
    factors: dict[str, float]
    effort: int
    horizon: str  # Immediate | Near-term | Strategic


@dataclass
class QueryResult:
    query: str
    overall: Optional[float]
    pillars: dict[str, Optional[float]]
    key_metrics: dict[str, Optional[float]]
    is_primary: bool = False


@dataclass
class AnalysisResults:
    generated_at: str = ""
    query: str = ""
    metrics: list[MetricResult] = field(default_factory=list)
    scoring: dict[str, Any] = field(default_factory=dict)
    recommendations: list[Recommendation] = field(default_factory=list)
    opportunities: dict[str, list[dict]] = field(default_factory=dict)
    evidence_gaps: list[str] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    answer_analyses: list[dict] = field(default_factory=list)
    external_summary: list[dict] = field(default_factory=list)
    query_set: list[QueryResult] = field(default_factory=list)
    facets: list[dict] = field(default_factory=list)
    semantic_backend: str = ""
    semantic_note: str = ""
    ai_status: str = ""
    ai_provider: str = ""
    ai_subtopics: list[str] = field(default_factory=list)
    ai_commentary: Optional[dict] = None
    intent: str = ""
    warnings: list[str] = field(default_factory=list)

    def metric(self, metric_id: int) -> Optional[MetricResult]:
        return next((m for m in self.metrics if m.id == metric_id), None)


@dataclass
class AnalysisSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)
    project: ProjectInput = field(default_factory=ProjectInput)
    target_doc: Optional[Document] = None
    external_docs: list[Document] = field(default_factory=list)
    answers: list[AIAnswer] = field(default_factory=list)
    results: Optional[AnalysisResults] = None
    is_demo: bool = False
    use_ai: bool = True
    pillar_weights: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    collected_at: str = ""
    analysed_at: str = ""
    report_generated_at: str = ""

    def touch(self) -> None:
        self.updated_at = utcnow()

    def stage(self) -> str:
        if self.results:
            return "analysed"
        if self.target_doc and self.target_doc.ok:
            return "collected"
        if self.project.query and self.project.entity:
            return "defined"
        return "new"

    def to_dict(self) -> dict:
        return asdict(self)

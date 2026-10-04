"""Load the bundled DEMO dataset into a session. The data is fictional and clearly labelled."""
from __future__ import annotations

import json
from pathlib import Path

from config.settings import BASE_DIR
from models.schemas import AIAnswer, AnalysisSession, Competitor

DATA = BASE_DIR / "data"
DEMO_LABEL = "DEMO DATA: fictional entity and sources bundled with the application. Not a real analysis."


def load_demo(session: AnalysisSession) -> AnalysisSession:
    cfg = json.loads((DATA / "demo_project.json").read_text(encoding="utf-8"))
    p = session.project
    p.query, p.entity, p.website = cfg["query"], cfg["entity"], cfg["website"]
    p.industry, p.market = cfg["industry"], cfg["market"]
    p.extra_queries = []
    p.competitors = [Competitor(**c) for c in cfg["competitors"]]
    p.target_url = cfg["website"] + "/best-accounting-software-small-business"
    p.target_pasted = (DATA / "sample_article.html").read_text(encoding="utf-8")
    p.external_urls = []
    p.external_pasted = [
        {"label": s["label"], "url": s["url"], "text": (DATA / s["file"]).read_text(encoding="utf-8")}
        for s in cfg["external_sources"]
    ]
    ans = json.loads((DATA / "sample_ai_answers.json").read_text(encoding="utf-8"))["answers"]
    session.answers = [AIAnswer(label=a["label"], query=a["query"], text=a["text"], citations=a["citations"]) for a in ans]
    session.is_demo = True
    session.results = None
    session.target_doc = None
    session.external_docs = []
    session.touch()
    return session

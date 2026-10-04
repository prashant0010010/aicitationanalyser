from analyzers.base import AnalysisContext
from analyzers.entity_analyzer import build_matcher, extract_entities, prepare
from analyzers.information_analyzer import FACT_PATTERNS, _fact_hits, build_facets
from analyzers.semantic_analyzer import SemanticEngine
from collectors.url_collector import extract_document
from config.scoring import METRICS
from core.pipeline import build_context, run_metrics
from models.schemas import AnalysisSession, Competitor
from utils.query import detect_intent
from utils.text import split_sentences


def test_matcher_variants_and_word_boundaries():
    m = build_matcher("Lumen Ledger Ltd", "https://www.lumenledger.example")
    assert m.present("We use Lumen Ledger daily") and m.present("lumenledger is great") and m.present("Lumen  Ledger")
    assert not m.present("illumen ledgers")


def test_entity_extraction_types_and_roles(demo_session):
    r = demo_session.results
    by = {e["name"]: e for e in r.entities}
    assert by["Lumen Ledger"]["role"] == "target"
    assert by["Ledgerly"]["role"] == "competitor" and by["Tallyworks"]["role"] == "competitor"
    assert by["Auckland"]["type"] == "LOCATION"
    assert any(e["type"] == "PERSON" for e in r.entities)


def test_relationship_extraction(demo_session):
    rels = {(x["relation"], x["object"]) for x in demo_session.results.relationships}
    assert ("partnership", "Hui Payments") in rels
    assert ("integration", "Shopify") in rels


def test_fact_patterns():
    hits = _fact_hits("Pricing starts at NZ$29 per month, up 15% since March 2025, compared with Ledgerly.")
    assert {"currency", "percentage", "date", "comparison"} <= set(hits)
    assert not _fact_hits("We care about our customers and their success.")


def test_intent_detection():
    assert detect_intent("best accounting software for small businesses") == "commercial"
    assert detect_intent("how to file a GST return") == "howto"
    assert detect_intent("what is generative engine optimisation") == "informational"
    assert detect_intent("plumber near me") == "local"
    assert detect_intent("accounting software pricing") == "transactional"


def test_facets_adapt_to_query():
    a = [f["name"] for f in build_facets("best crm for startups", "commercial")]
    b = [f["name"] for f in build_facets("how to bake sourdough", "howto")]
    assert a != b and any("Pricing" in x for x in a) and any("Step" in x for x in b)
    extra = build_facets("x y", "commercial", ["Data residency options"])
    assert any(f["origin"] == "AI suggestion" for f in extra)


def test_all_sixteen_metrics_present_and_in_range(demo_session):
    r = demo_session.results
    assert [m.id for m in r.metrics] == list(range(1, 17))
    for m in r.metrics:
        assert m.score is None or 0 <= m.score <= 100
        assert m.evidence, f"metric {m.id} has no evidence"
        assert m.method == METRICS[m.id]["method"]
    assert 0 <= r.scoring["overall"] <= 100


def test_no_external_data_marks_authority_metrics_unavailable(sample_html):
    s = AnalysisSession()
    s.project.query, s.project.entity, s.project.website = "best accounting software for small businesses", "Lumen Ledger", "https://lumenledger.example"
    s.target_doc = extract_document(sample_html, url="https://lumenledger.example/x")
    ctx = build_context(s, s.project.query, __import__("config.settings", fromlist=["Settings"]).Settings(semantic_backend="tfidf"), [])
    ms = {m.id: m for m in run_metrics(ctx)}
    for i in (13, 14, 15):
        assert ms[i].score is None and ms[i].status == "unavailable"
        assert "Requires" in ms[i].evidence[0]


def test_entity_absent_scores_zero_presence(sample_html):
    s = AnalysisSession()
    s.project.query, s.project.entity = "best accounting software for small businesses", "Totally Different Brand"
    s.target_doc = extract_document(sample_html)
    from config.settings import Settings

    ms = {m.id: m for m in run_metrics(build_context(s, s.project.query, Settings(semantic_backend="tfidf"), []))}
    assert ms[9].score == 0 and ms[10].score == 0


def test_metric_failure_is_contained(sample_html, monkeypatch):
    from core import pipeline
    from config.settings import Settings

    def boom(ctx):
        raise RuntimeError("boom")

    monkeypatch.setitem(pipeline.REGISTRY, 6, boom)
    s = AnalysisSession()
    s.project.query, s.project.entity = "accounting software", "Lumen Ledger"
    s.target_doc = extract_document(sample_html)
    ms = run_metrics(build_context(s, s.project.query, Settings(semantic_backend="tfidf"), []))
    assert ms[5].score is None and "could not be calculated" in ms[5].interpretation and len(ms) == 16

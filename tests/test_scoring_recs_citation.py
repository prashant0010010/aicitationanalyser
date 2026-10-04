from analyzers.citation_analyzer import analyze_answer, parse_citations
from config.scoring import METRICS, PILLARS, band_for
from core.recommendations import build_recommendations
from core.scoring import compute_scores
from models.schemas import AIAnswer, Competitor, MetricResult


def _m(i, score, status=None):
    meta = METRICS[i]
    st = "unavailable" if score is None else (status or meta["status_type"])
    return MetricResult(id=i, key=meta["key"], name=meta["name"], pillar=meta["pillar"], score=score, status=st, recommendations=["fix it"] if score is not None else [], evidence=["e"])


def test_score_math_equal_metrics():
    ms = [_m(i, 80.0) for i in METRICS]
    sc = compute_scores(ms)
    assert sc["overall"] == 80.0 and not sc["provisional"] and sc["band"] == "Good"


def test_weights_and_renormalisation():
    ms = [_m(i, 100.0 if METRICS[i]["pillar"] == "structural" else 0.0) for i in METRICS]
    sc = compute_scores(ms)
    assert sc["pillars"]["structural"]["score"] == 100 and sc["overall"] == 25.0
    sc2 = compute_scores(ms, {"structural": 1.0, "information": 0.0, "entity": 0.0, "authority": 0.0})
    assert sc2["overall"] == 100.0


def test_unavailable_metrics_do_not_count_as_zero():
    ms = [_m(i, 60.0) for i in METRICS]
    ms[12] = _m(13, None)
    sc = compute_scores(ms)
    assert sc["pillars"]["authority"]["score"] == 60.0 and sc["metrics_available"] == 15


def test_pillar_needs_measured_evidence_and_overall_provisional():
    ms = [_m(i, 70.0) for i in METRICS]
    for i in (13, 14, 15):
        ms[i - 1] = _m(i, None)
    sc = compute_scores(ms)
    assert sc["pillars"]["authority"]["score"] is None, "metric 16 alone (an estimate) must not score the pillar"
    assert sc["provisional"] and sc["overall"] == 70.0
    assert any("provisional" in n for n in sc["notes"])


def test_bands():
    assert band_for(90) == "Strong" and band_for(72) == "Good" and band_for(10) == "Very weak" and band_for(None) == "Not available"


def test_recommendation_priorities_ordered_and_threshold():
    ms = [_m(i, 90.0) for i in METRICS]
    ms[5] = _m(6, 20.0)
    ms[11] = _m(12, 70.0)
    recs = build_recommendations(ms, "commercial", 60)
    assert [r.metric_id for r in recs] == [6, 12]
    assert recs[0].priority_score > recs[1].priority_score
    assert recs[0].priority in ("High", "Medium", "Low") and recs[0].horizon in ("Immediate", "Near-term", "Strategic")
    assert set(recs[0].factors) == {"weakness", "impact", "query_importance", "entity_relevance", "effort", "evidence_strength"}
    assert build_recommendations([_m(i, 90.0) for i in METRICS], "commercial", 60) == []


def test_low_value_query_lowers_priority():
    ms = [_m(i, 40.0) for i in METRICS]
    hi = build_recommendations(ms, "commercial", 60)[0].priority_score
    lo = build_recommendations(ms, "navigational", 60)[0].priority_score
    assert hi > lo


def test_parse_citations():
    c = parse_citations(["Reviews - https://reviews.example/a", "https://www.news.example/b.", "Just a title"])
    assert c[0]["domain"] == "reviews.example" and c[0]["title"] == "Reviews"
    assert c[1]["url"] == "https://www.news.example/b" and c[2]["url"] == "" and c[2]["rank"] == 3


def test_answer_analysis_recommended_cited_and_competitors():
    ans = AIAnswer(text="Lumen Ledger is the best choice for sole traders [1]. Ledgerly is cheaper.", citations=["Lumen - https://lumenledger.example/p", "https://other.example/x"])
    a = analyze_answer(ans, "Lumen Ledger", "https://lumenledger.example", [Competitor("Ledgerly", "ledgerly.example")])
    assert a["mention_type"] == "recommended" and a["cited"] and a["citation_ranks"] == [1] and a["citation_prominence"] == 1.0
    assert a["competitor_mentions"] == {"Ledgerly": 1} and a["attributable_ratio"] == 1.0


def test_answer_absent_and_listed():
    absent = analyze_answer(AIAnswer(text="Try Ledgerly."), "Lumen Ledger", "https://lumenledger.example", [])
    assert absent["mention_type"] == "absent" and not absent["cited"] and absent["first_position_pct"] is None
    listed = analyze_answer(AIAnswer(text="Options:\n- Lumen Ledger\n- Ledgerly"), "Lumen Ledger", "https://lumenledger.example", [])
    assert listed["mention_type"] == "listed"


def test_citation_share_metric_values(demo_session):
    m = demo_session.results.metric(15)
    assert m.available and abs(m.raw_value["citation_share"] - 0.25) < 1e-9

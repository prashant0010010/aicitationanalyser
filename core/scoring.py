"""Citation Quality Score calculation from metric results and central weights."""
from __future__ import annotations

from typing import Optional

from config.scoring import METRICS, PILLARS, band_for, default_pillar_weights
from models.schemas import MetricResult


def compute_scores(metrics: list[MetricResult], pillar_weights: Optional[dict[str, float]] = None) -> dict:
    """Return overall score, pillar scores and a human-readable calculation trace.

    Metric weights inside a pillar and pillar weights are renormalised over the
    parts that have evidence. A pillar needs at least `min_measured` metrics with
    status measured or proxy to produce a score.
    """
    pw = {**default_pillar_weights(), **(pillar_weights or {})}
    by_id = {m.id: m for m in metrics}
    pillars, trace, notes = {}, [], []
    for key, pmeta in PILLARS.items():
        ids = [i for i, m in METRICS.items() if m["pillar"] == key]
        avail = [i for i in ids if i in by_id and by_id[i].available]
        measured = [i for i in avail if by_id[i].status in ("measured", "proxy")]
        if len(measured) < pmeta["min_measured"]:
            pillars[key] = {"name": pmeta["name"], "score": None, "available": len(avail), "total": len(ids), "weight": pw[key],
                            "metrics": ids, "reason": "Not enough measured evidence for this pillar."}
            trace.append(f"{pmeta['name']}: not scored (needs at least {pmeta['min_measured']} measured or proxy metric).")
            notes.append(f"{pmeta['name']} was not scored because the required evidence was not supplied.")
            continue
        wsum = sum(METRICS[i]["weight"] for i in avail)
        score = sum(by_id[i].score * METRICS[i]["weight"] for i in avail) / wsum
        parts = ", ".join(f"M{i} {by_id[i].score:.0f} x {METRICS[i]['weight'] / wsum:.2f}" for i in avail)
        trace.append(f"{pmeta['name']} = {score:.1f}  ({parts})")
        pillars[key] = {"name": pmeta["name"], "score": round(score, 1), "available": len(avail), "total": len(ids),
                        "weight": pw[key], "metrics": ids, "reason": ""}
    scored = {k: v for k, v in pillars.items() if v["score"] is not None}
    overall: Optional[float] = None
    if scored:
        wsum = sum(v["weight"] for v in scored.values()) or 1.0
        overall = sum(v["score"] * v["weight"] for v in scored.values()) / wsum
        eff = ", ".join(f"{PILLARS[k]['short']} {v['score']:.0f} x {v['weight'] / wsum:.2f}" for k, v in scored.items())
        trace.append(f"Citation Quality Score = {overall:.1f}  ({eff})")
        overall = round(overall, 1)
    provisional = len(scored) < len(PILLARS)
    if provisional:
        notes.append("The Citation Quality Score is provisional because not every pillar could be scored. It covers only the pillars shown.")
    n_avail = sum(1 for m in metrics if m.available)
    return {
        "overall": overall, "band": band_for(overall), "pillars": pillars, "provisional": provisional,
        "metrics_available": n_avail, "metrics_total": len(METRICS), "trace": trace, "notes": notes,
        "weights_used": {k: round(v, 3) for k, v in pw.items()},
    }

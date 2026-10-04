"""Professional PDF report generation with ReportLab (structured content, no screenshots)."""
from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

from config.scoring import (BANDS, CALIBRATION, INTENT_VALUE, METRICS, PILLARS, PRIORITY_THRESHOLDS,
                            PRIORITY_WEIGHTS, RECOMMENDATION_SCORE_THRESHOLD)
from config.lexicons import SOURCE_TYPE_LABELS
from models.schemas import AnalysisSession
from reporting.narrative import action_plan, executive_summary, strengths_and_weaknesses
from utils.text import pdf_safe, slugify

log = logging.getLogger("citation_analyser.pdf")
INK, MUTED, RULE, SHADE = colors.HexColor("#1f2933"), colors.HexColor("#6b7280"), colors.HexColor("#d1d5db"), colors.HexColor("#f3f4f6")
ACCENT = colors.HexColor("#1d4e89")


class ReportError(Exception):
    pass


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    n = ParagraphStyle("n", parent=base["Normal"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=INK, alignment=TA_LEFT)
    return {
        "n": n,
        "small": ParagraphStyle("small", parent=n, fontSize=8, leading=10.5, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=n, fontSize=8.2, leading=10.5),
        "cellb": ParagraphStyle("cellb", parent=n, fontSize=8.2, leading=10.5, fontName="Helvetica-Bold"),
        "title": ParagraphStyle("title", parent=n, fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=INK, spaceAfter=4),
        "sub": ParagraphStyle("sub", parent=n, fontSize=11, leading=15, textColor=MUTED, spaceAfter=10),
        "h1": ParagraphStyle("h1", parent=n, fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=ACCENT, spaceBefore=14, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=n, fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=INK, spaceBefore=10, spaceAfter=3),
        "bullet": ParagraphStyle("bullet", parent=n, leftIndent=10, bulletIndent=0, spaceAfter=2),
        "score": ParagraphStyle("score", parent=n, fontName="Helvetica-Bold", fontSize=34, leading=38, textColor=ACCENT),
    }


def P(text, style) -> Paragraph:
    return Paragraph(escape(pdf_safe(str(text))), style)


def _bullets(items, st) -> list:
    return [Paragraph(escape(pdf_safe(i)), st["bullet"], bulletText="-") for i in items]


def _table(rows, widths, st, header=True, zebra=True) -> Table:
    data = []
    for ri, row in enumerate(rows):
        data.append([c if not isinstance(c, str) else P(c, st["cellb"] if (header and ri == 0) else st["cell"]) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), SHADE), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK)]
    t.setStyle(TableStyle(style))
    return t


def _score(v) -> str:
    return "n/a" if v is None else f"{v:.0f}"


class _Doc(BaseDocTemplate):
    def __init__(self, buf, title: str, footer: str, **kw):
        super().__init__(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                         title=pdf_safe(title), author="AI Citation Analyser", **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.footer = pdf_safe(footer)
        self.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=self._decor)])

    def _decor(self, canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(MUTED)
        canv.drawString(doc.leftMargin, 10 * mm, self.footer[:120])
        canv.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Page {doc.page}")
        canv.setStrokeColor(RULE)
        canv.line(doc.leftMargin, 13 * mm, A4[0] - doc.rightMargin, 13 * mm)
        canv.restoreState()


def build_pdf(session: AnalysisSession) -> bytes:
    """Build the report and return PDF bytes. Raises ReportError with a readable message on failure."""
    if not session.results:
        raise ReportError("No completed analysis is available. Run the analysis first.")
    try:
        return _build(session)
    except ReportError:
        raise
    except Exception as exc:
        log.exception("PDF generation failed")
        raise ReportError(f"The PDF could not be generated ({type(exc).__name__}: {exc}).") from exc


def report_filename(session: AnalysisSession) -> str:
    return f"AI_Citation_Analysis_{slugify(session.project.entity)}_{datetime.now().strftime('%Y-%m-%d')}.pdf"


def save_pdf(session: AnalysisSession, directory: Path) -> Path:
    data = build_pdf(session)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_filename(session)
    path.write_bytes(data)
    return path


def _build(session: AnalysisSession) -> bytes:
    st = _styles()
    r, p, sc = session.results, session.project, session.results.scoring
    W = 170 * mm
    buf = io.BytesIO()
    demo = "  |  DEMO DATA" if session.is_demo else ""
    doc = _Doc(buf, f"AI Citation Analysis: {p.entity}", f"AI Citation Analysis  |  {p.entity}  |  {p.query}{demo}")
    s: list = []

    # ------------------------------------------------------------ page 1
    s.append(P("AI CITATION ANALYSIS", st["small"]))
    s.append(P(p.entity or "Target entity", st["title"]))
    s.append(P(f"Query: {p.query}", st["sub"]))
    if session.is_demo:
        s.append(P("DEMO DATA: the entity, pages and AI answers in this report are fictional examples bundled with the application. This is not a real analysis.", st["cellb"]))
        s.append(Spacer(1, 4))
    meta = [["Analysis date", r.generated_at], ["Target entity", p.entity], ["Target query", p.query], ["Website", p.website or p.target_url or "Not provided"],
            ["Industry and market", f"{p.industry or 'Not stated'}  |  {p.market or 'Not stated'}"], ["Query intent", r.intent],
            ["Analysis mode", ("AI enhanced" if r.ai_provider and r.ai_commentary is not None else "Local analysis") + f"  |  semantic backend: {r.semantic_backend}"]]
    s.append(_table(meta, [38 * mm, W - 38 * mm], st, header=False))
    s.append(Spacer(1, 8))
    score_txt = "n/a" if sc["overall"] is None else f"{sc['overall']:.0f}"
    big = Table([[Paragraph(f"{score_txt}<font size=14 color='#6b7280'> / 100</font>", st["score"]),
                  P(f"Citation Quality Score ({sc['band']})" + (". Provisional: not every pillar could be scored." if sc["provisional"] else ""), st["n"])]],
                colWidths=[55 * mm, W - 55 * mm])
    big.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.5, RULE), ("BACKGROUND", (0, 0), (-1, -1), SHADE)]))
    s.append(big)
    s.append(Spacer(1, 6))
    prow = [["Pillar", "Score", "Metrics scored", "Weight used"]]
    for k, v in sc["pillars"].items():
        prow.append([v["name"], _score(v["score"]), f"{v['available']} of {v['total']}", f"{sc['weights_used'][k]:.2f}"])
    s.append(_table(prow, [90 * mm, 20 * mm, 30 * mm, 30 * mm], st))
    s.append(P("Executive summary", st["h1"]))
    for para in executive_summary(session):
        s.append(P(para, st["n"]))
        s.append(Spacer(1, 3))
    s.append(PageBreak())

    # ------------------------------------------------------------ scoring and metrics overview
    s.append(P("Citation Quality Score and pillar analysis", st["h1"]))
    s.append(P("Each pillar score is the weighted mean of its available metric scores. The overall score is the weighted mean of the scored pillars. "
               "Weights are renormalised over the evidence that exists, so missing data is never counted as zero.", st["n"]))
    s.append(Spacer(1, 4))
    for line in sc["trace"]:
        s.append(P(line, st["small"]))
    s.append(Spacer(1, 6))
    mrows = [["#", "Metric", "Pillar", "Score", "Basis", "Reading"]]
    for m in r.metrics:
        mrows.append([str(m.id), m.name, PILLARS[m.pillar]["short"], _score(m.score), m.status.capitalize(), (m.interpretation or "")[:110]])
    s.append(_table(mrows, [8 * mm, 46 * mm, 20 * mm, 13 * mm, 20 * mm, 63 * mm], st))
    s.append(P("Basis: measured means directly observed; proxy means an indirect signal; estimate means a modelled judgement; unavailable means the evidence was not supplied.", st["small"]))

    # ------------------------------------------------------------ findings
    strong, weak = strengths_and_weaknesses(session)
    s.append(P("Important findings", st["h1"]))
    s.append(P("Strengths", st["h2"]))
    s.extend(_bullets([f"{m.name} ({m.score:.0f}): {m.evidence[0]}" for m in strong[:5]] or ["No metric reached 75 or above."], st))
    s.append(P("Weaknesses", st["h2"]))
    s.extend(_bullets([f"{m.name} ({m.score:.0f}): {m.evidence[0]}" for m in weak[:5]] or ["No metric scored below 60."], st))
    if r.evidence_gaps:
        s.append(P("Evidence gaps", st["h2"]))
        s.extend(_bullets(r.evidence_gaps, st))
    s.append(PageBreak())

    # ------------------------------------------------------------ 16 metric detail
    s.append(P("The 16 metrics in detail", st["h1"]))
    s.append(P("For every metric: the score, the evidence it rests on, how it was calculated, what it means and what to do about it.", st["n"]))
    for pk, pm in PILLARS.items():
        s.append(P(f"{pm['name']}  ({_score(sc['pillars'][pk]['score'])}/100)", st["h2"]))
        s.append(P(pm["description"], st["small"]))
        for m in [x for x in r.metrics if x.pillar == pk]:
            block = [P(f"{m.id}. {m.name}: {_score(m.score)}/100 ({m.status})", st["cellb"])]
            rows = [["Evidence", "\n".join(f"- {e}" for e in m.evidence) or "None"],
                    ["Calculation", m.method]]
            if m.components:
                rows.append(["Components", ", ".join(f"{k.replace('_', ' ')} {v:.0f}" if isinstance(v, (int, float)) else f"{k} n/a" for k, v in m.components.items() if v is not None)])
            rows.append(["Interpretation", m.interpretation or "Not available"])
            rows.append(["Recommendation", "\n".join(f"- {x}" for x in m.recommendations) or ("No action needed at this score." if m.available else "Supply the missing evidence to score this metric.")])
            t = Table([[P(a, st["cellb"]), _multiline(b, st["cell"])] for a, b in rows], colWidths=[26 * mm, W - 26 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
                                   ("BACKGROUND", (0, 0), (0, -1), SHADE), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
            s.append(KeepTogether(block + [t, Spacer(1, 7)]) if len(rows) < 6 and sum(len(x[1]) for x in rows) < 1400 else None)
            if s[-1] is None:
                s.pop()
                s.extend(block + [t, Spacer(1, 7)])
    s.append(PageBreak())

    # ------------------------------------------------------------ opportunities
    s.append(P("Opportunities", st["h1"]))
    labels = {"citation": "Citation opportunities", "content": "Content opportunities", "entity": "Entity opportunities",
              "authority": "Authority opportunities", "technical": "Technical opportunities"}
    for key, title in labels.items():
        items = r.opportunities.get(key, [])
        s.append(P(title, st["h2"]))
        if not items:
            s.append(P("No opportunity was identified from the supplied evidence." + (" Supply AI answers to find citation opportunities." if key == "citation" and not r.answer_analyses else ""), st["small"]))
            continue
        for it in items:
            rows = [["Opportunity", f"{it['title']}  [{it['priority']} priority]"], ["Evidence", " ".join(it["evidence"])],
                    ["Why it matters", it["why"]], ["Action", " ".join(it["action"])]]
            t = Table([[P(a, st["cellb"]), P(b, st["cell"])] for a, b in rows], colWidths=[26 * mm, W - 26 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE), ("BACKGROUND", (0, 0), (0, -1), SHADE)]))
            s.append(KeepTogether([t, Spacer(1, 5)]))

    # ------------------------------------------------------------ priority matrix and action plan
    s.append(P("Recommended actions and priority matrix", st["h1"]))
    if r.recommendations:
        s.append(P("Priority is calculated, not assigned. Each factor is scored from 0 to 1 and combined with the weights in config/scoring.py: "
                   + ", ".join(f"{k.replace('_', ' ')} {v:.2f}" for k, v in PRIORITY_WEIGHTS.items())
                   + f". High is {PRIORITY_THRESHOLDS['High']:.2f} or above, Medium {PRIORITY_THRESHOLDS['Medium']:.2f} or above.", st["n"]))
        s.append(Spacer(1, 4))
        rows = [["Priority", "Metric", "Score", "Weak", "Impact", "Query", "Entity", "Effort", "Evid.", "Total"]]
        for x in r.recommendations:
            f = x.factors
            rows.append([x.priority, f"{x.metric_id}. {x.metric_name}", _score(x.score), f"{f['weakness']:.2f}", f"{f['impact']:.2f}", f"{f['query_importance']:.2f}",
                         f"{f['entity_relevance']:.2f}", f"{f['effort']:.2f}", f"{f['evidence_strength']:.2f}", f"{x.priority_score:.2f}"])
        s.append(_table(rows, [16 * mm, 50 * mm, 12 * mm, 12 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 15 * mm][:10], st))
        s.append(P("Weak = distance from 100. Impact = metric weight in the overall score. Query = intent value. Entity = current entity relevance. Effort = higher means easier. Evid. = strength of evidence behind the metric.", st["small"]))
        for x in r.recommendations:
            rows = [["Metric", f"{x.metric_id}. {x.metric_name} (score {x.score:.0f}, {x.status})"],
                    ["Observed evidence", " ".join(x.evidence)], ["Why it matters", x.why],
                    ["Recommended action", "\n".join(f"- {a}" for a in x.action)], ["Expected effect", x.effect],
                    ["Priority", f"{x.priority} ({x.priority_score:.2f}), horizon: {x.horizon}"]]
            t = Table([[P(a, st["cellb"]), _multiline(b, st["cell"])] for a, b in rows], colWidths=[32 * mm, W - 32 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE), ("BACKGROUND", (0, 0), (0, -1), SHADE)]))
            s.append(Spacer(1, 6))
            s.append(KeepTogether([t]))
        s.append(P("Action plan", st["h2"]))
        for horizon, items in action_plan(session).items():
            s.append(P(horizon, st["cellb"]))
            s.extend(_bullets([f"{x.metric_name}: {x.action[0]}" for x in items] or ["Nothing scheduled at this horizon."], st))
    else:
        s.append(P(f"No metric scored below {RECOMMENDATION_SCORE_THRESHOLD}, so no corrective recommendation was generated.", st["n"]))

    # ------------------------------------------------------------ AI answers, sources, queries
    if r.answer_analyses:
        s.append(PageBreak())
        s.append(P("AI answer analysis", st["h1"]))
        s.append(P("Based only on the answers the user supplied. The application does not query AI search engines and cannot see private results.", st["small"]))
        rows = [["Answer", "Entity", "Type", "Cited", "Ranks", "Citations", "Competitors named"]]
        for a in r.answer_analyses:
            rows.append([a["label"], "yes" if a["entity_mentioned"] else "no", a["mention_type"], "yes" if a["cited"] else "no",
                         ", ".join(map(str, a["citation_ranks"])) or "-", str(a["citation_count"]),
                         ", ".join(f"{k} x{v}" for k, v in a["competitor_mentions"].items()) or "-"])
        s.append(_table(rows, [30 * mm, 14 * mm, 24 * mm, 14 * mm, 14 * mm, 18 * mm, 56 * mm], st))
        for a in r.answer_analyses:
            s.append(P(a["label"], st["h2"]))
            lines = []
            for c in a["contexts"][:2]:
                lines.append("Mention context: " + c)
            if a["unattributed_mentions"]:
                lines.append("Mentions without an inline citation marker: " + " | ".join(a["unattributed_mentions"][:2]))
            lines.append("Cited domains: " + (", ".join(c["domain"] or c["title"] for c in a["cited_sources"]) or "none supplied"))
            if a["cited_domains_not_mentioning_target"]:
                lines.append("Cited pages that do not mention the entity: " + ", ".join(a["cited_domains_not_mentioning_target"]))
            s.extend(_bullets(lines, st))

    if r.external_summary:
        s.append(P("External sources", st["h1"]))
        rows = [["Source", "Type", "Words", "Mentions", "Links to site", "Prominent"]]
        for e in r.external_summary:
            rows.append([e["label"] or e["url"], SOURCE_TYPE_LABELS.get(e["source_type"], e["source_type"]), str(e["words"]) if e["ok"] else "failed",
                         str(e["mentions"]) if e["ok"] else "-", "yes" if e["links_to_target"] else "no", "yes" if e["prominent"] else "no"])
        s.append(_table(rows, [58 * mm, 36 * mm, 14 * mm, 18 * mm, 22 * mm, 22 * mm], st))

    if len(r.query_set) > 1:
        s.append(P("Query set", st["h1"]))
        rows = [["Query", "Score", "Direct answer", "Coverage", "Relevance"]]
        for q in r.query_set:
            rows.append([q.query + (" (primary)" if q.is_primary else ""), _score(q.overall), _score(q.key_metrics.get("Direct answer")),
                         _score(q.key_metrics.get("Coverage")), _score(q.key_metrics.get("Contextual relevance"))])
        s.append(_table(rows, [80 * mm, 20 * mm, 24 * mm, 22 * mm, 24 * mm], st))
        s.append(P("Additional queries are scored against the same target page. Citation share is only calculated for queries that have matching AI answers.", st["small"]))

    if r.ai_commentary:
        s.append(P("AI-generated commentary", st["h1"]))
        s.append(P(f"Generated by {r.ai_provider} from the measured results. It does not alter any score. Review before use.", st["small"]))
        s.append(P(r.ai_commentary["summary"], st["n"]))
        s.extend(_bullets(r.ai_commentary["priorities"], st))
    s.append(PageBreak())

    # ------------------------------------------------------------ methodology and limits
    s.append(P("Methodology", st["h1"]))
    s.append(P("This is an analytical framework of 16 metrics in four pillars. It does not use, and makes no claim about, the proprietary retrieval or ranking mechanisms of any AI search engine. "
               "It evaluates observable properties of content and of the sources supplied to it.", st["n"]))
    rows = [["#", "Metric", "Basis", "Weight in pillar", "How it is calculated"]]
    for i, m in METRICS.items():
        rows.append([str(i), m["name"], m["status_type"], f"{m['weight']:.2f}", m["method"]])
    s.append(Spacer(1, 4))
    s.append(_table(rows, [8 * mm, 38 * mm, 18 * mm, 18 * mm, 88 * mm], st))
    s.append(P("Score bands", st["h2"]))
    s.append(P(", ".join(f"{label} from {floor}" for floor, label in BANDS), st["n"]))
    s.append(P("Semantic backend", st["h2"]))
    s.append(P(r.semantic_note, st["n"]))
    s.append(P("Limitations", st["h1"]))
    s.extend(_bullets([
        "Pattern-based fact and entity extraction approximates named entity recognition. It can miss entities and misclassify some types.",
        "Third-party mentions, source diversity and citation share describe only the sources and answers supplied. They are not measures of the whole web or of all AI answers.",
        "Source types are classified by domain rules. Unusual domains may be labelled as other web sources.",
        "Metric 16 is an estimate. It uses query intent and measured relevance, and no search volume, traffic or conversion data.",
        "Pages that require JavaScript or block automated access may be only partly collected. Pasted content is used as supplied.",
        "Semantic similarity with the TF-IDF backend reflects weighted term overlap rather than deep meaning. Install sentence embeddings for a stronger signal.",
        "Scores indicate the presence of characteristics associated with usefulness as a source. They do not predict that any specific AI system will cite the entity.",
    ], st))
    if r.warnings:
        s.append(P("Run warnings", st["h2"]))
        s.extend(_bullets(r.warnings, st))

    # ------------------------------------------------------------ data sources and appendix
    s.append(P("Data sources", st["h1"]))
    rows = [["Source", "Kind", "Origin", "Status", "Words"]]
    docs = [session.target_doc, *session.external_docs]
    for d in [x for x in docs if x]:
        rows.append([d.url or d.label, d.kind, d.origin.replace("_", " "), "read" if d.ok else f"failed: {d.error[:60]}", str(d.word_count)])
    s.append(_table(rows, [70 * mm, 18 * mm, 24 * mm, 42 * mm, 16 * mm], st))
    s.append(P(f"AI answers supplied: {len(r.answer_analyses)}. AI status: {r.ai_status}", st["small"]))

    s.append(P("Appendix", st["h1"]))
    s.append(P("A. Detected entities", st["h2"]))
    rows = [["Entity", "Type", "Role", "Mentions"]]
    for e in r.entities[:25]:
        rows.append([e["name"], e["type"].replace("_", " ").title(), e["role"], str(e["count"])])
    s.append(_table(rows, [70 * mm, 40 * mm, 35 * mm, 25 * mm], st))
    if r.relationships:
        s.append(P("B. Detected relationships", st["h2"]))
        rows = [["Relation", "Counterpart", "Evidence"]]
        for x in r.relationships[:15]:
            rows.append([x["relation"], x["object"], x["sentence"]])
        s.append(_table(rows, [26 * mm, 36 * mm, 108 * mm], st))
    if r.facets:
        s.append(P("C. Subtopic coverage checklist", st["h2"]))
        rows = [["Subtopic", "Status", "Origin", "Best similarity"]]
        for f in r.facets:
            rows.append([f["name"], f["level"], f["origin"], f"{f['best_similarity']:.2f}"])
        s.append(_table(rows, [80 * mm, 24 * mm, 36 * mm, 30 * mm], st))
    s.append(P("D. Configuration used", st["h2"]))
    s.append(P("Pillar weights: " + ", ".join(f"{PILLARS[k]['short']} {v:.2f}" for k, v in sc["weights_used"].items())
               + f". Recommendation threshold: score below {RECOMMENDATION_SCORE_THRESHOLD}. Fact density target: {CALIBRATION['fact_density_target_per_100_words']:g} per 100 words. "
               + "Intent values: " + ", ".join(f"{k} {v:.2f}" for k, v in INTENT_VALUE.items()) + ".", st["n"]))
    doc.build([x for x in s if x is not None])
    return buf.getvalue()


def _multiline(text: str, style) -> Paragraph:
    return Paragraph("<br/>".join(escape(pdf_safe(line)) for line in str(text).split("\n")), style)

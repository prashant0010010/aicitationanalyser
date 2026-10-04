"""Scoring configuration for the 16-metric framework.

Everything that decides how a score is built lives here: pillar weights,
metric weights inside each pillar, calibration targets, score bands and the
recommendation priority formula. Change values here, not in the analyzers.

Weights inside a pillar and across pillars are renormalised over the metrics
or pillars that actually have evidence, so a missing data source never
silently counts as zero.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------- pillars
PILLARS: dict[str, dict[str, Any]] = {
    "structural": {
        "name": "Structural Extractability",
        "short": "Structural",
        "weight": 0.25,
        "min_measured": 1,
        "description": "Whether answers, sections and facts can be located and lifted out of the page cleanly.",
    },
    "information": {
        "name": "Fact and Information Density",
        "short": "Information",
        "weight": 0.25,
        "min_measured": 1,
        "description": "How much specific, attributable and complete information the content carries.",
    },
    "entity": {
        "name": "Entity Clarity and Relationship Mapping",
        "short": "Entity",
        "weight": 0.25,
        "min_measured": 1,
        "description": "Whether the target entity is clearly defined and connected to relevant concepts.",
    },
    "authority": {
        "name": "Cross-Platform Authority",
        "short": "Authority",
        "weight": 0.25,
        "min_measured": 1,  # at least one measured or proxy metric (metric 16 is an estimate and does not count)
        "description": "Whether the entity has a coherent footprint beyond its own website.",
    },
}

# ---------------------------------------------------------------- metrics
# status_type: measured (direct observation), proxy (indirect signal), estimate (modelled judgement)
# effort: 1 = quick edit, 2 = moderate content or engineering work, 3 = sustained programme
METRICS: dict[int, dict[str, Any]] = {
    1: dict(
        key="bluf", name="Direct Answer / BLUF Strength", pillar="structural", weight=0.30,
        status_type="measured", needs="Target content and query", effort=1, category="content",
        definition="Whether the page states a clear answer to the target query early, and answers question-style headings directly.",
        method="Relevance of the opening 150 words to the query (semantic similarity) and passage length fit (50%), plus the share of question-style headings followed by a concise answer of 8 to 80 words (50%).",
        why="Answer engines tend to lift short, self-contained answer passages. A buried or missing answer gives them nothing clean to extract.",
        effect="Raises the chance that a passage from this page can be quoted verbatim without rewriting.",
    ),
    2: dict(
        key="headings", name="Heading Hierarchy", pillar="structural", weight=0.20,
        status_type="measured", needs="Target content", effort=1, category="technical",
        definition="Quality of the H1 to H6 outline as a navigable map of the page.",
        method="Single H1 (25%), no skipped levels (20%), section length balance (20%), descriptive heading wording (15%), share of headings related to the query (20%).",
        why="Headings are the labels that retrieval systems use to understand what each section is about.",
        effect="Improves section-level retrieval and makes passage boundaries unambiguous.",
    ),
    3: dict(
        key="chunkability", name="Content Chunkability", pillar="structural", weight=0.25,
        status_type="measured", needs="Target content", effort=2, category="content",
        definition="Whether the page divides into self-contained passages of useful length.",
        method="Share of paragraphs of 25 to 150 words (30%), self-containment of paragraph openings (25%), share of sections with a heading plus substantive paragraph (25%), absence of overlong paragraphs (20%).",
        why="Retrieval pipelines split pages into passages. Passages that depend on surrounding text lose meaning when isolated.",
        effect="Makes individual passages understandable and quotable on their own.",
    ),
    4: dict(
        key="structured", name="Structured Data / Machine Readability", pillar="structural", weight=0.25,
        status_type="measured", needs="Target page HTML", effort=2, category="technical",
        definition="Presence and quality of schema markup, metadata, lists and tables.",
        method="Additive checklist: JSON-LD (25), relevant schema types (20), entity schema naming the target (10), sameAs (5), meta description (10), title (10), canonical (5), Open Graph (5), lists or tables (5), dates (5).",
        why="Machine-readable markup states facts about the page and entity without requiring interpretation of prose.",
        effect="Reduces ambiguity about what the page and the entity are.",
    ),
    5: dict(
        key="density", name="Information Density", pillar="information", weight=0.20,
        status_type="measured", needs="Target content and query", effort=2, category="content",
        definition="Useful, specific content relative to filler and generic copy.",
        method="Informative sentence ratio (40%), semantic density against the query (25%), absence of filler phrases (20%), lexical diversity (15%).",
        why="Low-density copy gives retrieval and summarisation systems little to differentiate one source from another.",
        effect="Increases the proportion of the page that is worth citing.",
    ),
    6: dict(
        key="facts", name="Fact Density", pillar="information", weight=0.30,
        status_type="measured", needs="Target content", effort=2, category="content",
        definition="Concrete, checkable statements: figures, dates, prices, specifications, definitions and comparisons.",
        method="Fact items per 100 words against a target (80%) plus variety of fact types (20%). Extraction is pattern-based and deterministic.",
        why="Specific facts are the raw material of generated answers. Vague claims are rarely cited.",
        effect="Gives answer engines concrete statements to attribute to this source.",
    ),
    7: dict(
        key="attribution", name="Evidence Attribution", pillar="information", weight=0.25,
        status_type="proxy", needs="Target content", effort=2, category="content",
        definition="Whether quantitative and superlative claims are tied to identifiable sources.",
        method="Share of claim sentences with an attribution cue or in-paragraph outbound link (60%), outbound source domains (25%), presence of a references section (15%).",
        why="Unsupported claims are harder for a system to trust or repeat. Attributed claims carry their own provenance.",
        effect="Raises trust in the page's claims and the chance they are reused.",
    ),
    8: dict(
        key="coverage", name="Information Coverage", pillar="information", weight=0.25,
        status_type="proxy", needs="Target content and query", effort=3, category="content",
        definition="How completely the page addresses the subtopics a good answer to the query would need.",
        method="Query-adaptive subtopic set (intent facets, query concepts and optional AI-suggested topics). Each is checked by keyword evidence and semantic similarity. Full coverage counts 1, partial 0.5.",
        why="Queries are rarely answered by one fact. Pages that cover the surrounding subtopics are more useful as a single source.",
        effect="Widens the range of sub-questions the page can serve.",
    ),
    9: dict(
        key="presence", name="Entity Presence", pillar="entity", weight=0.20,
        status_type="measured", needs="Target content and entity name", effort=1, category="entity",
        definition="Prominence of the target entity in the page.",
        method="Mention in title (20), H1 (15), first 100 words (15), mention density per 1,000 words (20), headings (10), metadata or schema (10), spread across sections (10).",
        why="An entity that is not clearly prominent is easy to overlook as the subject of a page.",
        effect="Strengthens the association between the page, the query and the entity.",
    ),
    10: dict(
        key="clarity", name="Entity Clarity", pillar="entity", weight=0.30,
        status_type="measured", needs="Target content and entity name", effort=1, category="entity",
        definition="Whether the page plainly states what the entity is, what it offers, who it is for and where it operates.",
        method="Definition sentence (35), offering described (25), identity or location facts (15), audience stated (15), definition appears early (10).",
        why="Systems resolving an entity need an explicit statement of what it is and does.",
        effect="Makes the entity easier to describe accurately in a generated answer.",
    ),
    11: dict(
        key="relationships", name="Entity Relationships", pillar="entity", weight=0.20,
        status_type="measured", needs="Target content and entity name", effort=2, category="entity",
        definition="Explicit connections between the target entity and other entities.",
        method="Distinct related entities (40), typed relationship statements (30), entity type diversity (15), schema relationship properties (15).",
        why="Relationships place the entity in a network of products, partners, places and concepts that answers draw on.",
        effect="Improves how the entity is contextualised and compared.",
    ),
    12: dict(
        key="relevance", name="Contextual Relevance", pillar="entity", weight=0.30,
        status_type="measured", needs="Target content, entity and query", effort=2, category="content",
        definition="How strongly the entity and its surrounding text relate to the target query.",
        method="Relevance of entity-mentioning passages to the query (35%), share of all passages that are relevant (25%), query terms in title, H1 and headings (20%), entity and query co-occurrence (20%).",
        why="Being mentioned is not enough. The mention must sit in text that actually addresses the query.",
        effect="Aligns the entity with the query so that it is considered topically relevant.",
    ),
    13: dict(
        key="mentions", name="Third-Party Mentions", pillar="authority", weight=0.30,
        status_type="measured", needs="External source URLs or pasted content", effort=3, category="authority",
        definition="Independent external pages that mention the target entity.",
        method="Number of supplied external sources mentioning the entity, scaled so that 5 sources score 100 (60%), links to the entity website (20%), prominent mentions in title, headings or opening text (20%).",
        why="Independent mentions corroborate what the entity says about itself.",
        effect="Builds corroboration across sources that answer engines may consult.",
    ),
    14: dict(
        key="diversity", name="Source Diversity", pillar="authority", weight=0.25,
        status_type="measured", needs="External source URLs or pasted content", effort=3, category="authority",
        definition="Spread of mentioning sources across source types and domains.",
        method="Distinct source types among mentioning sources scaled to 4 (50%) plus distinct registrable domains scaled to 5 (50%). Source types are classified by domain rules.",
        why="A footprint concentrated on one kind of source is fragile and less representative.",
        effect="Makes the entity visible across the kinds of sources that answers cite.",
    ),
    15: dict(
        key="share", name="Citation Share", pillar="authority", weight=0.25,
        status_type="measured", needs="Supplied AI answers with citation lists", effort=3, category="citation",
        definition="Proportion of supplied AI answer citations and brand mentions that belong to the target entity.",
        method="Target-domain citations over all citations (60%) and target mentions over target plus competitor mentions (40%). Each share is scaled so that a 40% share scores 100.",
        why="Share shows how much of the observed answer space the entity occupies relative to others.",
        effect="Tracks competitive position within the answers you have actually collected.",
    ),
    16: dict(
        key="value", name="AI Referral Value / Citation Value", pillar="authority", weight=0.20,
        status_type="estimate", needs="Query and entity (optional: AI answers, external sources)", effort=1, category="citation",
        definition="Estimated strategic value of citation visibility for this query.",
        method="Weighted estimate: query intent value (40%), entity relevance from metrics 9 and 12 (30%), mean relevance of external sources (15%, if available), best citation prominence in supplied answers (15%, if available). No search volume or traffic data is used.",
        why="Not every query is worth the same. Commercial intent queries concentrate the value of being cited.",
        effect="Helps decide where to invest effort first.",
    ),
}

# ---------------------------------------------------------------- calibration
CALIBRATION: dict[str, Any] = {
    "fact_density_target_per_100_words": 3.0,
    "citation_share_full_score_at": 0.40,
    "min_words_for_analysis": 50,
    "external_sources_for_full_mentions": 5,
    "source_types_for_full_diversity": 4,
    "domains_for_full_diversity": 5,
    # similarity to 0-100 conversion per backend: (low, high)
    "sim_range": {"tfidf": (0.02, 0.35), "sbert": (0.15, 0.60)},
    # similarity above which a passage counts as relevant to a query
    "relevance_threshold": {"tfidf": 0.12, "sbert": 0.32},
    "coverage_high_sim": {"tfidf": 0.28, "sbert": 0.55},
    "coverage_low_sim": {"tfidf": 0.10, "sbert": 0.30},
}

# ---------------------------------------------------------------- bands
BANDS: list[tuple[float, str]] = [
    (85, "Strong"),
    (70, "Good"),
    (50, "Developing"),
    (30, "Weak"),
    (0, "Very weak"),
]

INTENT_VALUE: dict[str, float] = {
    "commercial": 1.00,
    "transactional": 1.00,
    "local": 0.85,
    "informational": 0.60,
    "howto": 0.55,
    "navigational": 0.45,
}

# ---------------------------------------------------------------- recommendations
RECOMMENDATION_SCORE_THRESHOLD = 75  # metrics at or above this do not generate a recommendation

PRIORITY_WEIGHTS: dict[str, float] = {
    "weakness": 0.35,          # how far the metric is below 100
    "impact": 0.20,            # metric weight within the overall score (normalised)
    "query_importance": 0.15,  # intent value of the query
    "entity_relevance": 0.10,  # how relevant the entity already is to the query (worth investing in)
    "effort": 0.10,            # lower effort scores higher
    "evidence_strength": 0.10, # measured > proxy > estimate
}
PRIORITY_THRESHOLDS = {"High": 0.72, "Medium": 0.55}  # below Medium is Low
EVIDENCE_STRENGTH = {"measured": 1.0, "proxy": 0.7, "estimate": 0.4}


def band_for(score: float | None) -> str:
    if score is None:
        return "Not available"
    for floor, label in BANDS:
        if score >= floor:
            return label
    return BANDS[-1][1]


def default_pillar_weights() -> dict[str, float]:
    return {k: v["weight"] for k, v in PILLARS.items()}


def metrics_in_pillar(pillar: str) -> list[int]:
    return [i for i, m in METRICS.items() if m["pillar"] == pillar]

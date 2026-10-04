"""Entity extraction and metrics 9 to 12 (Entity Clarity and Relationship Mapping).

Extraction is local and heuristic (capitalisation, suffixes, gazetteers and
patterns). It is a transparent approximation of named entity recognition, not
a trained NER model, and the report labels it that way.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Optional

from analyzers.base import AnalysisContext, clamp, make_metric, scale, unavailable, verdict
from config.lexicons import (CITIES, COUNTRIES, NON_ENTITY_WORDS, ORG_SUFFIXES, PERSON_TITLES,
                             RELATIONSHIPS, TECH_ACRONYMS_EXCLUDE)
from utils.query import query_terms
from utils.text import content_terms, light_stem, split_sentences, stem_set, truncate
from utils.urls import domain_stem

_ORG_SUFFIX_RE = re.compile(r"\s+(?:Inc|Ltd|Limited|LLC|LLP|Corp|Corporation|Co|Company|Pty|GmbH|PLC|Group|Holdings)\.?$", re.I)


# ------------------------------------------------------------------ matching
class EntityMatcher:
    """Match an entity by its name variants and website stem."""

    def __init__(self, name: str, website: str = "") -> None:
        self.name = (name or "").strip()
        variants = {self.name}
        stripped = _ORG_SUFFIX_RE.sub("", self.name).strip()
        if stripped:
            variants.add(stripped)
        stem = domain_stem(website) if website else ""
        if stem and len(stem) >= 4:
            variants.add(stem)
        self.variants = sorted({v for v in variants if v}, key=len, reverse=True)
        parts = []
        for v in self.variants:
            esc = re.escape(v).replace(r"\ ", r"[\s\-]+")
            parts.append(esc)
        flags = 0 if any(len(v) <= 3 for v in self.variants) else re.I
        self.regex = re.compile(r"(?<![\w])(?:" + "|".join(parts) + r")(?![\w])", flags) if parts else None

    def find(self, text: str) -> list[re.Match]:
        return list(self.regex.finditer(text or "")) if self.regex else []

    def count(self, text: str) -> int:
        return len(self.find(text))

    def present(self, text: str) -> bool:
        return bool(self.regex and self.regex.search(text or ""))


def build_matcher(name: str, website: str = "") -> EntityMatcher:
    return EntityMatcher(name, website)


# ------------------------------------------------------------------ extraction
_CAP_SEQ = re.compile(
    r"\b[A-Z][A-Za-z0-9&'’\-]*(?:\s+(?:of|de|von)\s+[A-Z][A-Za-z0-9&'’\-]*|\s+[A-Z][A-Za-z0-9&'’\-]*)*")


def _clause_start(s: str, pos: int) -> bool:
    """True when pos begins a sentence or a list or table clause."""
    return pos == 0 or s[max(0, pos - 2):pos] in ("; ", ": ", "| ", ". ")
_DATE_RE = re.compile(
    r"\b(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:\d{1,2},?\s+)?(?:19|20)\d{2}|(?:19|20)\d{2})\b")
_NUM_RE = re.compile(r"(?:[$€£]\s?)?\b\d[\d,]*(?:\.\d+)?\s?(?:%|percent|million|billion|thousand|k)?\b")


def _classify(name: str, sentence: str) -> str:
    low = name.lower()
    toks = name.split()
    if low in COUNTRIES or low in CITIES:
        return "LOCATION"
    if toks and toks[-1].lower().strip(".") in ORG_SUFFIXES:
        return "ORGANISATION"
    idx = sentence.find(name)
    before = sentence[max(0, idx - 30): idx].lower() if idx >= 0 else ""
    after = sentence[idx + len(name): idx + len(name) + 20].lower() if idx >= 0 else ""
    if any(before.strip().endswith(t) or (" " + t + " ") in (" " + before + " ") for t in PERSON_TITLES) or after.strip().startswith(("said", "says", "told")):
        if len(toks) >= 2 or before.strip():
            return "PERSON"
    if re.search(r"\d", name) or re.search(r"[a-z][A-Z]", name):
        return "PRODUCT"
    if name.isupper() and 2 <= len(name) <= 6:
        return "TECHNOLOGY"
    if len(toks) == 2 and all(t[0].isupper() and t.isalpha() for t in toks) and before.strip().endswith(("by", "founder", "ceo")):
        return "PERSON"
    return "BRAND_OR_PRODUCT"


def extract_entities(text: str, sentences: Optional[list[str]] = None) -> list[dict]:
    """Return aggregated entity candidates: {name, type, count, sentences}."""
    sentences = sentences if sentences is not None else split_sentences(text)
    # pass 1: capitalised tokens that occur away from sentence starts (confirms single-word names)
    mid_caps: set[str] = set()
    for s in sentences:
        for m in _CAP_SEQ.finditer(s):
            if not _clause_start(s, m.start()):
                mid_caps.add(m.group(0).strip().lower())
    counts: Counter = Counter()
    types: dict[str, str] = {}
    where: dict[str, list[int]] = defaultdict(list)
    for i, s in enumerate(sentences):
        for m in _CAP_SEQ.finditer(s):
            name = m.group(0).strip(" -'’&")
            if not name:
                continue
            toks = name.split()
            while toks and toks[0].lower() in NON_ENTITY_WORDS:
                toks = toks[1:]
            while toks and toks[-1].lower() in NON_ENTITY_WORDS:
                toks = toks[:-1]
            if not toks:
                continue
            name = " ".join(toks)
            low = name.lower()
            if low in NON_ENTITY_WORDS or len(name) < 2:
                continue
            at_start = _clause_start(s, m.start()) and len(toks) == len(m.group(0).split())
            if len(toks) == 1:
                if name.upper() in TECH_ACRONYMS_EXCLUDE:
                    continue
                if at_start and low not in mid_caps and not name.isupper():
                    continue
            counts[name] += 1
            if len(where[name]) < 8:
                where[name].append(i)
            types.setdefault(name, _classify(name, s))
    out = [{"name": n, "type": types[n], "count": c, "sentences": where[n]} for n, c in counts.most_common(80)]
    return out


def prepare(ctx: AnalysisContext) -> dict:
    """Compute entity analysis once per context and cache it on the context."""
    if ctx.entity_info is not None:
        return ctx.entity_info
    doc = ctx.doc
    ctx.matcher = build_matcher(ctx.entity, ctx.website)
    sentences = split_sentences(doc.text)
    ents = extract_entities(doc.text, sentences)
    comp_matchers = [(c.name, build_matcher(c.name, c.domain)) for c in ctx.competitors if c.name]
    target_sents = {i for i, s in enumerate(sentences) if ctx.matcher.present(s)}
    schema_names = _schema_names(doc)
    roles: dict[str, str] = {}
    for e in ents:
        name = e["name"]
        if ctx.matcher.present(name) or name.lower() == ctx.entity.lower():
            role = "target"
        elif any(m.present(name) for _, m in comp_matchers):
            role = "competitor"
        elif set(e["sentences"]) & target_sents:
            role = "related"
        elif e["count"] >= 2 or name.lower() in schema_names:
            role = "supporting"
        else:
            role = "unknown"
        e["role"] = role
        roles[name] = role
    # ensure the target appears even if capitalisation heuristics missed it
    tcount = ctx.matcher.count(doc.text)
    if tcount and not any(e["role"] == "target" for e in ents):
        ents.insert(0, {"name": ctx.entity, "type": "BRAND_OR_PRODUCT", "count": tcount, "sentences": sorted(target_sents)[:8], "role": "target"})
    for cname, cm in comp_matchers:
        cc = cm.count(doc.text)
        if cc and not any(e["name"].lower() == cname.lower() for e in ents):
            ents.append({"name": cname, "type": "BRAND_OR_PRODUCT", "count": cc, "sentences": [], "role": "competitor"})
    # topics: most frequent content bigrams
    terms = content_terms(doc.text)
    bigrams = Counter(f"{a} {b}" for a, b in zip(terms, terms[1:]) if a != b)
    topics = [t for t, c in bigrams.most_common(12) if c >= 2][:8]
    relationships = _relationships(ctx, sentences, ents)
    ctx.entity_info = {
        "sentences": sentences, "entities": ents, "target_sentence_idx": sorted(target_sents),
        "relationships": relationships, "topics": topics,
        "dates": len(_DATE_RE.findall(doc.text)), "numbers": len(_NUM_RE.findall(doc.text)),
        "schema_names": sorted(schema_names),
    }
    return ctx.entity_info


def _schema_names(doc) -> set[str]:
    names = set()
    for n in doc.jsonld:
        v = n.get("name")
        if isinstance(v, str):
            names.add(v.lower())
        for key in ("brand", "publisher", "author", "provider", "manufacturer"):
            sub = n.get(key)
            if isinstance(sub, dict) and isinstance(sub.get("name"), str):
                names.add(sub["name"].lower())
    return names


def _relationships(ctx: AnalysisContext, sentences: list[str], ents: list[dict]) -> list[dict]:
    rels: list[dict] = []
    others = [e for e in ents if e["role"] != "target"]
    for i in ctx.entity_info["target_sentence_idx"] if ctx.entity_info else [i for i, s in enumerate(sentences) if ctx.matcher.present(s)]:
        s = sentences[i]
        present = [(s.find(e["name"]), e) for e in others if e["name"] in s]
        verbs = [(label, m) for label, pat in RELATIONSHIPS.items() for m in re.finditer(pat, s, re.I)]
        for label, vm in verbs:
            after = sorted((pos, e) for pos, e in present if pos >= vm.end() - 1)
            cands = [e for _, e in after if e["name"] not in vm.group(0)]
            if label == "location":
                cands = [e for e in cands if e["type"] == "LOCATION"] or cands
            for e in cands[:2]:
                rels.append({"subject": ctx.entity, "relation": label, "object": e["name"], "object_type": e["type"], "sentence": truncate(s, 220)})
        if not verbs and present:
            for _, e in present[:2]:
                rels.append({"subject": ctx.entity, "relation": "co-mentioned", "object": e["name"], "object_type": e["type"], "sentence": truncate(s, 220)})
    seen, out = set(), []
    for r in rels:
        k = (r["relation"], r["object"].lower())
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


# ------------------------------------------------------------------ metrics
def entity_presence(ctx: AnalysisContext) -> "MetricResult":  # noqa: F821
    info = prepare(ctx)
    doc, m = ctx.doc, ctx.matcher
    if not ctx.entity.strip():
        return unavailable(9, "No target entity was defined.")
    total = m.count(doc.text)
    words = max(1, doc.word_count)
    per_1000 = total / words * 1000
    in_title = m.present(doc.title)
    h1s = [h["text"] for h in doc.headings if h["level"] == 1]
    in_h1 = any(m.present(h) for h in h1s)
    first100 = " ".join(doc.text.split()[:100])
    in_first = m.present(first100)
    heads = [h["text"] for h in doc.headings if m.present(h["text"])]
    meta_hit = m.present(doc.meta.get("description", "")) or m.present(doc.meta.get("og_title", "")) or any(
        m.present(str(n.get("name", ""))) for n in doc.jsonld)
    sections = doc.sections()
    sec_hit = sum(1 for s in sections if m.present(" ".join(s["paragraphs"]) + " " + s["heading"]))
    comp = {
        "title": 20 if in_title else 0, "h1": 15 if in_h1 else 0, "first_100_words": 15 if in_first else 0,
        "density": 20 * (1.0 if 3 <= per_1000 <= 20 else min(1.0, per_1000 / 3) if per_1000 < 3 else max(0.4, 1 - (per_1000 - 20) / 40)),
        "headings": 10 if heads else 0, "metadata_or_schema": 10 if meta_hit else 0,
        "section_spread": 10 * min(1.0, sec_hit / 3),
    }
    score = sum(comp.values()) if total else 0.0
    ev = [f"{total} mention(s) of '{ctx.entity}' in {words} words ({per_1000:.1f} per 1,000 words).",
          f"In title: {'yes' if in_title else 'no'}. In H1: {'yes' if in_h1 else 'no'}. In first 100 words: {'yes' if in_first else 'no'}.",
          f"Appears in {len(heads)} heading(s) and in {sec_hit} of {len(sections)} section(s)."]
    if heads:
        ev.append("Headings naming the entity: " + "; ".join(truncate(h, 70) for h in heads[:3]))
    recs = []
    if total == 0:
        recs.append(f"'{ctx.entity}' does not appear in the page text. State the entity name explicitly in the title, H1 and opening paragraph so it is unambiguous who the page is about.")
    else:
        if not in_title:
            recs.append(f"Add '{ctx.entity}' to the title tag (current title: '{truncate(doc.title, 70) or 'none'}').")
        if not in_h1:
            recs.append(f"Name '{ctx.entity}' in the H1. Current H1: {truncate(h1s[0], 70) if h1s else 'none found'}.")
        if not in_first:
            recs.append("Mention the entity within the first 100 words so the subject is clear before the page develops its argument.")
        if per_1000 < 3:
            recs.append(f"Entity mentions are sparse ({per_1000:.1f} per 1,000 words). Refer to the entity by name, not only by pronouns or 'we', in key passages.")
    interp = (f"The entity is {verdict(score)} in prominence. " + ("It is not present in the page text." if total == 0 else
              f"It is mentioned {total} time(s) and the strongest signals are {'in the title and H1' if in_title and in_h1 else 'in the body text'}."))
    return make_metric(9, score, raw={"mentions": total, "per_1000_words": round(per_1000, 2)}, evidence=ev,
                       interpretation=interp, recommendations=recs, components=comp)


_DEF_RE = lambda name: re.compile(rf"{name}(?:\W+\w+){{0,3}}?\s+(?:is|are|was)\s+(?:a|an|the|one of)\b", re.I)
_OFFER_RE = re.compile(r"\b(?:provides?|offers?|helps?|enables?|specialis\w+ in|delivers?|builds?|makes?|sells?|supplies|automates?|lets? you|allows?|designed to|used to)\b", re.I)
_IDENT_RE = re.compile(r"\b(?:founded|established|launched|headquartered|based in|located in|operates in|since (?:19|20)\d{2}|offices? in)\b", re.I)
_AUDIENCE_RE = re.compile(r"\b(?:for (?:small|medium|large|growing|enterprise|freelance|local|busy|teams|businesses|companies|individuals|people|organisations|organizations|[a-z]+s\b)|designed for|built for|aimed at|suited to|ideal for|made for|used by)\b", re.I)


def entity_clarity(ctx: AnalysisContext) -> "MetricResult":  # noqa: F821
    info = prepare(ctx)
    if not ctx.entity.strip():
        return unavailable(10, "No target entity was defined.")
    m = ctx.matcher
    sents = info["sentences"]
    tgt = [(i, sents[i]) for i in info["target_sentence_idx"]]
    if not tgt:
        return make_metric(10, 0.0, raw={"entity_sentences": 0},
                           evidence=[f"No sentence in the page text mentions '{ctx.entity}'."],
                           interpretation="The page never states what the entity is.",
                           recommendations=[f"Add a plain definition sentence such as '{ctx.entity} is a [category] that [does what] for [whom]' near the top of the page."])
    name_pat = "|".join(re.escape(v) for v in m.variants)
    def_re = _DEF_RE(f"(?:{name_pat})")
    defs = [(i, s) for i, s in tgt if def_re.search(s)]
    offers = [(i, s) for i, s in tgt if _OFFER_RE.search(s)]
    idents = [(i, s) for i, s in tgt if _IDENT_RE.search(s)]
    aud = [(i, s) for i, s in tgt if _AUDIENCE_RE.search(s)]
    early_cut = max(5, int(len(sents) * 0.2))
    early_def = any(i < early_cut for i, _ in defs) or any(i < early_cut for i, _ in offers)
    comp = {
        "definition_sentence": 35 if defs else (15 if offers else 0),
        "offering_described": 25 * (1.0 if len(offers) >= 2 else 0.6 if offers else 0),
        "identity_or_location": 15 if idents else 0,
        "audience_stated": 15 if aud else 0,
        "stated_early": 10 if early_def else 0,
    }
    score = sum(comp.values())
    ev = []
    if defs:
        ev.append("Definition: " + truncate(defs[0][1], 200))
    if offers:
        ev.append("Offering: " + truncate(offers[0][1], 200))
    if idents:
        ev.append("Identity or location: " + truncate(idents[0][1], 200))
    if aud:
        ev.append("Audience: " + truncate(aud[0][1], 200))
    ev.append(f"{len(tgt)} sentence(s) mention the entity; {len(defs)} define it, {len(offers)} describe an offering, {len(aud)} state an audience.")
    recs = []
    if not defs:
        recs.append(f"Add an explicit definition: '{ctx.entity} is a [category] that [specific function] for [audience]'. No sentence currently defines the entity.")
    if not aud:
        recs.append("State who the entity is for. No audience statement was found next to the entity name.")
    if not idents:
        recs.append("Add identity facts (year founded, headquarters or service area) beside the entity name so it can be disambiguated.")
    if defs and not early_def:
        recs.append("Move the definition into the first fifth of the page. It currently appears late.")
    interp = f"Entity clarity is {verdict(score)}. " + ("The page defines the entity directly." if defs else "The page describes the entity indirectly but never defines it.")
    return make_metric(10, score, raw={"definitions": len(defs), "offerings": len(offers), "audience": len(aud)},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def entity_relationships(ctx: AnalysisContext) -> "MetricResult":  # noqa: F821
    info = prepare(ctx)
    if not ctx.entity.strip():
        return unavailable(11, "No target entity was defined.")
    ents = info["entities"]
    related = [e for e in ents if e["role"] in ("related", "competitor")]
    typed = [r for r in info["relationships"] if r["relation"] != "co-mentioned"]
    types = {e["type"] for e in related}
    schema_props = _schema_relation_props(ctx.doc)
    comp = {
        "related_entities": 40 * min(1.0, len(related) / 8),
        "typed_relationships": 30 * min(1.0, len(typed) / 4),
        "type_diversity": 15 * min(1.0, len(types) / 3),
        "schema_relations": 15 * min(1.0, len(schema_props) / 3),
    }
    score = sum(comp.values()) if info["target_sentence_idx"] else 0.0
    ev = [f"{len(related)} related or competing entities share sentences with '{ctx.entity}' ({', '.join(e['name'] for e in related[:6]) or 'none'})."]
    for r in typed[:4]:
        ev.append(f"{r['relation'].title()}: {r['subject']} and {r['object']}. Evidence: {truncate(r['sentence'], 160)}")
    if schema_props:
        ev.append("Schema relationship properties: " + ", ".join(sorted(schema_props)))
    else:
        ev.append("No relationship properties (sameAs, founder, parentOrganization, brand and similar) found in schema markup.")
    recs = []
    if len(typed) < 2:
        recs.append("State relationships explicitly in sentences, for example integrations, partners, founders, locations or recognised credentials, naming each counterpart. Only "
                    f"{len(typed)} typed relationship(s) were detected.")
    if len(related) < 4:
        recs.append("Connect the entity to more named products, people, places and organisations that are relevant to the query.")
    if not schema_props and ctx.doc.has_html:
        recs.append("Add schema.org properties that express relationships (sameAs, founder, parentOrganization, brand, areaServed) to the entity's JSON-LD.")
    interp = f"Relationship mapping is {verdict(score)}: {len(typed)} typed relationship statement(s) and {len(related)} related entities were found."
    return make_metric(11, score, raw={"related": len(related), "typed": len(typed), "schema_props": sorted(schema_props)},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def _schema_relation_props(doc) -> set[str]:
    keys = {"sameAs", "founder", "parentOrganization", "subOrganization", "brand", "areaServed", "knowsAbout",
            "member", "memberOf", "affiliation", "owns", "manufacturer", "provider", "isRelatedTo", "isSimilarTo", "isPartOf"}
    found = set()
    for n in doc.jsonld:
        for k in keys:
            if n.get(k):
                found.add(k)
    return found


def contextual_relevance(ctx: AnalysisContext) -> "MetricResult":  # noqa: F821
    info = prepare(ctx)
    doc, eng = ctx.doc, ctx.engine
    if not ctx.query.strip():
        return unavailable(12, "No target query was defined.")
    passages = doc.passages(min_words=8)
    if not passages:
        return unavailable(12, "No passages of sufficient length were found.")
    texts = [p["text"] for p in passages]
    sims = eng.similarity([ctx.query], texts)[0]
    thr = eng.relevance_threshold
    share_rel = float((sims >= thr).mean())
    tgt_idx = [i for i, t in enumerate(texts) if ctx.matcher.present(t)] if ctx.entity.strip() else []
    top = sorted((float(x) for x in sims[tgt_idx]), reverse=True)[:5] if tgt_idx else []
    ent_rel = sum(top) / len(top) if top else 0.0
    qterms = {light_stem(t) for t in query_terms(ctx.query)} or stem_set(ctx.query)
    def has_q(text: str) -> float:
        st = stem_set(text)
        return len(qterms & st) / len(qterms) if qterms else 0.0
    h1s = [h["text"] for h in doc.headings if h["level"] == 1]
    place_hits = sum(1 for t in [doc.title, *h1s] if has_q(t) >= 0.5)
    heads = [h["text"] for h in doc.headings]
    head_share = (sum(1 for h in heads if has_q(h) > 0) / len(heads)) if heads else 0.0
    place_score = 0.5 * min(1.0, place_hits / 2) * 100 + 0.5 * min(1.0, head_share / 0.4) * 100
    co = sum(1 for t in texts if ctx.entity.strip() and ctx.matcher.present(t) and has_q(t) >= 0.5)
    co_share = (co / len(tgt_idx)) if tgt_idx else 0.0
    comp = {
        "entity_passage_relevance": 0.35 * eng.sim_to_score(ent_rel),
        "relevant_passage_share": 0.25 * scale(share_rel, 0.0, 0.6),
        "query_terms_in_headings": 0.20 * place_score,
        "entity_query_cooccurrence": 0.20 * (co_share * 100),
    }
    score = sum(comp.values())
    order = sorted(range(len(texts)), key=lambda i: -sims[i])[:3]
    ev = [f"Backend: {eng.backend}. {int((sims >= thr).sum())} of {len(texts)} passages are relevant to the query (similarity >= {thr:.2f}); best similarity {sims.max():.2f}.",
          f"{len(tgt_idx)} passage(s) mention the entity; {co} of them also contain at least half of the key query terms.",
          f"Query terms appear in the title: {'yes' if has_q(doc.title) >= 0.5 else 'no'}; in the H1: {'yes' if any(has_q(h) >= 0.5 for h in h1s) else 'no'}; in {head_share*100:.0f}% of headings."]
    for i in order[:2]:
        ev.append(f"Most relevant passage (similarity {sims[i]:.2f}): {truncate(texts[i], 180)}")
    recs = []
    if tgt_idx and co_share < 0.5:
        recs.append(f"Only {co} of {len(tgt_idx)} passages that name '{ctx.entity}' also use the language of the query. Put the query's key terms ({', '.join(list(query_terms(ctx.query))[:4])}) in the same passages as the entity name.")
    if place_score < 50:
        recs.append("Reflect the query wording in the title, H1 and at least some H2 headings so the page's topic matches the query at the structural level.")
    if share_rel < 0.3:
        recs.append("Most passages are only loosely related to the query. Tighten the page to the query or split off-topic material into separate pages.")
    interp = f"Contextual relevance is {verdict(score)}. " + ("The entity is discussed in text that addresses the query." if score >= 60 else "The entity and the query are only weakly linked in the page text.")
    return make_metric(12, score, raw={"relevant_share": round(share_rel, 3), "best_similarity": round(float(sims.max()), 3), "backend": eng.backend},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


METRICS = {9: entity_presence, 10: entity_clarity, 11: entity_relationships, 12: contextual_relevance}

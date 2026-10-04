"""Pillar 1: Structural Extractability (metrics 1 to 4)."""
from __future__ import annotations

import re

from analyzers.base import AnalysisContext, clamp, make_metric, scale, unavailable, verdict
from config.lexicons import DEPENDENT_OPENERS
from utils.query import query_terms
from utils.text import light_stem, stem_set, truncate, word_count

_QUESTION_START = re.compile(r"^(what|how|why|when|where|who|which|can|does|do|is|are|should|will|could)\b", re.I)
RELEVANT_SCHEMA = {
    "Organization", "Corporation", "LocalBusiness", "Product", "SoftwareApplication", "Service", "Article",
    "NewsArticle", "BlogPosting", "FAQPage", "HowTo", "WebPage", "WebSite", "BreadcrumbList", "Review",
    "AggregateRating", "Person", "Brand", "ItemList", "Offer", "QAPage",
}
ENTITY_SCHEMA = {"Organization", "Corporation", "LocalBusiness", "Brand", "Product", "SoftwareApplication", "Service"}


def _is_question(text: str) -> bool:
    t = text.strip()
    return t.endswith("?") or bool(_QUESTION_START.match(t))


def bluf_strength(ctx: AnalysisContext):
    doc, eng = ctx.doc, ctx.engine
    if not ctx.query.strip():
        return unavailable(1, "No target query was defined.")
    paras = [(i, b) for i, b in enumerate(doc.blocks) if b["type"] == "p" and word_count(b["text"]) >= 8]
    if not paras:
        return unavailable(1, "The page has no paragraphs of sufficient length to assess.")
    # opening window: paragraphs until ~150 words have been read
    window, total = [], 0
    for _, b in paras:
        window.append(b["text"])
        total += word_count(b["text"])
        if total >= 150:
            break
    sims = eng.similarity([ctx.query], window)[0]
    best = int(sims.argmax())
    wc = word_count(window[best])
    length_fit = 100 if 15 <= wc <= 80 else 60 if 80 < wc <= 120 else 40 if wc < 15 else 20
    opening = 0.35 * length_fit + 0.65 * eng.sim_to_score(float(sims[best]))
    # question headings and the block that follows
    pairs, direct = [], 0
    for h in doc.headings:
        if _is_question(h["text"]):
            nxt = next((b for b in doc.blocks[h["block"] + 1: h["block"] + 3] if b["type"] in ("p", "list")), None)
            ok = bool(nxt) and ((nxt["type"] == "p" and 8 <= word_count(nxt["text"]) <= 80) or (nxt["type"] == "list" and len(nxt.get("items", [])) >= 2))
            pairs.append((h["text"], nxt["text"] if nxt else "", ok))
            direct += int(ok)
    qa = (direct / len(pairs) * 100) if pairs else 25.0
    comp = {"opening_answer": 0.5 * opening, "question_answer_pairs": 0.5 * qa}
    score = sum(comp.values())
    ev = [f"Opening window ({total} words read): best match to the query is a {wc}-word paragraph with similarity {sims[best]:.2f} ({eng.backend}).",
          "Opening passage: " + truncate(window[best], 220)]
    if pairs:
        ev.append(f"{direct} of {len(pairs)} question-style headings are followed by a concise direct answer.")
        for q, a, ok in pairs[:3]:
            ev.append(f"{'Direct' if ok else 'Not direct'}: '{truncate(q, 70)}' then '{truncate(a, 90) or 'no answer block'}'")
    else:
        ev.append("No question-style headings were found, so there are no explicit question and answer pairs to extract.")
    recs = []
    if opening < 60:
        recs.append(f"Open with a 40 to 70 word answer to '{ctx.query}' that names {ctx.entity or 'the entity'} and states the conclusion before the supporting detail. "
                    f"The strongest opening paragraph is {wc} words with similarity {sims[best]:.2f}.")
    if not pairs:
        recs.append("Add a question-led section (FAQ or H2 phrased as the question) with a 40 to 60 word direct answer under each question.")
    elif direct < len(pairs):
        recs.append(f"{len(pairs) - direct} question heading(s) are not followed by a concise answer. Place a 40 to 60 word answer immediately under each question.")
    interp = f"Direct answer strength is {verdict(score)}. " + ("The query is answered early and concisely." if score >= 70 else "A reader or retrieval system would have to read further to find a clean answer.")
    return make_metric(1, score, raw={"opening_words": wc, "opening_similarity": round(float(sims[best]), 3), "qa_pairs": len(pairs), "qa_direct": direct},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def heading_hierarchy(ctx: AnalysisContext):
    doc = ctx.doc
    hs = doc.headings
    if not hs:
        return make_metric(2, 0.0, raw={"headings": 0}, evidence=["No headings were found in the main content."],
                           interpretation="The page has no heading structure to navigate or segment.",
                           recommendations=["Add one H1 and descriptive H2 sections. Each section should answer one sub-question related to the query."])
    h1 = [h for h in hs if h["level"] == 1]
    h1_score = 100 if len(h1) == 1 else 40 if len(h1) > 1 else 10
    skips = sum(1 for a, b in zip(hs, hs[1:]) if b["level"] - a["level"] > 1)
    skip_score = max(0.0, 100 - 25 * skips)
    sec_words = [word_count(" ".join(s["paragraphs"])) for s in doc.sections() if s["heading"]]
    avg = (sum(sec_words) / len(sec_words)) if sec_words else 0
    if not sec_words:
        bal = 0.0
    elif 60 <= avg <= 350:
        bal = 100.0
    elif avg > 350:
        bal = max(0.0, 100 - (avg - 350) / 5)
    else:
        bal = avg / 60 * 100
    wlen = [word_count(h["text"]) for h in hs]
    avg_len = sum(wlen) / len(wlen)
    uniq = len({h["text"].lower() for h in hs}) / len(hs)
    desc = (100 if 2 <= avg_len <= 10 else 40 if avg_len < 2 else 60) * (0.5 + 0.5 * uniq)
    qterms = {light_stem(t) for t in query_terms(ctx.query)} or stem_set(ctx.query)
    related = sum(1 for h in hs if qterms & stem_set(h["text"])) / len(hs) if qterms else 0.0
    rel_score = min(100.0, related / 0.4 * 100)
    comp = {"single_h1": 0.25 * h1_score, "no_skipped_levels": 0.20 * skip_score, "section_balance": 0.20 * bal,
            "descriptive_wording": 0.15 * desc, "query_related_headings": 0.20 * rel_score}
    score = sum(comp.values())
    outline = "; ".join(f"H{h['level']} {truncate(h['text'], 40)}" for h in hs[:8])
    ev = [f"{len(hs)} headings: {len([h for h in hs if h['level']==1])} H1, {len([h for h in hs if h['level']==2])} H2, {len([h for h in hs if h['level']==3])} H3, deeper {len([h for h in hs if h['level']>3])}.",
          f"{skips} skipped heading level(s). Average section length {avg:.0f} words. Average heading length {avg_len:.1f} words.",
          f"{related*100:.0f}% of headings contain query terms.", "Outline: " + outline]
    recs = []
    if len(h1) != 1:
        recs.append(f"Use exactly one H1 ({len(h1)} found) that states the page's subject and includes the query's key terms.")
    if skips:
        recs.append(f"Fix {skips} skipped heading level(s) so the outline is continuous (for example H2 then H3, not H2 then H4).")
    if avg > 350:
        recs.append(f"Sections average {avg:.0f} words. Split them under additional H2 or H3 headings so each passage has its own label.")
    if rel_score < 50:
        recs.append("Make headings descriptive of the sub-questions behind the query rather than generic labels such as 'Overview' or 'More'.")
    interp = f"Heading hierarchy is {verdict(score)}. " + ("The outline is a reliable map of the page." if score >= 70 else "The outline is incomplete or inconsistent, which weakens section-level retrieval.")
    return make_metric(2, score, raw={"headings": len(hs), "h1": len(h1), "skips": skips, "avg_section_words": round(avg, 1)},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def chunkability(ctx: AnalysisContext):
    doc = ctx.doc
    paras = [p for p in doc.paragraphs if word_count(p) >= 5]
    if not paras:
        return unavailable(3, "The page has no paragraphs to evaluate.")
    wcs = [word_count(p) for p in paras]
    ideal = sum(1 for w in wcs if 25 <= w <= 150) / len(wcs)
    overlong = sum(1 for w in wcs if w > 200) / len(wcs)
    dep = [p for p in paras if word_count(p) >= 15 and re.match(DEPENDENT_OPENERS, p.strip(), re.I)]
    dep_ratio = len(dep) / len(paras)
    secs = doc.sections()
    good_secs = sum(1 for s in secs if s["heading"] and any(word_count(p) >= 25 for p in s["paragraphs"] + s["lists"]))
    sec_ratio = good_secs / max(1, len([s for s in secs if s["heading"]])) if any(s["heading"] for s in secs) else 0.0
    comp = {"ideal_length_paragraphs": 0.30 * min(100.0, ideal / 0.6 * 100),
            "self_contained_openings": 0.25 * scale(1 - dep_ratio, 0.6, 1.0),
            "substantive_sections": 0.25 * sec_ratio * 100,
            "no_overlong_paragraphs": 0.20 * (100 - overlong * 100)}
    score = sum(comp.values())
    longest = max(paras, key=word_count)
    ev = [f"{len(paras)} paragraphs: {ideal*100:.0f}% are 25 to 150 words, {overlong*100:.0f}% exceed 200 words. Median length {sorted(wcs)[len(wcs)//2]} words.",
          f"{len(dep)} paragraph(s) open with a dependent referent such as 'This', 'However' or 'It' ({dep_ratio*100:.0f}%).",
          f"{good_secs} of {len([s for s in secs if s['heading']])} headed section(s) contain a substantive paragraph or list."]
    if dep:
        ev.append("Dependent opening example: " + truncate(dep[0], 130))
    if overlong:
        ev.append(f"Longest paragraph is {word_count(longest)} words: " + truncate(longest, 110))
    recs = []
    if overlong > 0.1:
        recs.append(f"Break the {int(overlong*len(paras)) or 1} paragraph(s) over 200 words into passages of 60 to 120 words that each make one point.")
    if dep_ratio > 0.15:
        recs.append("Rewrite paragraph openings that start with 'This', 'It' or 'However' so they name their subject. A passage lifted out of context should still make sense.")
    if sec_ratio < 0.7:
        recs.append("Give every H2 section at least one self-contained paragraph of 40 words or more rather than headings followed only by fragments.")
    interp = f"Chunkability is {verdict(score)}. " + ("Passages can be separated and quoted without loss of meaning." if score >= 70 else "Many passages would lose meaning if extracted on their own.")
    return make_metric(3, score, raw={"paragraphs": len(paras), "ideal_share": round(ideal, 3), "overlong_share": round(overlong, 3), "dependent_share": round(dep_ratio, 3)},
                       evidence=ev, interpretation=interp, recommendations=recs, components=comp)


def structured_data(ctx: AnalysisContext):
    doc = ctx.doc
    if not doc.has_html:
        return unavailable(4, "Only plain text was supplied, so markup and metadata cannot be assessed. Supply a URL or HTML to measure this.")
    types = set(doc.schema_types)
    rel = types & RELEVANT_SCHEMA
    ent_nodes = [n for n in doc.jsonld if (set(n.get("@type") if isinstance(n.get("@type"), list) else [n.get("@type")]) & ENTITY_SCHEMA)]
    names_target = False
    if ctx.entity.strip():
        from analyzers.entity_analyzer import build_matcher

        mt = build_matcher(ctx.entity, ctx.website)
        names_target = any(mt.present(str(n.get("name", ""))) for n in ent_nodes)
    same_as = any(n.get("sameAs") for n in doc.jsonld)
    desc = doc.meta.get("description", "")
    title = doc.title
    og = bool(doc.meta.get("og_title") and doc.meta.get("og_description"))
    comp = {
        "json_ld_present": 25 if doc.jsonld else 0,
        "relevant_schema_types": 20 * min(1.0, len(rel) / 3),
        "entity_schema_names_target": 10 if names_target else (5 if ent_nodes else 0),
        "sameAs": 5 if same_as else 0,
        "meta_description": 10 if 70 <= len(desc) <= 170 else 5 if desc else 0,
        "title": 10 if 20 <= len(title) <= 70 else 5 if title else 0,
        "canonical": 5 if doc.meta.get("canonical") else 0,
        "open_graph": 5 if og else 0,
        "lists_or_tables": 5 if (doc.lists or doc.tables) else 0,
        "dates": 5 if (doc.published or doc.modified) else 0,
    }
    score = sum(comp.values())
    ev = [f"JSON-LD blocks: {len(doc.jsonld)}; schema types: {', '.join(sorted(types)) or 'none'}.",
          f"Meta description: {len(desc)} characters" + (" (ideal 70 to 170)." if desc else " (missing)."),
          f"Title: {len(title)} characters. Canonical: {'yes' if doc.meta.get('canonical') else 'no'}. Open Graph title and description: {'yes' if og else 'no'}.",
          f"{len(doc.lists)} list(s) and {len(doc.tables)} table(s) in the main content. Published: {doc.published or 'not found'}; modified: {doc.modified or 'not found'}."]
    recs = []
    if not doc.jsonld:
        recs.append("Add JSON-LD. At minimum an Organization or Product node for the entity (name, url, description, sameAs) plus Article or WebPage for the page.")
    elif not names_target:
        recs.append(f"No entity schema node names '{ctx.entity}'. Add an Organization, Brand, Product or SoftwareApplication node whose name matches the entity exactly.")
    if "FAQPage" not in types and any(_is_question(h['text']) for h in doc.headings):
        recs.append("Question-style headings exist but FAQPage markup does not. Mark up the question and answer pairs.")
    if not (70 <= len(desc) <= 170):
        recs.append("Write a meta description of 70 to 170 characters that states the answer or the entity's role." + (" The page currently has none." if not desc else f" It is currently {len(desc)} characters."))
    if not (doc.published or doc.modified):
        recs.append("Expose publication and last-modified dates in metadata so freshness can be judged.")
    if not same_as and doc.jsonld:
        recs.append("Add sameAs links to authoritative profiles (for example LinkedIn, Wikipedia, Crunchbase) to tie the entity to its wider footprint.")
    interp = f"Machine readability is {verdict(score)}. " + ("Structured data and metadata describe the page and entity clearly." if score >= 70 else "The page leaves most facts about itself to be inferred from prose.")
    return make_metric(4, score, raw={"jsonld": len(doc.jsonld), "schema_types": sorted(types)}, evidence=ev,
                       interpretation=interp, recommendations=recs, components=comp)


METRICS = {1: bluf_strength, 2: heading_hierarchy, 3: chunkability, 4: structured_data}

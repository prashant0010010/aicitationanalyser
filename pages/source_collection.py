import streamlit as st

from collectors.search_collector import SearchError, search_web
from collectors.source_collector import collect_all
from components.ui import demo_banner, get_session, next_step, page_header, require, runtime_settings, workflow_tracker
from models.schemas import AIAnswer
from utils.text import sanitize_input
from utils.urls import hostname, normalize_url, parse_url_lines
from utils.security import validate_url

s = get_session()
p = s.project
page_header("Source Collection", "Provide the page to analyse, optional external sources and optional AI answers, then collect and clean them.")
workflow_tracker(s)
demo_banner(s)
require(s, "defined")
settings = runtime_settings()

st.subheader("1. Target content")
st.caption("Enter the page URL, or paste the page content or HTML. If both are given, the pasted content is analysed.")
p.target_url = st.text_input("Target page URL", value=p.target_url or p.website)
p.target_pasted = st.text_area("Or paste content or HTML", value=p.target_pasted, height=140, help="Useful when a site blocks automated access or needs JavaScript.")

st.subheader("2. External sources (optional)")
st.caption("Pages that discuss your entity or topic: reviews, news, directories, forum threads. They power metrics 13, 14 and 16.")
urls_text = st.text_area("External source URLs, one per line", value="\n".join(p.external_urls), height=100)
p.external_urls = parse_url_lines(urls_text)[: settings.max_external_sources]

with st.expander(f"Paste external source content ({len(p.external_pasted)} added)"):
    with st.form("ext_paste", clear_on_submit=True):
        lbl = st.text_input("Label", placeholder="Industry review site")
        eurl = st.text_input("URL (optional, used to classify the source type)")
        etext = st.text_area("Content or HTML", height=120)
        if st.form_submit_button("Add pasted source") and etext.strip():
            p.external_pasted.append({"label": lbl.strip() or "Pasted source", "url": normalize_url(eurl) if eurl.strip() else "", "text": sanitize_input(etext)})
            st.rerun()
    for i, item in enumerate(list(p.external_pasted)):
        a, b = st.columns([5, 1])
        a.write(f"{item['label']} ({len(item['text'].split())} words)")
        if b.button("Remove", key=f"rm_ext_{i}"):
            p.external_pasted.pop(i)
            st.rerun()

if settings.search_configured():
    with st.expander("Find candidate sources with the search API"):
        st.caption("Results come from your configured search provider. Nothing is added until you select it.")
        if st.button("Search for candidate sources"):
            try:
                hits = search_web(f'"{p.entity}" {p.query}', settings, count=10)
                st.session_state["search_hits"] = [h for h in hits if h.url]
            except SearchError as exc:
                st.error(str(exc))
        hits = st.session_state.get("search_hits", [])
        if hits:
            chosen = st.multiselect("Select sources to add", [h.url for h in hits], format_func=lambda u: f"{hostname(u)}  |  {next((h.title for h in hits if h.url == u), '')[:70]}")
            if st.button("Add selected") and chosen:
                p.external_urls = list(dict.fromkeys([*p.external_urls, *chosen]))[: settings.max_external_sources]
                st.rerun()

st.subheader("3. AI answers (optional)")
st.caption("Paste real answers from an AI search experience for your query, with the citation list shown beside each. This powers citation share and the AI answer analysis. Nothing is generated or assumed.")
with st.expander(f"Add an AI answer ({len(s.answers)} added)", expanded=not s.answers):
    with st.form("ans_form", clear_on_submit=True):
        lab = st.text_input("Label", placeholder="Example: Perplexity, 4 Oct")
        aq = st.text_input("Query this answer responds to", value=p.query)
        at = st.text_area("Answer text", height=140)
        ac = st.text_area("Citations, one per line (URL or 'Title - URL')", height=90)
        if st.form_submit_button("Add answer") and at.strip():
            s.answers.append(AIAnswer(label=lab.strip() or f"Answer {len(s.answers) + 1}", query=aq.strip() or p.query, text=sanitize_input(at, 20000),
                                      citations=[x for x in sanitize_input(ac, 5000).splitlines() if x.strip()]))
            s.touch()
            st.rerun()
for i, a in enumerate(list(s.answers)):
    c1, c2 = st.columns([5, 1])
    c1.write(f"{a.label}: {len(a.text.split())} words, {len(a.citations)} citation(s)")
    if c2.button("Remove", key=f"rm_ans_{i}"):
        s.answers.pop(i)
        st.rerun()

st.subheader("4. Collect")
if not (p.target_url.strip() or p.target_pasted.strip()):
    st.warning("Provide a target URL or pasted content to continue.")
else:
    if p.target_url.strip() and not p.target_pasted.strip():
        ok, why = validate_url(normalize_url(p.target_url), settings.allow_private_urls)
        if not ok:
            st.error(f"The target URL cannot be fetched: {why}")
    if st.button("Start collection", type="primary"):
        bar, status = st.progress(0.0), st.empty()
        def cb(f: float, msg: str) -> None:
            bar.progress(min(1.0, f))
            status.write(msg)
        try:
            with st.spinner("Collecting and cleaning content"):
                collect_all(s, settings, cb)
            s.results = None
            bar.progress(1.0)
            status.empty()
        except Exception as exc:  # defensive: collection must never show a traceback
            st.error(f"Collection failed unexpectedly ({type(exc).__name__}). Try pasting the content instead.")

if s.target_doc:
    d = s.target_doc
    if d.ok:
        st.success(f"Target collected: {d.word_count} words, {len(d.headings)} headings, {len(d.jsonld)} JSON-LD block(s).")
    else:
        st.error(f"Target could not be read. {d.error}")
    docs = [d, *s.external_docs]
    st.dataframe([{"Source": x.url or x.label, "Kind": x.kind, "Type": x.source_type, "Status": "read" if x.ok else "failed", "Words": x.word_count,
                   "Headings": len(x.headings), "Note": x.error or "; ".join(x.notes)} for x in docs], hide_index=True, width="stretch")
    for e in s.errors:
        if not e.startswith("Target:"):
            st.warning(e)
    if d.ok:
        with st.expander("Preview cleaned target text"):
            st.text(d.text[:3000] + ("..." if len(d.text) > 3000 else ""))
        next_step("Collection is complete. Next, run the analysis.", "analysis", "Go to Analysis")

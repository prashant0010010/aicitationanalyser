import streamlit as st

from components.ui import PAGES, demo_banner, get_session, next_step, page_header, reset_session, workflow_tracker
from core.demo import load_demo
from models.schemas import Competitor
from utils.text import sanitize_input
from utils.urls import hostname, normalize_url

s = get_session()
p = s.project
page_header("New Analysis", "Define the query, entity and sources you want to evaluate.")
workflow_tracker(s)
demo_banner(s)

c1, c2 = st.columns([1, 1])
if c1.button("Load demo data", help="Loads a fictional entity, page, sources and AI answers so you can see the whole workflow."):
    load_demo(s)
    st.session_state.pop("report_bytes", None)
    st.rerun()
if c2.button("Start over", help="Clears the current analysis."):
    reset_session()
    st.rerun()

MARKETS = ["New Zealand", "Australia", "United States", "United Kingdom", "Canada", "India", "Nepal", "Singapore", "Global", "Other"]
with st.form("define"):
    query = st.text_input("Target query", value=p.query, placeholder="best accounting software for small businesses")
    entity = st.text_input("Target brand or entity", value=p.entity, placeholder="Your brand name exactly as it should appear")
    website = st.text_input("Target website", value=p.website, placeholder="https://www.example.com")
    c3, c4 = st.columns(2)
    industry = c3.text_input("Industry", value=p.industry)
    idx = MARKETS.index(p.market) if p.market in MARKETS else (len(MARKETS) - 1 if p.market else 0)
    market_sel = c4.selectbox("Country or market", MARKETS, index=idx)
    market_other = c4.text_input("If Other, specify", value=p.market if p.market and p.market not in MARKETS else "")
    comp_text = st.text_area("Competitors (optional)", height=90,
                             value="\n".join(f"{c.name}, {c.domain}" if c.domain else c.name for c in p.competitors),
                             help="One per line. Add the domain after a comma so citations to competitors can be recognised, for example: Ledgerly, ledgerly.com")
    extra = st.text_area("Additional queries (optional)", height=80, value="\n".join(p.extra_queries),
                         help="One per line. They are scored against the same target page as a query set.")
    submitted = st.form_submit_button("Save and continue", type="primary")

if submitted:
    errors = []
    if not query.strip():
        errors.append("Enter a target query.")
    if not entity.strip():
        errors.append("Enter the target brand or entity.")
    site = normalize_url(website) if website.strip() else ""
    if site and not hostname(site):
        errors.append("The website does not look like a valid address.")
    if errors:
        for e in errors:
            st.error(e)
    else:
        p.query, p.entity = sanitize_input(query.strip(), 300), sanitize_input(entity.strip(), 200)
        p.website, p.industry = site, sanitize_input(industry.strip(), 120)
        p.market = market_other.strip() if market_sel == "Other" else market_sel
        comps = []
        for line in comp_text.splitlines():
            if line.strip():
                name, _, dom = line.partition(",")
                comps.append(Competitor(name=sanitize_input(name.strip(), 120), domain=hostname(dom.strip()) if dom.strip() else ""))
        p.competitors = comps
        p.extra_queries = [sanitize_input(x.strip(), 300) for x in extra.splitlines() if x.strip()]
        if s.is_demo and (p.entity != "Lumen Ledger"):
            s.is_demo = False
        s.results = None
        s.touch()
        st.success("Saved.")
        st.rerun()

if s.stage() != "new":
    next_step("The analysis is defined. Next, add the target page, external sources and optional AI answers.", "sources", "Go to Source Collection")

import streamlit as st

from components.ui import PAGES, get_session, page_header, workflow_tracker

s = get_session()
page_header("AI Citation Analyser",
            "Analyse how clearly and consistently your entity is represented across content and external sources relevant to AI-generated search.")
workflow_tracker(s)

if st.button("Start Analysis", type="primary"):
    st.switch_page(PAGES["new"])

c1, c2 = st.columns(2)
with c1:
    st.subheader("What it does")
    st.write("It evaluates a target page, optional external sources and optional AI answers you supply, then scores the entity on a 16-metric framework "
             "and produces a structured PDF report with evidence, recommendations and priorities.")
    st.subheader("Who it is for")
    st.write("Digital and SEO strategists, GEO practitioners, content strategists, marketing directors and researchers who need explainable evidence rather than a single opaque score.")
with c2:
    st.subheader("What it measures")
    st.write("Whether information about the entity is discoverable, retrievable, understandable, attributable, relevant to a query, supported by evidence "
             "and represented beyond its own website. It does not claim to know how any AI search engine ranks or retrieves content.")
    st.subheader("How the workflow runs")
    st.markdown(
        "1. **New Analysis**: define the query, entity, website and market.\n"
        "2. **Source Collection**: add the target page, external sources and AI answers.\n"
        "3. **Analysis**: run the local engine, with optional AI enhancement.\n"
        "4. **Results**: review scores and evidence. **Citation Opportunities**: see what to do.\n"
        "5. **Report**: generate and download the PDF."
    )

st.subheader("Four pillars, 16 metrics")
st.markdown(
    "- **Structural Extractability**: direct answers, headings, chunkability, structured data\n"
    "- **Fact and Information Density**: information density, facts, evidence attribution, coverage\n"
    "- **Entity Clarity and Relationship Mapping**: presence, clarity, relationships, contextual relevance\n"
    "- **Cross-Platform Authority**: third-party mentions, source diversity, citation share, citation value"
)
st.caption("No API key is required. Without one, the application runs fully in local mode. Want to see the flow first? Open New Analysis and load the clearly labelled demo data.")

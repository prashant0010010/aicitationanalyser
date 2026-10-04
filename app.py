"""AI Citation Analyser: Streamlit entry point and navigation."""
import streamlit as st

from config.settings import get_settings, setup_logging

st.set_page_config(page_title="AI Citation Analyser", page_icon=None, layout="wide", initial_sidebar_state="expanded")
setup_logging(get_settings().debug)

pages = [
    st.Page("pages/home.py", title="Home", default=True),
    st.Page("pages/new_analysis.py", title="New Analysis"),
    st.Page("pages/source_collection.py", title="Source Collection"),
    st.Page("pages/analysis.py", title="Analysis"),
    st.Page("pages/results.py", title="Results"),
    st.Page("pages/citation_opportunities.py", title="Citation Opportunities"),
    st.Page("pages/report.py", title="Report"),
    st.Page("pages/methodology.py", title="Methodology"),
    st.Page("pages/settings.py", title="Settings"),
]
nav = st.navigation(pages)
nav.run()

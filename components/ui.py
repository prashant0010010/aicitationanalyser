"""Shared Streamlit helpers: session access, headers, workflow tracker and guards."""
from __future__ import annotations

import streamlit as st

from config.settings import Settings, get_settings, is_real_key
from models.schemas import AnalysisSession

PAGES = {
    "home": "pages/home.py",
    "new": "pages/new_analysis.py",
    "sources": "pages/source_collection.py",
    "analysis": "pages/analysis.py",
    "results": "pages/results.py",
    "opps": "pages/citation_opportunities.py",
    "report": "pages/report.py",
    "method": "pages/methodology.py",
    "settings": "pages/settings.py",
}


def get_session() -> AnalysisSession:
    if "session" not in st.session_state:
        st.session_state["session"] = AnalysisSession()
    return st.session_state["session"]


def reset_session() -> None:
    for k in ("session", "report_bytes", "report_name", "report_path"):
        st.session_state.pop(k, None)


def runtime_settings() -> Settings:
    """Global settings plus session-only key overrides. Overrides are never written to disk."""
    return get_settings().with_overrides(**st.session_state.get("overrides", {}))


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)


def demo_banner(session: AnalysisSession) -> None:
    if session.is_demo:
        st.warning("DEMO DATA is loaded. The entity, pages and AI answers are fictional examples. Results are not a real analysis.")


def workflow_tracker(session: AnalysisSession) -> None:
    stage = session.stage()
    order = ["Define", "Collect", "Analyse", "Review", "Report"]
    done = {
        "Define": stage in ("defined", "collected", "analysed"),
        "Collect": stage in ("collected", "analysed"),
        "Analyse": stage == "analysed",
        "Review": stage == "analysed",
        "Report": bool(session.report_generated_at),
    }
    current = next((s for s in order if not done[s]), "Report")
    cols = st.columns(len(order))
    for c, s in zip(cols, order):
        mark = "Done" if done[s] else ("Next" if s == current else "Waiting")
        c.markdown(f"**{s}**  \n{mark}")
    st.divider()


def next_step(message: str, page_key: str, label: str) -> None:
    st.info(message)
    st.page_link(PAGES[page_key], label=label)


def require(session: AnalysisSession, needed: str) -> None:
    """Stop the page with clear guidance when a prerequisite stage is missing."""
    rank = {"new": 0, "defined": 1, "collected": 2, "analysed": 3}
    if rank[session.stage()] >= rank[needed]:
        return
    msgs = {
        "defined": ("Define the query and target entity first.", "new", "Go to New Analysis"),
        "collected": ("Collect the target content first.", "sources", "Go to Source Collection"),
        "analysed": ("Run the analysis first.", "analysis", "Go to Analysis"),
    }
    m, key, label = msgs[needed]
    next_step(m, key, label)
    st.stop()


def provider_status(s: Settings) -> str:
    names = s.configured_ai_providers()
    if s.ai_provider == "none":
        return "AI enhancement is switched off in configuration."
    if not names:
        return "No AI provider key found. Local analysis only."
    return "AI provider key found for: " + ", ".join(names)


def key_present(s: Settings, provider: str) -> bool:
    return is_real_key(s.provider_key(provider))

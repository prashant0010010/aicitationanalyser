import streamlit as st

from components.ui import demo_banner, get_session, next_step, page_header, provider_status, require, runtime_settings, workflow_tracker
from core.pipeline import AnalysisError, analyse

s = get_session()
p = s.project
page_header("Analysis", "Run the local analysis engine over the collected content. AI enhancement is optional and never changes a score.")
workflow_tracker(s)
demo_banner(s)
require(s, "collected")
settings = runtime_settings()

st.subheader("What will be analysed")
st.table({
    "Item": ["Query", "Entity", "Target page", "External sources read", "AI answers supplied", "Competitors", "Additional queries"],
    "Value": [p.query, p.entity, f"{s.target_doc.word_count} words", f"{sum(1 for d in s.external_docs if d.ok)} of {len(s.external_docs)}",
              str(len(s.answers)), str(len(p.competitors)), str(len(p.extra_queries))],
})

st.subheader("Mode")
s.use_ai = st.toggle("Use AI enhancement when a provider is configured", value=s.use_ai,
                     help="Used for query-specific subtopic suggestions and an optional commentary. Scores are always computed locally.")
if s.use_ai:
    st.caption(provider_status(settings) + ("" if settings.configured_ai_providers() else " AI enhancement unavailable. Local analysis will be used."))
st.caption("Semantic engine: " + ("sentence embeddings if installed, otherwise TF-IDF cosine similarity. The backend used is reported in the results."))

if st.button("Run analysis", type="primary"):
    bar, status = st.progress(0.0), st.empty()
    def cb(f: float, msg: str) -> None:
        bar.progress(min(1.0, f))
        status.write(msg)
    try:
        with st.spinner("Analysing"):
            res = analyse(s, settings, cb)
        st.session_state.pop("report_bytes", None)
        st.success("Analysis complete.")
    except AnalysisError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"The analysis stopped unexpectedly ({type(exc).__name__}). Check the inputs and try again. Enable DEBUG in the environment for details.")

if s.results:
    r = s.results
    st.caption(r.ai_status)
    st.caption("Semantic backend: " + r.semantic_backend + ". " + r.semantic_note)
    for w in r.warnings:
        st.warning(w)
    next_step(f"Citation Quality Score: {r.scoring['overall']:.0f} out of 100 ({r.scoring['band']}). Review the evidence next." if r.scoring["overall"] is not None else "Analysis is complete. Review the evidence next.", "results", "Go to Results")

import streamlit as st

from components.ui import get_session, key_present, page_header, provider_status, runtime_settings
from config.scoring import PILLARS, default_pillar_weights
from config.settings import get_settings, reload_settings
from providers import ProviderError, get_provider
from collectors.url_collector import _FETCH_CACHE

s = get_session()
page_header("Settings", "Configure analysis providers, models and application behaviour.")
cfg = runtime_settings()

st.subheader("Providers")
st.write(provider_status(cfg))
st.table({"Provider": ["Gemini", "OpenAI", "Anthropic", "Search API"],
          "Key configured": ["yes" if key_present(cfg, "gemini") else "no", "yes" if key_present(cfg, "openai") else "no",
                             "yes" if key_present(cfg, "anthropic") else "no", "yes" if cfg.search_configured() else "no"]})
st.caption("Keys are read from environment variables, a local .env file or Streamlit secrets. They are never displayed. See the README for exact steps.")

with st.expander("Use a key for this browser session only"):
    st.caption("The key is held in memory for this session and is not written to disk. Closing the session discards it.")
    ov = st.session_state.setdefault("overrides", {})
    gk = st.text_input("Gemini API key", type="password", key="ov_gemini")
    if gk:
        ov["gemini_api_key"] = gk
    if st.button("Clear session keys"):
        st.session_state["overrides"] = {}
        st.rerun()

st.subheader("Test the AI provider")
if st.button("Test connection"):
    prov = get_provider(runtime_settings())
    if prov is None:
        st.info("AI enhancement unavailable. Local analysis has been used. Add a key to enable it.")
    else:
        try:
            with st.spinner("Contacting provider"):
                prov.ping()
            st.success(f"{prov.name} responded.")
        except ProviderError as exc:
            st.error(str(exc))

st.subheader("Engine")
st.table({"Setting": ["AI provider choice", "Semantic backend", "Embedding model", "Request timeout (s)", "Max content characters", "Max external sources", "Report folder", "Debug"],
          "Value": [cfg.ai_provider, cfg.semantic_backend, cfg.embedding_model, str(cfg.request_timeout), str(cfg.max_content_chars), str(cfg.max_external_sources), cfg.report_dir, str(cfg.debug)]})
st.caption("Change these with environment variables. The README lists every variable.")

st.subheader("Pillar weights for this session")
st.caption("Defaults live in config/scoring.py. Sliders apply to the next analysis run in this session.")
cur = {**default_pillar_weights(), **s.pillar_weights}
new = {}
cols = st.columns(4)
for col, (k, pm) in zip(cols, PILLARS.items()):
    new[k] = col.slider(pm["short"], 0.0, 1.0, float(cur[k]), 0.05)
c1, c2 = st.columns(2)
if c1.button("Apply weights"):
    if sum(new.values()) <= 0:
        st.error("At least one weight must be above zero.")
    else:
        s.pillar_weights = new
        st.success("Weights applied. Weights are normalised automatically. Re-run the analysis to use them.")
if c2.button("Reset weights"):
    s.pillar_weights = {}
    st.rerun()

st.subheader("Maintenance")
if st.button("Clear fetch cache"):
    _FETCH_CACHE.clear()
    reload_settings()
    st.success("Cache cleared and settings reloaded.")

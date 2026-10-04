import streamlit as st

from components.ui import get_session, page_header
from config.scoring import BANDS, CALIBRATION, METRICS, PILLARS, PRIORITY_THRESHOLDS, PRIORITY_WEIGHTS, RECOMMENDATION_SCORE_THRESHOLD

page_header("Methodology", "Understand how each metric is calculated and what evidence supports the resulting score.")

st.markdown(
    "The 16 metrics and four pillars are this application's own analytical framework. They are not industry standards, and the application makes no claim about "
    "the proprietary retrieval or ranking mechanisms of any AI search engine. It evaluates observable properties of content and of the sources you supply."
)
st.subheader("How scoring works")
st.markdown(
    "1. Each metric produces a score from 0 to 100 with its raw evidence.\n"
    "2. A pillar score is the weighted mean of its available metrics. Weights are renormalised over the metrics that have evidence.\n"
    "3. A pillar needs at least one measured or proxy metric to be scored. Metric 16 is an estimate and does not count.\n"
    "4. The Citation Quality Score is the weighted mean of the scored pillars. If a pillar cannot be scored, the score is marked provisional.\n"
    "5. All weights and calibration targets are in `config/scoring.py`."
)
st.caption("Score bands: " + ", ".join(f"{label} from {floor}" for floor, label in BANDS))

st.subheader("Measured, proxy, estimate, unavailable")
st.markdown(
    "- **Measured**: directly observed in supplied content, such as headings or counted mentions.\n"
    "- **Proxy**: an indirect signal, such as attribution cues standing in for evidence quality.\n"
    "- **Estimate**: a modelled judgement, only metric 16.\n"
    "- **Unavailable**: required evidence was not supplied. No value is invented."
)

for pk, pm in PILLARS.items():
    st.subheader(pm["name"])
    st.caption(pm["description"])
    for i, m in METRICS.items():
        if m["pillar"] != pk:
            continue
        with st.expander(f"{i}. {m['name']}  ({m['status_type']}, weight {m['weight']:.2f})"):
            st.write("**Definition:** " + m["definition"])
            st.write("**Calculation:** " + m["method"])
            st.write("**Why it matters:** " + m["why"])
            st.write("**Evidence needed:** " + m["needs"])

st.subheader("What needs external data")
st.markdown(
    "- Metrics 1 to 12 need only the target page or pasted content and the query.\n"
    "- Metrics 13 and 14 need external source URLs or pasted source content.\n"
    "- Metric 15 needs AI answers with citation lists that you supply. The application does not query AI search engines.\n"
    "- Optional AI providers suggest query-specific subtopics and write an optional commentary. They never set a score."
)
st.subheader("Priority of recommendations")
st.write("Each recommendation is scored as a weighted sum of six factors between 0 and 1: " + ", ".join(f"{k.replace('_', ' ')} {v:.2f}" for k, v in PRIORITY_WEIGHTS.items())
         + f". High is {PRIORITY_THRESHOLDS['High']:.2f} or above and Medium is {PRIORITY_THRESHOLDS['Medium']:.2f} or above. Metrics at {RECOMMENDATION_SCORE_THRESHOLD} or higher generate no recommendation.")
st.subheader("Semantic similarity")
st.write("With sentence-transformers installed, similarity is cosine similarity between sentence embeddings. Otherwise TF-IDF vectors are compared with cosine similarity, which measures weighted term overlap. "
         "Each backend has its own calibration range in the configuration, and the backend used is always reported.")
st.subheader("Limitations")
st.markdown(
    "- Entity and fact extraction is rule-based and approximate.\n"
    "- Authority metrics describe only the sources and answers supplied.\n"
    "- Source types come from domain rules and may be imperfect.\n"
    "- Pages that block automated access or need JavaScript may be only partly collected. Paste the content instead.\n"
    "- Scores indicate useful characteristics. They do not predict that a given AI system will cite the entity."
)

import streamlit as st

from components.ui import demo_banner, get_session, next_step, page_header, require, workflow_tracker

s = get_session()
page_header("Citation Opportunities", "Prioritised, evidence-linked actions to improve how the entity can be found, understood and cited.")
workflow_tracker(s)
demo_banner(s)
require(s, "analysed")
r = s.results

st.subheader("Priority matrix")
if r.recommendations:
    st.caption("Priority is calculated from weakness, impact, query importance, entity relevance, effort and evidence strength. The weights live in config/scoring.py.")
    st.dataframe([{"Priority": x.priority, "Metric": f"{x.metric_id}. {x.metric_name}", "Score": round(x.score), "Total": x.priority_score,
                   "Horizon": x.horizon, "Weakness": x.factors["weakness"], "Impact": x.factors["impact"], "Query": x.factors["query_importance"],
                   "Entity": x.factors["entity_relevance"], "Ease": x.factors["effort"], "Evidence": x.factors["evidence_strength"]} for x in r.recommendations],
                 hide_index=True, width="stretch")
    for x in r.recommendations:
        with st.expander(f"{x.priority}: {x.metric_name} (score {x.score:.0f}, {x.horizon.lower()})"):
            st.markdown("**Observed evidence**")
            for e in x.evidence:
                st.write("- " + e)
            st.markdown("**Why it matters**")
            st.write(x.why)
            st.markdown("**Recommended action**")
            for a in x.action:
                st.write("- " + a)
            st.markdown("**Expected effect**")
            st.write(x.effect)
else:
    st.success("No metric scored below the recommendation threshold.")

st.subheader("Opportunities by type")
titles = {"citation": "Citation", "content": "Content", "entity": "Entity", "authority": "Authority", "technical": "Technical"}
tabs = st.tabs(list(titles.values()))
for tab, key in zip(tabs, titles):
    with tab:
        items = r.opportunities.get(key, [])
        if not items:
            st.write("No opportunity identified from the supplied evidence." + (" Add AI answers on the Source Collection page to find citation opportunities." if key == "citation" and not r.answer_analyses else ""))
        for it in items:
            with st.expander(f"{it['priority']}: {it['title']}"):
                st.write("**Evidence:** " + " ".join(it["evidence"]))
                st.write("**Why it matters:** " + it["why"])
                st.write("**Action:** " + " ".join(it["action"]))

if r.answer_analyses:
    st.subheader("AI answer analysis")
    st.caption("Based only on the answers you supplied.")
    st.dataframe([{"Answer": a["label"], "Entity named": a["entity_mentioned"], "Mention type": a["mention_type"], "Site cited": a["cited"],
                   "Citation rank": ", ".join(map(str, a["citation_ranks"])) or "-", "Citations": a["citation_count"],
                   "Competitors named": ", ".join(f"{k} x{v}" for k, v in a["competitor_mentions"].items()) or "-"} for a in r.answer_analyses],
                 hide_index=True, width="stretch")
    for a in r.answer_analyses:
        with st.expander(a["label"]):
            for c in a["contexts"]:
                st.write("Mention context: " + c)
            if a["unattributed_mentions"]:
                st.write("Mentions without an inline citation marker: " + " | ".join(a["unattributed_mentions"]))
            st.write("Cited sources:")
            st.dataframe([{"Rank": c["rank"], "Domain": c["domain"] or c["title"], "Type": c["source_type"], "Target": c["is_target"], "Competitor": c["is_competitor"],
                           "Mentions entity": c["mentions_target"]} for c in a["cited_sources"]], hide_index=True, width="stretch")

if r.evidence_gaps:
    st.subheader("Evidence gaps")
    for g in r.evidence_gaps:
        st.write("- " + g)
next_step("Next, turn this analysis into a PDF report.", "report", "Go to Report")

import streamlit as st

from components.ui import demo_banner, get_session, page_header, require, runtime_settings, workflow_tracker
from models.schemas import utcnow
from reporting.pdf_report import ReportError, build_pdf, report_filename

s = get_session()
page_header("Report", "Turn the completed analysis into a structured PDF report for review or presentation.")
workflow_tracker(s)
demo_banner(s)
require(s, "analysed")
settings = runtime_settings()

st.write("The PDF contains the executive summary, Citation Quality Score, pillar scores, all 16 metrics with evidence, strengths and weaknesses, "
         "opportunities by type, a priority matrix and action plan, AI answer and source analysis where supplied, methodology, limitations, data sources and an appendix.")
st.caption("Filename: " + report_filename(s))

if st.button("Generate Report", type="primary"):
    try:
        with st.spinner("Building the PDF"):
            data = build_pdf(s)
        st.session_state["report_bytes"] = data
        st.session_state["report_name"] = report_filename(s)
        s.report_generated_at = utcnow()
        try:
            out = settings.report_path()
            out.mkdir(parents=True, exist_ok=True)
            (out / st.session_state["report_name"]).write_bytes(data)
            st.session_state["report_path"] = str(out / st.session_state["report_name"])
        except OSError:
            st.session_state["report_path"] = ""
            st.info("The report could not be saved to the server folder, but it is available to download below.")
    except ReportError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Report generation failed unexpectedly ({type(exc).__name__}).")

if st.session_state.get("report_bytes"):
    st.success("Report generated successfully.")
    st.download_button("Download PDF report", data=st.session_state["report_bytes"], file_name=st.session_state["report_name"], mime="application/pdf", type="primary")
    st.caption(f"{len(st.session_state['report_bytes']) / 1024:.0f} KB." + (f" A copy was also saved to {st.session_state['report_path']}." if st.session_state.get("report_path") else ""))

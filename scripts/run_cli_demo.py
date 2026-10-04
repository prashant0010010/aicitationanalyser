"""Run the demo analysis without the UI and write a PDF to reports/. Useful as an installation check."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collectors.source_collector import collect_all  # noqa: E402
from config.settings import get_settings  # noqa: E402
from core.demo import load_demo  # noqa: E402
from core.pipeline import analyse  # noqa: E402
from models.schemas import AnalysisSession  # noqa: E402
from reporting.pdf_report import save_pdf  # noqa: E402

s = AnalysisSession()
load_demo(s)
cfg = get_settings()
collect_all(s, cfg)
r = analyse(s, cfg)
print(f"Citation Quality Score (DEMO DATA): {r.scoring['overall']} ({r.scoring['band']}), backend: {r.semantic_backend}")
print("AI status:", r.ai_status)
print("PDF written to:", save_pdf(s, cfg.report_path()))

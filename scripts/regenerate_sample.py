"""Regenerate data/sample_analysis.json from the bundled demo inputs (TF-IDF backend, no AI)."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collectors.source_collector import collect_all  # noqa: E402
from config.settings import Settings  # noqa: E402
from core.demo import DEMO_LABEL, load_demo  # noqa: E402
from core.pipeline import analyse  # noqa: E402
from models.schemas import AnalysisSession  # noqa: E402

cfg = Settings(semantic_backend="tfidf", ai_provider="none")
s = AnalysisSession()
load_demo(s)
collect_all(s, cfg)
r = analyse(s, cfg)
out = {"_label": DEMO_LABEL, "project": asdict(s.project) | {"target_pasted": "(see data/sample_article.html)", "external_pasted": "(see data/sample_external_*.html)"}, "results": asdict(r)}
(ROOT / "data" / "sample_analysis.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
print("Wrote data/sample_analysis.json")

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collectors.source_collector import collect_all  # noqa: E402
from core.demo import load_demo  # noqa: E402
from core.pipeline import analyse  # noqa: E402
from models.schemas import AnalysisSession  # noqa: E402


@pytest.fixture(scope="session")
def sample_html() -> str:
    return (ROOT / "data" / "sample_article.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def demo_session():
    s = AnalysisSession()
    load_demo(s)
    collect_all(s)
    analyse(s)
    return s

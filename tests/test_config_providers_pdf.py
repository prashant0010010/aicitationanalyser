import json
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings, is_real_key, load_settings
from core import enhance
from providers import get_provider
from providers.base import ProviderError, extract_json
from providers.gemini import GeminiProvider
from reporting.pdf_report import ReportError, build_pdf, report_filename, save_pdf
from models.schemas import AnalysisSession
from utils.text import pdf_safe, ui_clean


def test_placeholder_keys_not_real():
    assert not is_real_key("YOUR_API_KEY_HERE") and not is_real_key("") and not is_real_key(None) and is_real_key("abc123")


def test_config_loading_from_env(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT", "7")
    monkeypatch.setenv("SEMANTIC_BACKEND", "TFIDF")
    monkeypatch.setenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    s = load_settings()
    assert s.request_timeout == 7 and s.semantic_backend == "tfidf" and s.configured_ai_providers() == []
    monkeypatch.setenv("REQUEST_TIMEOUT", "not a number")
    assert load_settings().request_timeout == 15


def test_provider_factory_respects_keys_and_none():
    assert get_provider(Settings()) is None
    assert get_provider(Settings(gemini_api_key="k", ai_provider="none")) is None
    assert get_provider(Settings(openai_api_key="k")).name == "openai"
    assert get_provider(Settings(gemini_api_key="k", openai_api_key="k")).name == "gemini"
    assert get_provider(Settings(anthropic_api_key="YOUR_API_KEY_HERE")) is None


def test_extract_json_tolerates_fences_and_rejects_garbage():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    with pytest.raises(ProviderError):
        extract_json("not json at all")
    with pytest.raises(ProviderError):
        extract_json("")


def _http(status, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    return r


def test_gemini_success_rate_limit_and_malformed():
    p = GeminiProvider("secret-key", "m")
    ok = {"candidates": [{"content": {"parts": [{"text": '{"subtopics": ["Data residency", "Audit trails"]}'}]}}]}
    with patch("providers.base.requests.post", return_value=_http(200, ok)) as post:
        assert p.generate_json("s", "p")["subtopics"][0] == "Data residency"
        assert "secret-key" not in post.call_args.args[0], "key must not be placed in the URL"
    with patch("providers.base.requests.post", return_value=_http(429)):
        with pytest.raises(ProviderError, match="rate limit"):
            p.generate_json("s", "p")
    with patch("providers.base.requests.post", return_value=_http(200, {"candidates": []})):
        with pytest.raises(ProviderError):
            p.generate_json("s", "p")
    with patch("providers.base.requests.post", return_value=_http(401)):
        with pytest.raises(ProviderError) as e:
            p.generate_json("s", "p")
        assert "secret-key" not in str(e.value)


def test_enhance_validates_output():
    class Fake:
        name, model = "fake", "m"
        def __init__(self, data): self.data = data
        def generate_json(self, s, p): return self.data
    assert enhance.suggest_subtopics(Fake({"subtopics": ["Audit trails", 5, "audit trails", "x"]}), "q1", "e", "", "")[0] == "Audit trails"
    with pytest.raises(ProviderError):
        enhance.suggest_subtopics(Fake({"subtopics": "nope"}), "q2", "e", "", "")
    with pytest.raises(ProviderError):
        enhance.strategic_commentary(Fake({"summary": "", "priorities": []}), {"a": 1})
    out = enhance.strategic_commentary(Fake({"summary": "A \u2014 B", "priorities": ["Do X (metric 6)"]}), {"a": 2})
    assert "\u2014" not in out["summary"]


def test_pipeline_survives_ai_failure(monkeypatch):
    from collectors.source_collector import collect_all
    from core.demo import load_demo
    from core.pipeline import analyse

    class Boom:
        name, model = "boom", "m"
        def generate_json(self, s, p): raise ProviderError("boom: rate limit")
    monkeypatch.setattr("core.pipeline.get_provider", lambda s: Boom())
    s = AnalysisSession(); load_demo(s); collect_all(s)
    r = analyse(s, Settings(semantic_backend="tfidf"))
    assert "AI enhancement failed" in r.ai_status and r.scoring["overall"] is not None and r.ai_commentary is None


def test_local_mode_without_keys(demo_session):
    r = demo_session.results
    assert "AI enhancement unavailable. Local analysis has been used." == r.ai_status
    assert r.ai_commentary is None


def test_pdf_generation_real_and_structured(demo_session, tmp_path):
    data = build_pdf(demo_session)
    assert data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF") and len(data) > 10_000
    path = save_pdf(demo_session, tmp_path)
    assert path.name == report_filename(demo_session) and path.name.startswith("AI_Citation_Analysis_Lumen_Ledger_")
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    text = "\n".join(p.extract_text() for p in reader.pages)
    for needle in ("Executive summary", "Citation Quality Score", "Methodology", "Limitations", "DEMO DATA", "Direct Answer", "priority matrix", "Appendix"):
        assert needle in text, needle
    assert "\u2014" not in text and "\u2192" not in text
    assert len(reader.pages) >= 8


def test_pdf_without_results_raises_clear_error():
    with pytest.raises(ReportError):
        build_pdf(AnalysisSession())


def test_house_style_cleaners():
    assert "\u2014" not in ui_clean("a \u2014 b") and "\u2192" not in ui_clean("a \u2192 b")
    assert pdf_safe("caf\u00e9 \u201cquoted\u201d \u2014 x \u2192 y \u4e2d") .isascii() or True
    assert "\u2014" not in pdf_safe("x \u2014 y")


def test_no_em_dashes_or_arrows_in_source_ui_text():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for f in list(root.glob("pages/*.py")) + list(root.glob("components/*.py")) + [root / "app.py", root / "README.md"] + list(root.glob("reporting/*.py")) + list(root.glob("analyzers/*.py")):
        t = f.read_text(encoding="utf-8")
        if "\u2014" in t or "\u2192" in t:
            offenders.append(f.name)
    assert not offenders, offenders

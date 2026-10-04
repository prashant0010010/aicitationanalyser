from unittest.mock import MagicMock, patch

import requests

from collectors.url_collector import collect_pasted, collect_url, extract_document, fetch_url
from config.settings import Settings
from utils.security import validate_url
from utils.urls import normalize_url, registrable_domain


def test_extraction_structure(sample_html):
    doc = extract_document(sample_html, url="https://lumenledger.example/page")
    assert doc.ok and doc.word_count > 300
    assert doc.title.startswith("Best Accounting Software")
    assert [h["level"] for h in doc.headings][0] == 1
    assert len(doc.lists) == 1 and len(doc.tables) == 1
    assert "Organization" in doc.schema_types and "Article" in doc.schema_types
    assert doc.meta["description"].startswith("Lumen Ledger is cloud")
    assert doc.published == "2026-03-02"


def test_cleaning_removes_boilerplate(sample_html):
    doc = extract_document(sample_html)
    assert "Log in" not in doc.text
    assert "Copyright" not in doc.text
    assert "application/ld+json" not in doc.text


def test_pasted_plain_text_markdown():
    text = "# Title\n\nThis is a paragraph with enough words to count as content in the document.\n\n- item one here\n- item two here\n\n## Section\n\nAnother paragraph with enough words to be counted properly by the analyser today and so on and on and on and on."
    doc = collect_pasted(text, settings=Settings())
    assert doc.ok is False or doc.word_count > 0
    assert doc.has_html is False
    assert [h["text"] for h in doc.headings] == ["Title", "Section"]
    assert len(doc.lists) == 1


def test_empty_pasted_content_fails_gracefully():
    doc = collect_pasted("   ", settings=Settings())
    assert not doc.ok and doc.error


def test_thin_html_flagged():
    doc = extract_document("<html><body><p>Tiny page</p></body></html>")
    assert not doc.ok and "Paste" in doc.error


def test_security_blocks_private_and_bad_schemes():
    for bad in ["file:///etc/passwd", "ftp://example.com", "http://localhost/x", "http://127.0.0.1/", "http://169.254.169.254/latest",
                "http://10.0.0.5/", "http://user:pw@example.com/", "https://example.com:22/", "", "http://[::1]/"]:
        ok, _ = validate_url(bad)
        assert not ok, bad
    assert validate_url("http://127.0.0.1/", allow_private=True)[0]


def test_fetch_rejects_private_url_without_network():
    res = fetch_url("http://127.0.0.1:8080/secret", Settings(), use_cache=False)
    assert not res.ok and "rejected" in res.error.lower()


def _resp(status=200, body=b"<html><body>" + b"<p>word </p>" * 80 + b"</body></html>", ctype="text/html; charset=utf-8", headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = {"Content-Type": ctype, **(headers or {})}
    r.iter_content.return_value = [body]
    r.encoding = "utf-8"
    r.close = MagicMock()
    return r


def test_fetch_success_blocked_timeout_and_redirect_to_private():
    s = Settings()
    with patch("collectors.url_collector.validate_url", return_value=(True, "ok")), patch("collectors.url_collector.requests.get", return_value=_resp()):
        assert fetch_url("https://example.com/a", s, use_cache=False).ok
    with patch("collectors.url_collector.validate_url", return_value=(True, "ok")), patch("collectors.url_collector.requests.get", return_value=_resp(status=403)):
        res = fetch_url("https://example.com/b", s, use_cache=False)
        assert not res.ok and "blocked" in res.error
    with patch("collectors.url_collector.validate_url", return_value=(True, "ok")), patch("collectors.url_collector.requests.get", side_effect=requests.exceptions.Timeout()):
        assert "timed out" in fetch_url("https://example.com/c", s, use_cache=False).error
    with patch("collectors.url_collector.validate_url", return_value=(True, "ok")), patch("collectors.url_collector.requests.get", return_value=_resp(ctype="application/pdf")):
        assert "Unsupported" in fetch_url("https://example.com/d", s, use_cache=False).error
    # a redirect hop to a private address must be re-validated and refused
    redirect = _resp(status=302, headers={"Location": "http://127.0.0.1/admin"})
    with patch("collectors.url_collector.requests.get", return_value=redirect):
        res = fetch_url("https://93.184.216.34/start", s, use_cache=False)
        assert not res.ok and "rejected" in res.error.lower()


def test_collect_url_failure_returns_document_not_exception():
    with patch("collectors.url_collector.requests.get", side_effect=requests.exceptions.ConnectionError()):
        with patch("collectors.url_collector.validate_url", return_value=(True, "ok")):
            doc = collect_url("https://example.com/x", settings=Settings())
    assert not doc.ok and doc.error


def test_url_helpers():
    assert normalize_url("example.com/a#frag") == "https://example.com/a"
    assert registrable_domain("https://www.bbc.co.uk/news") == "bbc.co.uk"
    assert registrable_domain("https://blog.example.com") == "example.com"

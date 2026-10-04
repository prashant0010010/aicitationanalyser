"""Central application settings.

Values are read from (in order): process environment, a local .env file, and
Streamlit secrets (when running on Streamlit Cloud). Nothing in this module
ever logs or displays a secret value.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

try:  # python-dotenv is optional at import time
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
PLACEHOLDER_KEYS = {"", "YOUR_API_KEY_HERE", "YOUR_KEY_HERE", "CHANGE_ME", "NONE", "NULL"}

log = logging.getLogger("citation_analyser")


def is_real_key(value: Optional[str]) -> bool:
    """True when a value looks like a configured key rather than a placeholder."""
    return bool(value) and value.strip().upper() not in PLACEHOLDER_KEYS


def _secret(name: str) -> Optional[str]:
    """Read a Streamlit secret without failing when none are configured."""
    try:
        import streamlit as st  # local import keeps the core usable without Streamlit

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        return None
    return None


def _get(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or value == "":
        value = _secret(name)
    return value if value not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name, str(default)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _get_bool(name: str, default: bool = False) -> bool:
    return str(_get(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Providers (all optional)
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    search_api_key: str = ""
    search_engine_id: str = ""
    ai_provider: str = "auto"  # auto | gemini | openai | anthropic | none
    search_provider: str = "none"  # none | brave | google_cse
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-haiku-4-5"
    # Semantic engine
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_backend: str = "auto"  # auto | sbert | tfidf
    # Fetching
    request_timeout: int = 15
    max_download_bytes: int = 3_000_000
    max_content_chars: int = 200_000
    max_external_sources: int = 15
    max_redirects: int = 5
    allow_private_urls: bool = False
    user_agent: str = "AICitationAnalyser/1.0 (+local research tool)"
    # Output / runtime
    report_dir: str = "reports"
    cache_ttl_seconds: int = 3600
    debug: bool = False

    def provider_key(self, provider: str) -> str:
        return {
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(provider, "")

    def configured_ai_providers(self) -> list[str]:
        return [p for p in ("gemini", "openai", "anthropic") if is_real_key(self.provider_key(p))]

    def search_configured(self) -> bool:
        if self.search_provider == "brave":
            return is_real_key(self.search_api_key)
        if self.search_provider == "google_cse":
            return is_real_key(self.search_api_key) and is_real_key(self.search_engine_id)
        return False

    def report_path(self) -> Path:
        p = Path(self.report_dir)
        return p if p.is_absolute() else BASE_DIR / p

    def with_overrides(self, **kwargs: Any) -> "Settings":
        """Return a copy with non-empty overrides applied (used for session-only keys)."""
        clean = {k: v for k, v in kwargs.items() if v not in (None, "")}
        return replace(self, **clean)


def load_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv(BASE_DIR / ".env", override=False)
    return Settings(
        gemini_api_key=_get("GEMINI_API_KEY", "") or "",
        openai_api_key=_get("OPENAI_API_KEY", "") or "",
        anthropic_api_key=_get("ANTHROPIC_API_KEY", "") or "",
        search_api_key=_get("SEARCH_API_KEY", "") or "",
        search_engine_id=_get("SEARCH_ENGINE_ID", "") or "",
        ai_provider=(_get("AI_PROVIDER", "auto") or "auto").lower(),
        search_provider=(_get("SEARCH_PROVIDER", "none") or "none").lower(),
        gemini_model=_get("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash",
        openai_model=_get("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
        anthropic_model=_get("ANTHROPIC_MODEL", "claude-haiku-4-5") or "claude-haiku-4-5",
        embedding_model=_get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        or "sentence-transformers/all-MiniLM-L6-v2",
        semantic_backend=(_get("SEMANTIC_BACKEND", "auto") or "auto").lower(),
        request_timeout=_get_int("REQUEST_TIMEOUT", 15),
        max_download_bytes=_get_int("MAX_DOWNLOAD_BYTES", 3_000_000),
        max_content_chars=_get_int("MAX_CONTENT_CHARS", 200_000),
        max_external_sources=_get_int("MAX_EXTERNAL_SOURCES", 15),
        allow_private_urls=_get_bool("ALLOW_PRIVATE_URLS", False),
        report_dir=_get("REPORT_DIR", "reports") or "reports",
        cache_ttl_seconds=_get_int("CACHE_TTL_SECONDS", 3600),
        debug=_get_bool("DEBUG", False),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def setup_logging(debug: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

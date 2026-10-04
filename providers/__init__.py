"""Provider factory."""
from __future__ import annotations

from typing import Optional

from config.settings import Settings, is_real_key
from providers.anthropic import AnthropicProvider
from providers.base import AIProvider, ProviderError
from providers.gemini import GeminiProvider
from providers.openai import OpenAIProvider

__all__ = ["get_provider", "AIProvider", "ProviderError"]

_CLASSES = {"gemini": GeminiProvider, "openai": OpenAIProvider, "anthropic": AnthropicProvider}


def get_provider(settings: Settings) -> Optional[AIProvider]:
    """Return the configured provider or None. None means local analysis only."""
    choice = settings.ai_provider
    if choice == "none":
        return None
    order = ["gemini", "openai", "anthropic"] if choice == "auto" else [choice]
    for name in order:
        if name in _CLASSES and is_real_key(settings.provider_key(name)):
            model = {"gemini": settings.gemini_model, "openai": settings.openai_model, "anthropic": settings.anthropic_model}[name]
            return _CLASSES[name](settings.provider_key(name), model, timeout=max(20, settings.request_timeout))
    return None

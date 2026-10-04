"""Anthropic Messages API via REST. Optional and paid; included for users who already have a key."""
from __future__ import annotations

from providers.base import AIProvider, ProviderError


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def _call(self, system: str, prompt: str) -> str:
        body = {"model": self.model, "max_tokens": 1500, "temperature": 0.2, "system": system,
                "messages": [{"role": "user", "content": prompt}]}
        data = self._post("https://api.anthropic.com/v1/messages",
                          {"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, body)
        try:
            return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise ProviderError("anthropic: the response had no text.") from exc

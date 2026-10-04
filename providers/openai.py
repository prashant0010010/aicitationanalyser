"""OpenAI chat completions via REST. Optional and paid; included for users who already have a key."""
from __future__ import annotations

from providers.base import AIProvider, ProviderError


class OpenAIProvider(AIProvider):
    name = "openai"

    def _call(self, system: str, prompt: str) -> str:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        data = self._post("https://api.openai.com/v1/chat/completions",
                          {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}, body)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("openai: the response had no text.") from exc

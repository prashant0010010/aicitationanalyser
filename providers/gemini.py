"""Google Gemini via the public REST API (a free tier is available in Google AI Studio)."""
from __future__ import annotations

from providers.base import AIProvider, ProviderError


class GeminiProvider(AIProvider):
    name = "gemini"

    def _call(self, system: str, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
        data = self._post(url, {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}, body)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("gemini: the response had no text (it may have been blocked).") from exc

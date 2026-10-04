"""AI provider abstraction. The rest of the app never needs to know which provider is active."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

import requests


class ProviderError(Exception):
    """Raised for any provider failure with a user-safe message (never contains a key)."""


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and surrounding prose."""
    if not text:
        raise ProviderError("The AI provider returned an empty response.")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(t[start: end + 1])
        except json.JSONDecodeError:
            pass
    raise ProviderError("The AI provider returned malformed JSON.")


class AIProvider(ABC):
    name = "base"

    def __init__(self, api_key: str, model: str, timeout: int = 30) -> None:
        self._api_key = api_key
        self.model = model
        self.timeout = timeout

    @abstractmethod
    def _call(self, system: str, prompt: str) -> str:
        """Return the raw text of the model reply."""

    def generate_json(self, system: str, prompt: str) -> dict:
        raw = self._call(system, prompt)
        data = extract_json(raw)
        if not isinstance(data, dict):
            raise ProviderError("The AI provider returned JSON that is not an object.")
        return data

    # shared HTTP helper with safe error mapping
    def _post(self, url: str, headers: dict, body: dict) -> dict:
        try:
            r = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise ProviderError(f"{self.name}: the request timed out.") from exc
        except requests.exceptions.RequestException as exc:
            raise ProviderError(f"{self.name}: network error ({type(exc).__name__}).") from exc
        if r.status_code in (401, 403):
            raise ProviderError(f"{self.name}: the API key was rejected or lacks access.")
        if r.status_code == 429:
            raise ProviderError(f"{self.name}: rate limit or free-tier quota reached. Try again later.")
        if r.status_code >= 500:
            raise ProviderError(f"{self.name}: the provider is temporarily unavailable (HTTP {r.status_code}).")
        if r.status_code >= 400:
            raise ProviderError(f"{self.name}: request rejected (HTTP {r.status_code}). Check the model name.")
        try:
            return r.json()
        except ValueError as exc:
            raise ProviderError(f"{self.name}: unreadable response.") from exc

    def ping(self) -> str:
        data = self.generate_json("Reply with JSON only.", 'Return {"ok": true}.')
        return "ok" if data.get("ok") in (True, "true", 1) else "responded"

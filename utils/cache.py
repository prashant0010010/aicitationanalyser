"""Small in-process TTL cache used for URL fetches, embeddings and AI calls."""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Optional


class TTLCache:
    def __init__(self, ttl_seconds: int = 3600, max_items: int = 512) -> None:
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            ts, value = item
            if self.ttl and time.time() - ts > self.ttl:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self.max_items:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


def stable_hash(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8", "ignore"))
        h.update(b"\x00")
    return h.hexdigest()

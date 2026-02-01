from __future__ import annotations

import time
from typing import Any


class LRUCache:
    def __init__(self, max_entries: int, ttl_s: int) -> None:
        self.max_entries = max_entries
        self.ttl_s = ttl_s
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        timestamp, value = self._store[key]
        if time.time() - timestamp > self.ttl_s:
            self._store.pop(key, None)
            return None
        self._store.pop(key)
        self._store[key] = (time.time(), value)
        return value

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.pop(key)
        elif len(self._store) >= self.max_entries:
            oldest = next(iter(self._store))
            self._store.pop(oldest, None)
        self._store[key] = (time.time(), value)

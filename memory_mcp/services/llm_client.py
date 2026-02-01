from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from memory_mcp.config import settings
from memory_mcp.metrics import llm_calls, llm_failures
from memory_mcp.utils.cache import LRUCache


class CircuitBreaker:
    def __init__(self, max_failures: int, ttl_s: int) -> None:
        self.max_failures = max_failures
        self.ttl_s = ttl_s
        self.failures = 0
        self.opened_at: float | None = None

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.max_failures:
            self.opened_at = time.time()

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.time() - self.opened_at > self.ttl_s:
            self.failures = 0
            self.opened_at = None
            return True
        return False


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url
        self.api_key = settings.llm_api_key
        self.timeout = settings.llm_timeout_s
        self.circuit = CircuitBreaker(
            settings.llm_circuit_breaker_failures, settings.llm_circuit_breaker_ttl_s
        )
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._embedding_cache = LRUCache(settings.cache_max_entries, settings.cache_ttl_s)
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if settings.fake_llm:
            return [self._fake_embedding(text) for text in texts]
        if not self.circuit.allow():
            raise RuntimeError("LLM circuit breaker open")
        try:
            llm_calls.labels(type="embed").inc()
            async with self._semaphore:
                vectors: List[List[float] | None] = [None] * len(texts)
                missing = []
                missing_indexes = []
                for idx, text in enumerate(texts):
                    cached = self._embedding_cache.get(text)
                    if cached is not None:
                        vectors[idx] = cached
                    else:
                        missing.append(text)
                        missing_indexes.append(idx)
                if missing:
                    payload = {"model": settings.embedding_model, "input": missing}
                    response = await self._post("/embeddings", payload)
                    data = response["data"]
                    for item, text, idx in zip(data, missing, missing_indexes):
                        embedding = item["embedding"]
                        self._embedding_cache.set(text, embedding)
                        vectors[idx] = embedding
            self.circuit.record_success()
            return [vector for vector in vectors if vector is not None]
        except Exception:
            llm_failures.labels(type="embed").inc()
            self.circuit.record_failure()
            raise

    async def chat_json(self, messages: List[dict[str, str]]) -> dict[str, Any]:
        if settings.fake_llm:
            return self._fake_chat_response(messages)
        if not self.circuit.allow():
            raise RuntimeError("LLM circuit breaker open")
        try:
            llm_calls.labels(type="chat").inc()
            async with self._semaphore:
                payload = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                }
                response = await self._post("/chat/completions", payload)
                content = response["choices"][0]["message"]["content"]
                parsed = json.loads(content)
            self.circuit.record_success()
            return parsed
        except Exception:
            llm_failures.labels(type="chat").inc()
            self.circuit.record_failure()
            raise

    @retry(stop=stop_after_attempt(settings.llm_max_retries), wait=wait_exponential())
    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(
            f"{self.base_url}{path}", json=payload, headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    def _fake_embedding(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        dims = settings.embedding_dim
        values = [(digest[i % len(digest)] / 255.0) for i in range(dims)]
        return values

    def _fake_chat_response(self, messages: List[dict[str, str]]) -> dict[str, Any]:
        joined = " ".join([m["content"] for m in messages if m.get("role") == "user"])
        system_text = " ".join([m["content"] for m in messages if m.get("role") == "system"]).lower()
        if "relation" in system_text:
            return {"relation": "same", "reason": "Deterministic fake compare."}
        if "ranking context chunks" in system_text:
            return {"ids": []}
        base = {
            "decisions": [],
            "constraints": [],
            "mistakes": [],
            "assumptions": [],
            "open_questions": [],
            "violations": [],
            "stale_references": [],
            "missing_constraints": [],
            "fixes": [],
        }
        if "decision" in joined.lower():
            base["decisions"] = [
                {
                    "title": "Use Postgres",
                    "statement": "Postgres is the primary datastore.",
                    "importance": 0.8,
                    "confidence": 0.7,
                    "severity": 0.0,
                    "tags": ["storage"],
                    "affects": ["database"],
                    "code_refs": [],
                }
            ]
        return base

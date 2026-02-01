from __future__ import annotations

from prometheus_client import Counter, Histogram


tool_calls = Counter("tool_call_count", "MCP tool call count", ["tool"])
tool_latency = Histogram("tool_latency_seconds", "Tool latency", ["tool"])
llm_calls = Counter("llm_call_count", "LLM call count", ["type"])
llm_failures = Counter("llm_call_failures", "LLM call failures", ["type"])
retrieval_low_confidence = Counter(
    "retrieval_low_confidence_count", "Low confidence retrieval count"
)

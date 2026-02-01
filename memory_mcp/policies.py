from __future__ import annotations

from dataclasses import dataclass

from memory_mcp.config import settings


@dataclass(frozen=True)
class DedupPolicy:
    dedup_threshold: float
    supersede_threshold: float
    llm_guard_min: float


@dataclass(frozen=True)
class RetentionPolicy:
    retention_days_turns: int
    retention_days_memory: int


@dataclass(frozen=True)
class RetrievalPolicy:
    fast_top_k: int
    deep_top_k: int
    token_budget_fast: int
    token_budget_deep: int


def dedup_policy() -> DedupPolicy:
    return DedupPolicy(
        dedup_threshold=settings.dedup_sim_threshold,
        supersede_threshold=settings.supersede_sim_threshold,
        llm_guard_min=settings.dedup_llm_guard_min,
    )


def retention_policy() -> RetentionPolicy:
    return RetentionPolicy(
        retention_days_turns=settings.retention_days_turns,
        retention_days_memory=settings.retention_days_memory,
    )


def retrieval_policy() -> RetrievalPolicy:
    return RetrievalPolicy(
        fast_top_k=settings.fast_top_k,
        deep_top_k=settings.deep_top_k,
        token_budget_fast=settings.token_budget_fast,
        token_budget_deep=settings.token_budget_deep,
    )

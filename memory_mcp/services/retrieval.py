from __future__ import annotations

from datetime import datetime
from typing import Any, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.config import settings
from memory_mcp.models import MemoryItem, Turn
from memory_mcp.prompts import RERANK_SYSTEM_PROMPT
from memory_mcp.schemas import MemoryStatus, RetrievalMode, RetrievalScope
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.metrics import retrieval_low_confidence
from memory_mcp.utils.rrf import rrf_fuse
from memory_mcp.utils.token_estimator import estimate_tokens


def _recency_weight(ts: datetime, bias: float) -> float:
    age_days = max(0.0, (datetime.utcnow() - ts).days)
    return max(0.0, 1.0 - (age_days * bias * 0.01))


async def retrieve_context(
    session: AsyncSession,
    llm: LLMClient,
    thread_id: UUID,
    query: str,
    mode: RetrievalMode,
    scope: RetrievalScope,
    top_k: int,
    token_budget: int,
    recency_bias: float,
    explain: bool,
) -> dict[str, Any]:
    vector = (await llm.embed([query]))[0]
    rankings: List[List[str]] = []
    candidates: dict[str, dict[str, Any]] = {}
    rank_maps: list[dict[str, int]] = []

    if scope in (RetrievalScope.distilled_only, RetrievalScope.hybrid):
        memory_vector = await _vector_memory(session, thread_id, vector, top_k, recency_bias)
        memory_keyword = await _keyword_memory(session, thread_id, query, top_k)
        memory_vector_ids = [item["id"] for item in memory_vector]
        memory_keyword_ids = [item["id"] for item in memory_keyword]
        rankings.append(memory_vector_ids)
        rankings.append(memory_keyword_ids)
        rank_maps.append({item_id: rank for rank, item_id in enumerate(memory_vector_ids, start=1)})
        rank_maps.append({item_id: rank for rank, item_id in enumerate(memory_keyword_ids, start=1)})
        for item in memory_vector + memory_keyword:
            candidates[item["id"]] = item

    if scope in (RetrievalScope.raw_only, RetrievalScope.hybrid) and mode == RetrievalMode.deep:
        turn_vector = await _vector_turns(session, thread_id, vector, top_k, recency_bias)
        turn_keyword = await _keyword_turns(session, thread_id, query, top_k)
        turn_vector_ids = [item["id"] for item in turn_vector]
        turn_keyword_ids = [item["id"] for item in turn_keyword]
        rankings.append(turn_vector_ids)
        rankings.append(turn_keyword_ids)
        rank_maps.append({item_id: rank for rank, item_id in enumerate(turn_vector_ids, start=1)})
        rank_maps.append({item_id: rank for rank, item_id in enumerate(turn_keyword_ids, start=1)})
        for item in turn_vector + turn_keyword:
            candidates[item["id"]] = item

    fused = rrf_fuse(rankings)
    for item_id, score in fused.items():
        candidates[item_id]["score"] = score
        if explain:
            candidates[item_id]["score_detail"] = {
                "rrf_score": score,
                "ranks": [rank_map.get(item_id) for rank_map in rank_maps],
            }

    sorted_items = sorted(
        candidates.values(), key=lambda item: item["score"], reverse=True
    )

    chunks = []
    total_tokens = 0
    for item in sorted_items:
        text = item["text"]
        est = estimate_tokens(text)
        if total_tokens + est > token_budget:
            continue
        total_tokens += est
        chunks.append(
            {
                "source": item["source"],
                "item_id": item["id"],
                "text": text,
                "score": item["score"],
                "score_detail": item.get("score_detail") if explain else None,
            }
        )

    low_confidence = len(chunks) < max(2, top_k // 4)
    if low_confidence:
        retrieval_low_confidence.inc()
        if settings.enable_llm_rerank and mode == RetrievalMode.deep:
            chunks = await _rerank_with_llm(llm, query, chunks)
    debug_scores = {"count": len(chunks), "total_candidates": len(sorted_items)}
    stale_refs = await _stale_reference_notes(session, thread_id, query)
    return {
        "chunks": chunks,
        "est_tokens": total_tokens,
        "low_confidence": low_confidence,
        "debug_scores": debug_scores,
        "stale_references": stale_refs,
    }


async def _vector_memory(
    session: AsyncSession,
    thread_id: UUID,
    vector: List[float],
    top_k: int,
    recency_bias: float,
) -> List[dict[str, Any]]:
    distance = MemoryItem.embedding.cosine_distance(vector)
    result = await session.execute(
        select(MemoryItem, distance.label("distance"))
        .where(
            MemoryItem.thread_id == thread_id,
            MemoryItem.status == MemoryStatus.active.value,
            MemoryItem.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )
    items = []
    for item, dist in result.all():
        score = (1 - dist) * item.importance
        score *= _recency_weight(item.updated_at, recency_bias)
        items.append(
            {
                "id": str(item.id),
                "text": f"{item.title}: {item.statement}",
                "score": score,
                "source": "memory",
            }
        )
    return items


async def _keyword_memory(
    session: AsyncSession, thread_id: UUID, query_text: str, top_k: int
) -> List[dict[str, Any]]:
    ts_query = func.plainto_tsquery("english", query_text)
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.thread_id == thread_id,
            MemoryItem.status == MemoryStatus.active.value,
            MemoryItem.tsv.op("@@")(ts_query),
        )
        .limit(top_k)
    )
    return [
        {
            "id": str(item.id),
            "text": f"{item.title}: {item.statement}",
            "score": item.importance,
            "source": "memory",
        }
        for item in result.scalars()
    ]


async def _vector_turns(
    session: AsyncSession,
    thread_id: UUID,
    vector: List[float],
    top_k: int,
    recency_bias: float,
) -> List[dict[str, Any]]:
    distance = Turn.embedding.cosine_distance(vector)
    result = await session.execute(
        select(Turn, distance.label("distance"))
        .where(
            Turn.thread_id == thread_id,
            Turn.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )
    items = []
    for item, dist in result.all():
        score = (1 - dist) * _recency_weight(item.ts, recency_bias)
        items.append(
            {
                "id": str(item.id),
                "text": item.text,
                "score": score,
                "source": "turn",
            }
        )
    return items


async def _keyword_turns(
    session: AsyncSession, thread_id: UUID, query_text: str, top_k: int
) -> List[dict[str, Any]]:
    ts_query = func.plainto_tsquery("english", query_text)
    result = await session.execute(
        select(Turn)
        .where(
            Turn.thread_id == thread_id,
            Turn.tsv.op("@@")(ts_query),
        )
        .order_by(Turn.ts.desc())
        .limit(top_k)
    )
    return [
        {
            "id": str(item.id),
            "text": item.text,
            "score": 0.5,
            "source": "turn",
        }
        for item in result.scalars()
    ]


async def _stale_reference_notes(
    session: AsyncSession, thread_id: UUID, query_text: str
) -> List[str]:
    from memory_mcp.services.stale import find_stale_references

    return await find_stale_references(session, thread_id, query_text, limit=5)


async def _rerank_with_llm(
    llm: LLMClient, query: str, chunks: List[dict[str, Any]]
) -> List[dict[str, Any]]:
    snippet = [
        {"id": chunk["item_id"], "text": chunk["text"][:200]}
        for chunk in chunks[:20]
    ]
    messages = [
        {
            "role": "system",
            "content": RERANK_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Pick the best 8 chunks for query '{query}'. Return JSON list of ids. Chunks: {snippet}",
        },
    ]
    response = await llm.chat_json(messages)
    ordered_ids = response.get("ids", [])
    if not ordered_ids:
        return chunks
    lookup = {str(chunk["item_id"]): chunk for chunk in chunks}
    reranked = [lookup[item_id] for item_id in ordered_ids if item_id in lookup]
    return reranked or chunks

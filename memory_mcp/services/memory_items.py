from __future__ import annotations

import difflib
from datetime import datetime
from typing import List, Tuple
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.config import settings
from memory_mcp.policies import dedup_policy
from memory_mcp.prompts import COMPARE_SYSTEM_PROMPT, SUPERSEDE_REASON_SYSTEM_PROMPT
from memory_mcp.models import MemoryItem
from memory_mcp.schemas import MemoryStatus, MemoryType
from memory_mcp.services.llm_client import LLMClient


def _text_similarity(statement_a: str, statement_b: str) -> float:
    return difflib.SequenceMatcher(None, statement_a, statement_b).ratio()


def _material_change(statement_a: str, statement_b: str) -> bool:
    return _text_similarity(statement_a, statement_b) < 0.95


def _apply_importance_heuristics(item: dict) -> dict:
    importance = item.get("importance", 0.5)
    text = f"{item.get('title','')} {item.get('statement','')}".lower()
    if any(word in text for word in ["final", "karar", "kesin", "asla"]):
        importance = min(1.0, importance + 0.1)
    if "security" in item.get("tags", []) or "performance" in item.get("tags", []):
        importance = min(1.0, importance + 0.1)
    if "core" in item.get("affects", []):
        importance = min(1.0, importance + 0.05)
    item["importance"] = importance
    return item


async def find_candidates(
    session: AsyncSession,
    embedding: List[float],
    item_type: MemoryType,
    thread_id: UUID,
    limit: int = 5,
) -> List[tuple[MemoryItem, float]]:
    distance = MemoryItem.embedding.cosine_distance(embedding)
    result = await session.execute(
        select(MemoryItem, distance.label("distance"))
        .where(
            MemoryItem.thread_id == thread_id,
            MemoryItem.type == item_type.value,
            MemoryItem.status == MemoryStatus.active.value,
            MemoryItem.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(limit)
    )
    return list(result.all())


async def keyword_candidates(
    session: AsyncSession,
    text: str,
    item_type: MemoryType,
    thread_id: UUID,
    limit: int = 5,
) -> List[MemoryItem]:
    query = func.plainto_tsquery("english", text)
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.thread_id == thread_id,
            MemoryItem.type == item_type.value,
            MemoryItem.status == MemoryStatus.active.value,
            MemoryItem.tsv.op("@@")(query),
        )
        .limit(limit)
    )
    return list(result.scalars())


async def upsert_memory_item(
    session: AsyncSession,
    llm: LLMClient,
    thread_id: UUID,
    item_type: MemoryType,
    payload: dict,
    evidence_turn_ids: List[UUID],
) -> Tuple[MemoryItem, str]:
    payload = _apply_importance_heuristics(payload)
    embeddings = await llm.embed([f"{payload['title']} {payload['statement']}"])
    embedding = embeddings[0]
    candidates = await find_candidates(session, embedding, item_type, thread_id)
    kw_candidates = await keyword_candidates(session, payload["statement"], item_type, thread_id)
    candidates_map = {c.id: (c, distance) for c, distance in candidates}
    for candidate in kw_candidates:
        candidates_map.setdefault(candidate.id, (candidate, None))
    best_match = None
    best_similarity = 0.0
    for candidate, distance in candidates_map.values():
        if distance is None:
            similarity = _text_similarity(candidate.statement, payload["statement"])
        else:
            similarity = 1 - distance
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = candidate

    policy = dedup_policy()
    if best_match and best_similarity >= policy.dedup_threshold:
        if best_similarity < policy.llm_guard_min:
            return await _insert_new(session, thread_id, item_type, payload, evidence_turn_ids, embedding)
        relation = await _compare_with_llm(llm, best_match.statement, payload["statement"])
        if relation != "same":
            return await _insert_new(session, thread_id, item_type, payload, evidence_turn_ids, embedding)
        new_evidence = list({*(best_match.evidence_turn_ids or []), *evidence_turn_ids})
        await session.execute(
            update(MemoryItem)
            .where(MemoryItem.id == best_match.id)
            .values(evidence_turn_ids=new_evidence, updated_at=datetime.utcnow())
        )
        await session.commit()
        return best_match, "deduped"

    if best_match and best_similarity >= policy.supersede_threshold:
        if _material_change(best_match.statement, payload["statement"]):
            relation = await _compare_with_llm(llm, best_match.statement, payload["statement"])
            if relation == "different":
                return await _insert_new(session, thread_id, item_type, payload, evidence_turn_ids, embedding)
            reason = await _supersede_reason(llm, best_match.statement, payload["statement"])
            new_item = MemoryItem(
                thread_id=thread_id,
                type=item_type.value,
                status=MemoryStatus.active.value,
                title=payload["title"],
                statement=payload["statement"],
                importance=payload["importance"],
                confidence=payload["confidence"],
                severity=payload.get("severity", 0.0),
                tags=payload.get("tags", []),
                affects=payload.get("affects", []),
                code_refs=payload.get("code_refs", []),
                evidence_turn_ids=evidence_turn_ids,
                supersedes_id=best_match.id,
                supersede_reason=reason,
                embedding=embedding,
            )
            session.add(new_item)
            await session.commit()
            await session.refresh(new_item)
            await session.execute(
                update(MemoryItem)
                .where(MemoryItem.id == best_match.id)
                .values(
                    status=MemoryStatus.superseded.value,
                    superseded_by_id=new_item.id,
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()
            return new_item, "superseded"

    return await _insert_new(session, thread_id, item_type, payload, evidence_turn_ids, embedding)


async def _supersede_reason(llm: LLMClient, old: str, new: str) -> str:
    if settings.fake_llm:
        return "Updated decision to reflect new requirements."
    messages = [
        {
            "role": "system",
            "content": SUPERSEDE_REASON_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Explain briefly why this statement supersedes the old one. Old: {old} New: {new}",
        },
    ]
    response = await llm.chat_json(messages)
    return response.get("reason", "Updated to match new information.")


async def _compare_with_llm(llm: LLMClient, old: str, new: str) -> str:
    if settings.fake_llm:
        if _text_similarity(old, new) > 0.9:
            return "same"
        return "update"
    messages = [
        {
            "role": "system",
            "content": COMPARE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Old: {old}\nNew: {new}",
        },
    ]
    response = await llm.chat_json(messages)
    return response.get("relation", "different")


async def _insert_new(
    session: AsyncSession,
    thread_id: UUID,
    item_type: MemoryType,
    payload: dict,
    evidence_turn_ids: List[UUID],
    embedding: List[float],
) -> Tuple[MemoryItem, str]:
    new_item = MemoryItem(
        thread_id=thread_id,
        type=item_type.value,
        status=MemoryStatus.active.value,
        title=payload["title"],
        statement=payload["statement"],
        importance=payload["importance"],
        confidence=payload["confidence"],
        severity=payload.get("severity", 0.0),
        tags=payload.get("tags", []),
        affects=payload.get("affects", []),
        code_refs=payload.get("code_refs", []),
        evidence_turn_ids=evidence_turn_ids,
        embedding=embedding,
    )
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    return new_item, "inserted"


async def list_by_type_status(
    session: AsyncSession, thread_id: UUID, item_type: MemoryType, status: MemoryStatus
) -> List[MemoryItem]:
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.thread_id == thread_id,
            MemoryItem.type == item_type.value,
            MemoryItem.status == status.value,
        )
        .order_by(MemoryItem.importance.desc(), MemoryItem.updated_at.desc())
    )
    return list(result.scalars())

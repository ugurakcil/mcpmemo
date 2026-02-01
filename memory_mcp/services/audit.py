from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.models import MemoryItem
from memory_mcp.prompts import AUDIT_SYSTEM_PROMPT
from memory_mcp.schemas import MemoryStatus
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.stale import find_stale_references


async def audit_consistency(
    session: AsyncSession,
    llm: LLMClient,
    thread_id: UUID,
    plan_text: str,
    deep: bool,
) -> dict[str, List[str]]:
    active_items = await _load_items(session, thread_id, MemoryStatus.active)
    superseded_items = await _load_items(session, thread_id, MemoryStatus.superseded)

    stale_refs = await find_stale_references(session, thread_id, plan_text)

    if deep:
        response = await _audit_with_llm(llm, plan_text, active_items, superseded_items)
        response["stale_references"] = list(set(response.get("stale_references", []) + stale_refs))
        return response

    return {
        "violations": [],
        "stale_references": stale_refs,
        "missing_constraints": [],
        "fixes": [],
    }


async def _load_items(
    session: AsyncSession, thread_id: UUID, status: MemoryStatus
) -> List[MemoryItem]:
    result = await session.execute(
        select(MemoryItem)
        .where(MemoryItem.thread_id == thread_id, MemoryItem.status == status.value)
        .order_by(MemoryItem.updated_at.desc())
    )
    return list(result.scalars())


async def _audit_with_llm(
    llm: LLMClient,
    plan_text: str,
    active_items: List[MemoryItem],
    superseded_items: List[MemoryItem],
) -> dict:
    def serialize(items: List[MemoryItem]) -> List[dict]:
        return [
            {
                "id": str(item.id),
                "type": item.type,
                "title": item.title,
                "statement": item.statement,
            }
            for item in items
        ]

    messages = [
        {
            "role": "system",
            "content": AUDIT_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                "Return JSON with keys: violations, stale_references, missing_constraints, fixes. "
                "Violations should mention conflicting decisions/constraints, stale_references should explain superseded usage, "
                "fixes should be actionable. Plan text: "
                f"{plan_text}\nActive items: {serialize(active_items)}\nSuperseded items: {serialize(superseded_items)}"
            ),
        },
    ]
    response = await llm.chat_json(messages)
    return {
        "violations": response.get("violations", []),
        "stale_references": response.get("stale_references", []),
        "missing_constraints": response.get("missing_constraints", []),
        "fixes": response.get("fixes", []),
    }

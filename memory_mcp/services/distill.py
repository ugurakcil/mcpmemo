from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.prompts import DISTILL_SYSTEM_PROMPT
from memory_mcp.schemas import DistillResult, MemoryType
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.memory_items import upsert_memory_item
from memory_mcp.services.turns import get_recent_turns


async def distill_extract(
    session: AsyncSession,
    llm: LLMClient,
    thread_id: UUID,
    turn_id: UUID,
    include_recent_turns: int,
    write_to_memory: bool,
) -> dict[str, Any]:
    turns = await get_recent_turns(session, thread_id, include_recent_turns)
    turns_text = "\n".join([f"{turn.role}: {turn.text}" for turn in reversed(turns)])

    messages = [
        {
            "role": "system",
            "content": DISTILL_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Conversation:\n{turns_text}",
        },
    ]
    response = await llm.chat_json(messages)
    extracted = DistillResult(**response)

    inserted = 0
    deduped = 0
    superseded = 0

    if write_to_memory:
        for key, item_type in [
            ("decisions", MemoryType.decision),
            ("constraints", MemoryType.constraint),
            ("mistakes", MemoryType.mistake),
            ("assumptions", MemoryType.assumption),
            ("open_questions", MemoryType.open_question),
        ]:
            items = getattr(extracted, key)
            for item in items:
                memory_item, status = await upsert_memory_item(
                    session,
                    llm,
                    thread_id,
                    item_type,
                    item.model_dump(),
                    [turn_id],
                )
                if status == "inserted":
                    inserted += 1
                elif status == "deduped":
                    deduped += 1
                elif status == "superseded":
                    superseded += 1

    return {
        "inserted": inserted,
        "deduped": deduped,
        "superseded": superseded,
        "extracted": extracted,
    }

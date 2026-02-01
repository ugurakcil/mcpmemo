from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.models import Turn
from memory_mcp.services import distill
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.retention import apply_retention


async def handle_embed_turn(
    session: AsyncSession, payload: dict, llm: LLMClient
) -> None:
    turn_id = UUID(payload["turn_id"])
    result = await session.execute(select(Turn).where(Turn.id == turn_id))
    turn = result.scalar_one()
    if turn.embedding is not None:
        return
    embeddings = await llm.embed([payload.get("text", turn.text)])
    await session.execute(
        update(Turn).where(Turn.id == turn_id).values(embedding=embeddings[0])
    )
    await session.commit()


async def handle_distill_turn(
    session: AsyncSession, payload: dict, llm: LLMClient
) -> None:
    await distill.distill_extract(
        session,
        llm,
        UUID(payload["thread_id"]),
        UUID(payload["turn_id"]),
        include_recent_turns=4,
        write_to_memory=True,
    )


async def handle_retention_cleanup(session: AsyncSession, payload: dict, llm: LLMClient) -> None:
    await apply_retention(session)

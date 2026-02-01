from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.config import settings
from memory_mcp.models import Plan, Thread, Turn
from memory_mcp.services import jobs
from memory_mcp.services.llm_client import LLMClient


async def create_thread(session: AsyncSession, plan_id, meta: dict) -> Thread:
    result = await session.execute(select(Plan).where(Plan.id == plan_id))
    result.scalar_one()
    thread = Thread(plan_id=plan_id, meta=meta)
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread


async def ingest_turn(
    session: AsyncSession,
    llm: LLMClient,
    thread_id: UUID,
    role: str,
    text: str,
    ts: datetime | None,
    meta: dict,
    branch_id: str | None,
    external_turn_id: str | None,
    embed_now: bool,
) -> Turn:
    if external_turn_id:
        existing = await session.execute(
            select(Turn).where(
                Turn.thread_id == thread_id, Turn.external_turn_id == external_turn_id
            )
        )
        turn = existing.scalar_one_or_none()
        if turn is not None:
            return turn
    turn = Turn(
        thread_id=thread_id,
        role=role,
        text=text,
        ts=ts or datetime.utcnow(),
        meta=meta,
        branch_id=branch_id,
        external_turn_id=external_turn_id,
    )
    session.add(turn)
    await session.commit()
    await session.refresh(turn)
    await session.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(updated_at=datetime.utcnow())
    )
    await session.commit()
    if embed_now and settings.ingest_embed_sync:
        embeddings = await llm.embed([text])
        turn.embedding = embeddings[0]
        await session.commit()
    elif embed_now:
        await jobs.enqueue_job(
            session,
            job_type="embed_turn",
            payload={"turn_id": str(turn.id), "text": text},
        )
    if settings.auto_distill_on_ingest:
        await jobs.enqueue_job(
            session,
            job_type="distill_turn",
            payload={"thread_id": str(thread_id), "turn_id": str(turn.id)},
        )
    return turn


async def get_recent_turns(
    session: AsyncSession, thread_id: UUID, limit: int
) -> List[Turn]:
    result = await session.execute(
        select(Turn)
        .where(Turn.thread_id == thread_id)
        .order_by(Turn.ts.desc())
        .limit(limit)
    )
    return list(result.scalars())

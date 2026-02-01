from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.policies import retention_policy
from memory_mcp.models import Turn, MemoryItem


async def apply_retention(session: AsyncSession) -> None:
    policy = retention_policy()
    if policy.retention_days_turns > 0:
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days_turns)
        await session.execute(delete(Turn).where(Turn.ts < cutoff))
    if policy.retention_days_memory > 0:
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days_memory)
        await session.execute(delete(MemoryItem).where(MemoryItem.updated_at < cutoff))
    await session.commit()

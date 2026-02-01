from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.models import MemoryItem
from memory_mcp.schemas import MemoryStatus


async def find_stale_references(
    session: AsyncSession, thread_id: UUID, text: str, limit: int = 10
) -> List[str]:
    ts_query = func.plainto_tsquery("english", text)
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.thread_id == thread_id,
            MemoryItem.status == MemoryStatus.superseded.value,
            MemoryItem.tsv.op("@@")(ts_query),
        )
        .limit(limit)
    )
    return [
        f"Plan references superseded item '{item.title}'. Use newer decision if available."
        for item in result.scalars()
    ]

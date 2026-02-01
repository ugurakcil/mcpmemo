from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.models import MemoryItem


async def override_scores(
    session: AsyncSession,
    item_id: UUID,
    importance: Optional[float],
    confidence: Optional[float],
    severity: Optional[float],
    reason: str,
) -> MemoryItem:
    result = await session.execute(select(MemoryItem).where(MemoryItem.id == item_id))
    item = result.scalar_one()
    meta = dict(item.meta or {})
    overrides = meta.get("overrides", [])
    overrides.append(
        {
            "importance": importance,
            "confidence": confidence,
            "severity": severity,
            "reason": reason,
            "ts": datetime.utcnow().isoformat(),
        }
    )
    meta["overrides"] = overrides
    values = {"meta": meta, "updated_at": datetime.utcnow()}
    if importance is not None:
        values["importance"] = importance
    if confidence is not None:
        values["confidence"] = confidence
    if severity is not None:
        values["severity"] = severity
    await session.execute(update(MemoryItem).where(MemoryItem.id == item_id).values(**values))
    await session.commit()
    await session.refresh(item)
    return item

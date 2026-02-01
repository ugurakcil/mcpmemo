from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.models import MemoryItem
from memory_mcp.schemas import MemoryStatus


async def deprecate_item(session: AsyncSession, item_id: UUID, reason: str) -> MemoryItem:
    result = await session.execute(select(MemoryItem).where(MemoryItem.id == item_id))
    item = result.scalar_one()
    meta = dict(item.meta or {})
    meta["deprecate_reason"] = reason
    await session.execute(
        update(MemoryItem)
        .where(MemoryItem.id == item_id)
        .values(status=MemoryStatus.deprecated.value, meta=meta, updated_at=datetime.utcnow())
    )
    await session.commit()
    await session.refresh(item)
    return item


async def supersede_item(
    session: AsyncSession,
    old_item_id: UUID,
    new_item_payload: dict,
    reason: str,
) -> MemoryItem:
    result = await session.execute(select(MemoryItem).where(MemoryItem.id == old_item_id))
    old_item = result.scalar_one()
    new_item = MemoryItem(
        thread_id=old_item.thread_id,
        type=old_item.type,
        status=MemoryStatus.active.value,
        title=new_item_payload["title"],
        statement=new_item_payload["statement"],
        importance=new_item_payload["importance"],
        confidence=new_item_payload["confidence"],
        severity=new_item_payload.get("severity", 0.0),
        tags=new_item_payload.get("tags", []),
        affects=new_item_payload.get("affects", []),
        code_refs=new_item_payload.get("code_refs", []),
        evidence_turn_ids=new_item_payload.get("evidence_turn_ids", []),
        supersedes_id=old_item.id,
        supersede_reason=reason,
    )
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)

    await session.execute(
        update(MemoryItem)
        .where(MemoryItem.id == old_item.id)
        .values(
            status=MemoryStatus.superseded.value,
            superseded_by_id=new_item.id,
            updated_at=datetime.utcnow(),
        )
    )
    await session.commit()
    return new_item

from __future__ import annotations

from datetime import datetime
from typing import Any, List
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.models import Plan


async def create_plan(session: AsyncSession, name: str, meta: dict[str, Any]) -> Plan:
    plan = Plan(name=name, meta=meta)
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def list_plans(session: AsyncSession, include_archived: bool) -> List[Plan]:
    query = select(Plan)
    if not include_archived:
        query = query.where(Plan.status == "active")
    result = await session.execute(query.order_by(Plan.updated_at.desc()))
    return list(result.scalars())


async def get_plan(session: AsyncSession, plan_id: UUID) -> Plan:
    result = await session.execute(select(Plan).where(Plan.id == plan_id))
    return result.scalar_one()


async def rename_plan(session: AsyncSession, plan_id: UUID, name: str) -> Plan:
    await session.execute(
        update(Plan)
        .where(Plan.id == plan_id)
        .values(name=name, updated_at=datetime.utcnow())
    )
    await session.commit()
    return await get_plan(session, plan_id)


async def archive_plan(session: AsyncSession, plan_id: UUID, archived: bool) -> Plan:
    status = "archived" if archived else "active"
    await session.execute(
        update(Plan)
        .where(Plan.id == plan_id)
        .values(status=status, updated_at=datetime.utcnow())
    )
    await session.commit()
    return await get_plan(session, plan_id)


async def touch_plan(session: AsyncSession, plan_id: UUID) -> Plan:
    await session.execute(
        update(Plan)
        .where(Plan.id == plan_id)
        .values(updated_at=datetime.utcnow())
    )
    await session.commit()
    return await get_plan(session, plan_id)

from __future__ import annotations

import pytest

from memory_mcp.services.plans import create_plan, list_plans, rename_plan, archive_plan, touch_plan


@pytest.mark.asyncio
async def test_plan_registry_flow(db_session):
    plan = await create_plan(db_session, "alpha", {})
    plans = await list_plans(db_session, include_archived=False)
    assert any(item.id == plan.id for item in plans)

    renamed = await rename_plan(db_session, plan.id, "beta")
    assert renamed.name == "beta"

    archived = await archive_plan(db_session, plan.id, archived=True)
    assert archived.status == "archived"

    touched = await touch_plan(db_session, plan.id)
    assert touched.updated_at >= archived.updated_at

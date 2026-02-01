from __future__ import annotations

import pytest

from memory_mcp.services.plans import create_plan
from memory_mcp.services.turns import create_thread, ingest_turn
from memory_mcp.services.llm_client import LLMClient


@pytest.mark.asyncio
async def test_turn_ingest_idempotent(db_session):
    plan = await create_plan(db_session, "plan", {})
    thread = await create_thread(db_session, plan.id, {})
    llm = LLMClient()

    turn1 = await ingest_turn(
        db_session,
        llm,
        thread.id,
        "user",
        "First turn",
        None,
        {},
        None,
        "external-1",
        False,
    )
    turn2 = await ingest_turn(
        db_session,
        llm,
        thread.id,
        "user",
        "First turn",
        None,
        {},
        None,
        "external-1",
        False,
    )
    assert turn1.id == turn2.id
    await llm.close()

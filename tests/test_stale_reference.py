from __future__ import annotations

import pytest

from memory_mcp.schemas import MemoryStatus, MemoryType
from memory_mcp.services.audit import audit_consistency
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.turns import create_thread
from memory_mcp.services.plans import create_plan
from memory_mcp.models import MemoryItem


@pytest.mark.asyncio
async def test_stale_reference_detection(db_session):
    plan = await create_plan(db_session, "plan", {})
    thread = await create_thread(db_session, plan.id, {})
    stale_item = MemoryItem(
        thread_id=thread.id,
        type=MemoryType.decision.value,
        status=MemoryStatus.superseded.value,
        title="Old storage",
        statement="Use SQLite",
        importance=0.5,
        confidence=0.5,
        severity=0.0,
        tags=[],
        affects=[],
        code_refs=[],
        evidence_turn_ids=[],
        meta={},
    )
    db_session.add(stale_item)
    await db_session.commit()

    llm = LLMClient()
    result = await audit_consistency(db_session, llm, thread.id, "We will use SQLite", False)
    assert result["stale_references"]
    await llm.close()

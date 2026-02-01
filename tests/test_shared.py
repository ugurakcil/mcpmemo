from __future__ import annotations

import pytest

from memory_mcp.config import settings
from memory_mcp.models import MemoryItem
from memory_mcp.schemas import MemoryStatus, MemoryType
from memory_mcp.services.shared import export_shared, import_shared
from memory_mcp.services.turns import create_thread
from memory_mcp.services.plans import create_plan


@pytest.mark.asyncio
async def test_shared_export_import(db_session):
    settings.shared_hmac_secret = "secret"
    plan = await create_plan(db_session, "plan", {})
    thread = await create_thread(db_session, plan.id, {})
    item = MemoryItem(
        thread_id=thread.id,
        type=MemoryType.decision.value,
        status=MemoryStatus.active.value,
        title="Decision",
        statement="Use Postgres",
        importance=0.7,
        confidence=0.6,
        severity=0.0,
        tags=[],
        affects=[],
        code_refs=[],
        evidence_turn_ids=[],
        meta={},
    )
    db_session.add(item)
    await db_session.commit()

    exported = await export_shared(
        db_session,
        thread.id,
        [MemoryType.decision],
        include_mistakes=False,
        expires_in_minutes=60,
    )
    imported = await import_shared(db_session, exported["payload"], exported["signature"])
    assert imported["imported_count"] == 1

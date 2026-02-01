from __future__ import annotations

import pytest

from memory_mcp.config import settings
from memory_mcp.schemas import MemoryType
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.memory_items import upsert_memory_item
from memory_mcp.services.turns import create_thread
from memory_mcp.services.plans import create_plan


@pytest.mark.asyncio
async def test_dedup_and_supersede(db_session):
    plan = await create_plan(db_session, "plan", {})
    thread = await create_thread(db_session, plan.id, {})
    llm = LLMClient()

    settings.dedup_sim_threshold = 0.99
    settings.supersede_sim_threshold = 0.1

    payload = {
        "title": "Decision",
        "statement": "Use Postgres for storage",
        "importance": 0.6,
        "confidence": 0.6,
        "severity": 0.0,
        "tags": [],
        "affects": [],
        "code_refs": [],
    }

    item1, status1 = await upsert_memory_item(
        db_session, llm, thread.id, MemoryType.decision, payload, []
    )
    assert status1 == "inserted"

    item2, status2 = await upsert_memory_item(
        db_session, llm, thread.id, MemoryType.decision, payload, []
    )
    assert status2 == "deduped"

    payload["statement"] = "Use Postgres with pgvector for embeddings"
    item3, status3 = await upsert_memory_item(
        db_session, llm, thread.id, MemoryType.decision, payload, []
    )
    assert status3 == "superseded"
    assert item3.supersedes_id == item1.id
    await llm.close()

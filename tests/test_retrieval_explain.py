from __future__ import annotations

import pytest

from memory_mcp.models import MemoryItem
from memory_mcp.schemas import MemoryStatus, MemoryType, RetrievalMode, RetrievalScope
from memory_mcp.services.plans import create_plan
from memory_mcp.services.retrieval import retrieve_context
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.turns import create_thread


@pytest.mark.asyncio
async def test_retrieval_explain_and_stale(db_session):
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
    result = await retrieve_context(
        db_session,
        llm,
        thread.id,
        "SQLite",
        RetrievalMode.fast,
        RetrievalScope.distilled_only,
        top_k=5,
        token_budget=200,
        recency_bias=0.1,
        explain=True,
    )
    assert result["stale_references"]
    await llm.close()

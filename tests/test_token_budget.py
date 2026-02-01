from __future__ import annotations

import pytest

from memory_mcp.schemas import MemoryType, RetrievalMode, RetrievalScope
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.memory_items import upsert_memory_item
from memory_mcp.services.retrieval import retrieve_context
from memory_mcp.services.turns import create_thread
from memory_mcp.services.plans import create_plan


@pytest.mark.asyncio
async def test_token_budget_packing(db_session):
    plan = await create_plan(db_session, "plan", {})
    thread = await create_thread(db_session, plan.id, {})
    llm = LLMClient()

    for idx in range(3):
        payload = {
            "title": f"Decision {idx}",
            "statement": "word " * 100,
            "importance": 0.6,
            "confidence": 0.6,
            "severity": 0.0,
            "tags": [],
            "affects": [],
            "code_refs": [],
        }
        await upsert_memory_item(db_session, llm, thread.id, MemoryType.decision, payload, [])

    result = await retrieve_context(
        db_session,
        llm,
        thread.id,
        "decision",
        RetrievalMode.fast,
        RetrievalScope.distilled_only,
        top_k=5,
        token_budget=200,
        recency_bias=0.1,
        explain=False,
    )
    assert result["est_tokens"] <= 200
    assert len(result["chunks"]) >= 1
    await llm.close()

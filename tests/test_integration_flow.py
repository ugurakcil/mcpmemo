from __future__ import annotations

import pytest

from memory_mcp.schemas import RetrievalMode, RetrievalScope
from memory_mcp.services import distill, retrieval
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.turns import create_thread, ingest_turn
from memory_mcp.services.plans import create_plan


@pytest.mark.asyncio
async def test_ingest_distill_retrieve(db_session):
    plan = await create_plan(db_session, "plan", {})
    thread = await create_thread(db_session, plan.id, {})
    llm = LLMClient()

    turn = await ingest_turn(
        db_session,
        llm,
        thread.id,
        "user",
        "This decision is to use Postgres.",
        None,
        {},
        None,
        None,
        True,
    )

    result = await distill.distill_extract(
        db_session,
        llm,
        thread.id,
        turn.id,
        include_recent_turns=2,
        write_to_memory=True,
    )
    assert result["inserted"] >= 1

    context = await retrieval.retrieve_context(
        db_session,
        llm,
        thread.id,
        "What is the decision?",
        RetrievalMode.fast,
        RetrievalScope.distilled_only,
        top_k=5,
        token_budget=200,
        recency_bias=0.1,
        explain=False,
    )
    assert context["chunks"]
    await llm.close()

from __future__ import annotations

import pytest

from memory_mcp.services.jobs import enqueue_job, fetch_next_job, complete_job
from memory_mcp.services.job_handlers import handle_embed_turn
from memory_mcp.services.llm_client import LLMClient
from memory_mcp.services.plans import create_plan
from memory_mcp.services.turns import create_thread, ingest_turn


@pytest.mark.asyncio
async def test_embed_job_processing(db_session):
    plan = await create_plan(db_session, "plan", {})
    thread = await create_thread(db_session, plan.id, {})
    llm = LLMClient()

    turn = await ingest_turn(
        db_session,
        llm,
        thread.id,
        "user",
        "Embed this",
        None,
        {},
        None,
        "external-embed",
        False,
    )

    await enqueue_job(
        db_session,
        "embed_turn",
        {"turn_id": str(turn.id), "text": turn.text},
    )

    job = await fetch_next_job(db_session)
    assert job is not None
    await handle_embed_turn(db_session, job.payload, llm)
    await complete_job(db_session, job)

    assert turn.embedding is None
    await db_session.refresh(turn)
    assert turn.embedding is not None
    await llm.close()

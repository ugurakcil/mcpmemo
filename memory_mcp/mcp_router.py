from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp import metrics
from memory_mcp.db import get_session
from memory_mcp.schemas import (
    AuditCheckRequest,
    DistillExtractRequest,
    MemoryDeprecateRequest,
    MemorySupersedeRequest,
    PlanArchiveRequest,
    PlanCreateRequest,
    PlanGetRequest,
    PlanListRequest,
    PlanRenameRequest,
    PlanTouchRequest,
    RetrieveDecisionStateRequest,
    RetrieveContextRequest,
    ScoreOverrideRequest,
    SharedExportRequest,
    SharedImportRequest,
    ThreadCreateRequest,
    TurnIngestRequest,
)
from memory_mcp.services import admin, audit, decision_state, distill, plans, retrieval, scoring, shared, turns
from memory_mcp.services.llm_client import LLMClient

router = APIRouter()
llm_client = LLMClient()


class ToolRequest(BaseModel):
    tool: str
    arguments: dict[str, Any]


@router.post("")
async def mcp_entry(
    request: ToolRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    tool_name = request.tool
    start = time.time()
    metrics.tool_calls.labels(tool=tool_name).inc()
    try:
        if tool_name == "thread.create":
            payload = ThreadCreateRequest(**request.arguments)
            thread = await turns.create_thread(session, payload.plan_id, payload.meta)
            return {"thread_id": thread.id}
        if tool_name == "turn.ingest":
            payload = TurnIngestRequest(**request.arguments)
            turn = await turns.ingest_turn(
                session,
                llm_client,
                payload.thread_id,
                payload.role,
                payload.text,
                payload.ts,
                payload.meta,
                payload.branch_id,
                payload.external_turn_id,
                payload.embed_now,
            )
            return {"turn_id": turn.id}
        if tool_name == "plan.create":
            payload = PlanCreateRequest(**request.arguments)
            plan = await plans.create_plan(session, payload.name, payload.meta)
            return {"plan_id": plan.id}
        if tool_name == "plan.list":
            payload = PlanListRequest(**request.arguments)
            items = await plans.list_plans(session, payload.include_archived)
            return {
                "plans": [
                    {
                        "id": plan.id,
                        "name": plan.name,
                        "status": plan.status,
                        "updated_at": plan.updated_at,
                    }
                    for plan in items
                ]
            }
        if tool_name == "plan.get":
            payload = PlanGetRequest(**request.arguments)
            plan = await plans.get_plan(session, payload.plan_id)
            return {
                "id": plan.id,
                "name": plan.name,
                "status": plan.status,
                "updated_at": plan.updated_at,
                "meta": plan.meta,
            }
        if tool_name == "plan.rename":
            payload = PlanRenameRequest(**request.arguments)
            plan = await plans.rename_plan(session, payload.plan_id, payload.name)
            return {"id": plan.id, "name": plan.name}
        if tool_name == "plan.archive":
            payload = PlanArchiveRequest(**request.arguments)
            plan = await plans.archive_plan(session, payload.plan_id, payload.archived)
            return {"id": plan.id, "status": plan.status}
        if tool_name == "plan.touch":
            payload = PlanTouchRequest(**request.arguments)
            plan = await plans.touch_plan(session, payload.plan_id)
            return {"id": plan.id, "updated_at": plan.updated_at}
        if tool_name == "distill.extract":
            payload = DistillExtractRequest(**request.arguments)
            return await distill.distill_extract(
                session,
                llm_client,
                payload.thread_id,
                payload.turn_id,
                payload.include_recent_turns,
                payload.write_to_memory,
            )
        if tool_name == "retrieve.decision_state":
            payload = RetrieveDecisionStateRequest(**request.arguments)
            return await decision_state.decision_state(session, payload.thread_id)
        if tool_name == "retrieve.context":
            payload = RetrieveContextRequest(**request.arguments)
            return await retrieval.retrieve_context(
                session,
                llm_client,
                payload.thread_id,
                payload.query,
                payload.mode,
                payload.scope,
                payload.top_k,
                payload.token_budget,
                payload.recency_bias,
                payload.explain,
            )
        if tool_name == "audit.check_consistency":
            payload = AuditCheckRequest(**request.arguments)
            return await audit.audit_consistency(
                session,
                llm_client,
                payload.thread_id,
                payload.proposed_plan_text,
                payload.deep,
            )
        if tool_name == "memory.deprecate":
            payload = MemoryDeprecateRequest(**request.arguments)
            item = await admin.deprecate_item(session, payload.item_id, payload.reason)
            return {"item_id": item.id, "status": item.status}
        if tool_name == "memory.supersede":
            payload = MemorySupersedeRequest(**request.arguments)
            item = await admin.supersede_item(
                session, payload.old_item_id, payload.new_item.model_dump(), payload.reason
            )
            return {"item_id": item.id, "status": item.status}
        if tool_name == "score.override":
            payload = ScoreOverrideRequest(**request.arguments)
            item = await scoring.override_scores(
                session,
                payload.item_id,
                payload.importance,
                payload.confidence,
                payload.severity,
                payload.reason,
            )
            return {"item_id": item.id, "status": item.status}
        if tool_name == "shared.export":
            payload = SharedExportRequest(**request.arguments)
            return await shared.export_shared(
                session,
                payload.thread_id,
                payload.types,
                payload.include_mistakes,
                payload.expires_in_minutes,
            )
        if tool_name == "shared.import":
            payload = SharedImportRequest(**request.arguments)
            return await shared.import_shared(session, payload.payload, payload.signature)

        raise HTTPException(status_code=404, detail=f"Unknown tool {tool_name}")
    finally:
        duration = time.time() - start
        metrics.tool_latency.labels(tool=tool_name).observe(duration)

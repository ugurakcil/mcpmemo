from __future__ import annotations

import asyncio

from fastapi import FastAPI
from sqlalchemy import text
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from memory_mcp.config import settings
from memory_mcp.db import engine, session_factory
from memory_mcp.logging import configure_logging
from memory_mcp.mcp_router import router as mcp_router, llm_client
from memory_mcp.services import jobs
from memory_mcp.services.job_handlers import (
    handle_distill_turn,
    handle_embed_turn,
    handle_retention_cleanup,
)
from memory_mcp.services.vector_index import ensure_vector_indexes


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name)
    stop_event = asyncio.Event()

    @app.on_event("startup")
    async def startup_event() -> None:
        await ensure_vector_indexes(engine)
        handlers = {
            "embed_turn": lambda session, payload: handle_embed_turn(session, payload, llm_client),
            "distill_turn": lambda session, payload: handle_distill_turn(session, payload, llm_client),
            "retention_cleanup": lambda session, payload: handle_retention_cleanup(
                session, payload, llm_client
            ),
        }
        app.state.job_worker = asyncio.create_task(
            jobs.job_worker(session_factory, handlers, stop_event)
        )
        app.state.retention_task = asyncio.create_task(_schedule_retention_jobs())

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        stop_event.set()
        if hasattr(app.state, "job_worker"):
            await app.state.job_worker
        if hasattr(app.state, "retention_task"):
            app.state.retention_task.cancel()
        await llm_client.close()

    @app.get("/health")
    async def health() -> dict[str, str]:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    if settings.metrics_enabled:
        @app.get("/metrics")
        async def metrics() -> Response:
            data = generate_latest()
            return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    app.include_router(mcp_router, prefix="/mcp")
    return app


async def _schedule_retention_jobs() -> None:
    while True:
        async with session_factory() as session:
            await jobs.enqueue_job(session, "retention_cleanup", payload={})
        await asyncio.sleep(settings.retention_cleanup_interval_s)


app = create_app()

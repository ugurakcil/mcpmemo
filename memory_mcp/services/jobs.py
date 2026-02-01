from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.config import settings
from memory_mcp.models import Job


JobHandler = Callable[[AsyncSession, dict[str, Any]], Coroutine[Any, Any, None]]


async def enqueue_job(
    session: AsyncSession,
    job_type: str,
    payload: dict[str, Any],
    run_at: datetime | None = None,
) -> Job:
    job = Job(
        type=job_type,
        payload=payload,
        run_at=run_at or datetime.utcnow(),
        status="pending",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def fetch_next_job(session: AsyncSession) -> Job | None:
    result = await session.execute(
        select(Job)
        .where(Job.status == "pending", Job.run_at <= datetime.utcnow())
        .order_by(Job.run_at.asc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(status="running", updated_at=datetime.utcnow())
    )
    await session.commit()
    return job


async def complete_job(session: AsyncSession, job: Job) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(status="done", updated_at=datetime.utcnow())
    )
    await session.commit()


async def fail_job(session: AsyncSession, job: Job, error: str) -> None:
    attempts = job.attempts + 1
    status = "failed" if attempts >= settings.job_max_attempts else "pending"
    run_at = datetime.utcnow() + timedelta(seconds=2**attempts)
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            status=status,
            attempts=attempts,
            last_error=error,
            run_at=run_at,
            updated_at=datetime.utcnow(),
        )
    )
    await session.commit()


async def job_worker(
    session_factory: Callable[[], AsyncSession],
    handlers: dict[str, JobHandler],
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        async with session_factory() as session:
            job = await fetch_next_job(session)
            if job is None:
                await asyncio.sleep(settings.job_poll_interval_s)
                continue
            handler = handlers.get(job.type)
            if handler is None:
                await fail_job(session, job, "Unknown job type")
                continue
            try:
                await handler(session, job.payload)
                await complete_job(session, job)
            except Exception as exc:
                await fail_job(session, job, str(exc))
        await asyncio.sleep(settings.job_poll_interval_s)

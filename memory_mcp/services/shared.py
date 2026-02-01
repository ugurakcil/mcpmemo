from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.config import settings
from memory_mcp.models import MemoryItem, SharedPackage, Thread
from memory_mcp.schemas import MemoryStatus, MemoryType
from memory_mcp.utils.hmac_utils import sign_payload, verify_signature


async def export_shared(
    session: AsyncSession,
    thread_id: UUID,
    types: List[MemoryType],
    include_mistakes: bool,
    expires_in_minutes: int,
) -> dict[str, Any]:
    if not settings.shared_hmac_secret:
        raise ValueError("SHARED_HMAC_SECRET is not configured")
    allow_types = {t.value for t in types}
    if include_mistakes:
        allow_types.add(MemoryType.mistake.value)
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.thread_id == thread_id,
            MemoryItem.type.in_(allow_types),
            MemoryItem.status == MemoryStatus.active.value,
        )
    )
    items = [
        {
            "type": item.type,
            "title": item.title,
            "statement": item.statement,
            "importance": item.importance,
            "confidence": item.confidence,
            "severity": item.severity,
            "tags": item.tags,
            "affects": item.affects,
            "code_refs": item.code_refs,
            "evidence_turn_ids": item.evidence_turn_ids,
        }
        for item in result.scalars()
    ]
    payload = {
        "thread_id": str(thread_id),
        "items": items,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(minutes=expires_in_minutes)).isoformat(),
    }
    signature = sign_payload(settings.shared_hmac_secret, payload)
    package = SharedPackage(
        payload=payload,
        signature=signature,
        expires_at=datetime.utcnow() + timedelta(minutes=expires_in_minutes),
    )
    session.add(package)
    await session.commit()
    await session.refresh(package)
    return {"package_id": package.id, "payload": payload, "signature": signature}


async def import_shared(
    session: AsyncSession, payload: dict[str, Any], signature: str
) -> dict[str, Any]:
    if not settings.shared_hmac_secret:
        raise ValueError("SHARED_HMAC_SECRET is not configured")
    if not verify_signature(settings.shared_hmac_secret, payload, signature):
        raise ValueError("Invalid signature")
    expires_at = datetime.fromisoformat(payload["expires_at"])
    if datetime.utcnow() > expires_at:
        raise ValueError("Package expired")

    thread = Thread()
    session.add(thread)
    await session.commit()
    await session.refresh(thread)

    inserted = []
    for item in payload.get("items", []):
        if item["type"] not in {
            MemoryType.decision.value,
            MemoryType.constraint.value,
            MemoryType.mistake.value,
        }:
            continue
        memory_item = MemoryItem(
            thread_id=thread.id,
            type=item["type"],
            status=MemoryStatus.active.value,
            title=item["title"],
            statement=item["statement"],
            importance=item.get("importance", 0.5),
            confidence=item.get("confidence", 0.5),
            severity=item.get("severity", 0.0),
            tags=item.get("tags", []),
            affects=item.get("affects", []),
            code_refs=item.get("code_refs", []),
            evidence_turn_ids=item.get("evidence_turn_ids", []),
            meta={"source": "external"},
        )
        session.add(memory_item)
        inserted.append(memory_item)
    await session.commit()

    return {
        "imported_count": len(inserted),
        "thread_id_created": thread.id,
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "type": item.type,
            }
            for item in inserted
        ],
    }

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from memory_mcp.schemas import MemoryStatus, MemoryType
from memory_mcp.services.memory_items import list_by_type_status


def _serialize(items: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": item.id,
            "title": item.title,
            "statement": item.statement,
            "importance": item.importance,
            "confidence": item.confidence,
        }
        for item in items
    ]


async def decision_state(session: AsyncSession, thread_id: UUID) -> dict[str, Any]:
    decisions = await list_by_type_status(session, thread_id, MemoryType.decision, MemoryStatus.active)
    constraints = await list_by_type_status(
        session, thread_id, MemoryType.constraint, MemoryStatus.active
    )
    mistakes = await list_by_type_status(session, thread_id, MemoryType.mistake, MemoryStatus.active)
    assumptions = await list_by_type_status(
        session, thread_id, MemoryType.assumption, MemoryStatus.active
    )
    open_questions = await list_by_type_status(
        session, thread_id, MemoryType.open_question, MemoryStatus.active
    )

    return {
        "decisions": _serialize(decisions),
        "constraints": _serialize(constraints),
        "avoid_list_mistakes": _serialize(mistakes),
        "assumptions": _serialize(assumptions),
        "open_questions": _serialize(open_questions),
    }

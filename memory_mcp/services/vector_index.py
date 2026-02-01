from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from memory_mcp.config import settings


async def ensure_vector_indexes(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        index_type = settings.vector_index_type.lower()
        if index_type == "auto":
            index_type = await _detect_vector_index(conn)
        if index_type == "hnsw":
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_turns_embedding_hnsw "
                    "ON turns USING hnsw (embedding vector_cosine_ops) "
                    "WITH (m = :m, ef_construction = :ef)"
                ),
                {"m": settings.vector_hnsw_m, "ef": settings.vector_hnsw_ef_construction},
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_memory_embedding_hnsw "
                    "ON memory_items USING hnsw (embedding vector_cosine_ops) "
                    "WITH (m = :m, ef_construction = :ef)"
                ),
                {"m": settings.vector_hnsw_m, "ef": settings.vector_hnsw_ef_construction},
            )
        else:
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_turns_embedding_ivfflat "
                    "ON turns USING ivfflat (embedding vector_cosine_ops) "
                    "WITH (lists = :lists)"
                ),
                {"lists": settings.vector_ivfflat_lists},
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_memory_embedding_ivfflat "
                    "ON memory_items USING ivfflat (embedding vector_cosine_ops) "
                    "WITH (lists = :lists)"
                ),
                {"lists": settings.vector_ivfflat_lists},
            )


async def _detect_vector_index(conn) -> str:
    try:
        result = await conn.execute(text("SHOW server_version_num"))
        _ = result.scalar_one()
        await conn.execute(
            text(
                "SELECT 1 FROM pg_am WHERE amname = 'hnsw'"
            )
        )
        result = await conn.execute(text("SELECT 1 FROM pg_am WHERE amname = 'hnsw'"))
        if result.scalar_one_or_none():
            return "hnsw"
    except Exception:
        return "ivfflat"
    return "ivfflat"

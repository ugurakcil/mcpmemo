from __future__ import annotations

import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from memory_mcp.config import settings

@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def alembic_config(postgres_container: PostgresContainer) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_container.get_connection_url())
    return config


@pytest.fixture(scope="session")
def migrated_db(alembic_config: Config) -> str:
    command.upgrade(alembic_config, "head")
    return alembic_config.get_main_option("sqlalchemy.url")


@pytest_asyncio.fixture()
async def db_session(migrated_db: str) -> AsyncSession:
    os.environ["DATABASE_URL"] = migrated_db
    os.environ["FAKE_LLM"] = "true"
    settings.database_url = migrated_db
    settings.fake_llm = True
    engine = create_async_engine(migrated_db, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()
